# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""S3 noise / mixing / manifest — gates on synthetic audio (no corpora needed)."""

from pathlib import Path

import numpy as np
import pytest

from fabench.audio import write_audio
from fabench.config import Config
from fabench.noise import synth
from fabench.noise.mixer import measure_snr_db, mix_at_snr
from fabench.noise.provider import NoiseProvider
from fabench.schema import Interval, Utterance

SR = 16000


def _speech(dur=1.5, f=180, silence_tail=0.5):
    t = np.arange(int(dur * SR)) / SR
    x = 0.3 * np.sin(2 * np.pi * f * t) * (t < (dur - silence_tail))
    return x


# --------------------------------------------------------------------------
# synth determinism + spectrum
# --------------------------------------------------------------------------
def test_synth_determinism():
    assert np.array_equal(synth.white(1000, 7), synth.white(1000, 7))
    assert not np.array_equal(synth.white(1000, 7), synth.white(1000, 8))
    assert np.array_equal(synth.pink(1000, 3), synth.pink(1000, 3))


def test_pink_is_low_pass_tilted():
    x = synth.pink(1 << 15, 1)
    spec = np.abs(np.fft.rfft(x)) ** 2
    lo = spec[1:100].mean()
    hi = spec[5000:6000].mean()
    assert lo > hi  # 1/f: more power at low freq


# --------------------------------------------------------------------------
# mixer: timing preservation (gate #1) + achieved SNR (gate #3)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ntype", ["white", "pink"])
@pytest.mark.parametrize("snr", [20, 15, 10])
def test_mix_timing_and_snr(ntype, snr):
    speech = _speech()
    noise = synth.generate(ntype, 3 * SR, seed=42)
    mixed, scale, _meta = mix_at_snr(speech, noise, snr, SR)
    assert len(mixed) == len(speech)  # sample-exact
    ach = measure_snr_db(speech, scale * noise[: len(speech)], SR)
    assert abs(ach - snr) < 0.5


def test_mix_rejects_short_noise():
    with pytest.raises(ValueError):
        mix_at_snr(_speech(dur=2.0), synth.white(1000, 1), 10, SR)


# --------------------------------------------------------------------------
# provider + held-out split
# --------------------------------------------------------------------------
def test_held_out_split_disjoint_deterministic():
    from fabench.noise.musan import held_out_split

    files = [Path(f"f{i}.wav") for i in range(20)]
    tr1, ev1 = held_out_split(files, seed=1)
    tr2, ev2 = held_out_split(files, seed=1)
    assert (tr1, ev1) == (tr2, ev2)                 # deterministic
    assert set(tr1).isdisjoint(set(ev1))            # disjoint
    assert len(tr1) + len(ev1) == 20


def test_provider_synth_and_babble(tmp_path):
    # synthetic musan speech pool: 8 short clips
    pool = []
    for i in range(8):
        p = tmp_path / f"sp{i}.wav"
        write_audio(p, 0.2 * synth.white(SR, i), SR)
        pool.append(p)
    prov = NoiseProvider(musan_speech_eval=pool, babble_min_sources=6)
    # white deterministic via provider
    a, src, _off = prov.segment("white", 8000, seed=5)
    b, _, _ = prov.segment("white", 8000, seed=5)
    assert np.array_equal(a, b) and src == "synthetic:white"
    # babble sums >=6 sources
    bab, prov_str, _ = prov.segment("babble", 8000, seed=9)
    assert len(bab) == 8000
    assert prov_str.count("+") >= 5  # >=6 sources joined by '+'


# --------------------------------------------------------------------------
# manifest: determinism (gate #6) + per-item timing/SNR
# --------------------------------------------------------------------------
def _mini_cfg(work_dir):
    return Config(
        raw={
            "seeds": {"mix": 123},
            "conditions": {
                "noise_types": ["white", "pink"],
                "snr_db": [20, 10],
                "include_clean": True,
            },
            "paths": {"work_dir": str(work_dir)},
        },
        path=Path("cfg.yaml"),
    )


def test_build_manifest_deterministic_and_gates(tmp_path):
    from fabench.audio import load_resample
    from fabench.noise.manifest import build_manifest

    # two synthetic utterances with real wav files
    utts = []
    for i in range(2):
        wav = tmp_path / f"u{i}.wav"
        write_audio(wav, _speech(), SR)
        utts.append(
            Utterance(f"u{i}", "toy", "read", f"spk{i}", str(wav), SR, 1.5,
                      phones=[Interval("s", 0.0, 1.0)])
        )
    cfg = _mini_cfg(tmp_path / "work")
    prov = NoiseProvider()  # only white/pink needed

    items1 = build_manifest(utts, cfg, prov, tmp_path / "mix1")
    items2 = build_manifest(utts, cfg, prov, tmp_path / "mix2")
    # determinism: identical manifest rows (ignoring the differing out path)
    d1 = [{k: v for k, v in it.to_dict().items() if k != "mixed_audio_path"} for it in items1]
    d2 = [{k: v for k, v in it.to_dict().items() if k != "mixed_audio_path"} for it in items2]
    assert d1 == d2

    # 2 utts x (clean + 2 noise x 2 snr) = 2 x 5 = 10 items
    assert len(items1) == 10
    # per-item timing + achieved SNR gate
    for it in items1:
        clean, sr = load_resample(str(Path(it.mixed_audio_path).parent / "clean.wav"), SR)
        mixed, _ = load_resample(it.mixed_audio_path, SR)
        assert len(mixed) == len(clean)
        if it.snr_db is not None:
            ach = measure_snr_db(clean, mixed[: len(clean)] - clean, sr)
            assert abs(ach - it.snr_db) < 0.5


# --------------------------------------------------------------------------
# MUSAN cache. cache/musan is read as "fetched", so it must never be partial.
# --------------------------------------------------------------------------
def _fake_musan_archive(where, kinds):
    import tarfile

    root = where / "tree" / "musan"
    for kind in kinds:
        (root / kind).mkdir(parents=True)
        (root / kind / "a.wav").write_bytes(b"RIFF")
    archive = where / "musan.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(root, arcname="musan")
    return archive


@pytest.mark.parametrize("damage", ["missing_kind", "truncated"])
def test_a_bad_musan_archive_leaves_no_musan_dir(tmp_path, damage):
    from fabench.noise.musan import _extract

    kinds = ["noise"] if damage == "missing_kind" else ["noise", "speech", "music"]
    archive = _fake_musan_archive(tmp_path, kinds)
    if damage == "truncated":
        archive.write_bytes(archive.read_bytes()[: archive.stat().st_size // 2])
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(Exception):  # noqa: B017  RuntimeError or tarfile's own error
        _extract(archive, cache)
    assert sorted(p.name for p in cache.iterdir()) == []


def test_a_whole_musan_archive_lands_with_all_three_kinds(tmp_path):
    from fabench.noise.musan import _extract

    cache = tmp_path / "cache"
    cache.mkdir()
    _extract(_fake_musan_archive(tmp_path, ["noise", "speech", "music"]), cache)
    assert sorted(p.name for p in (cache / "musan").iterdir()) == ["music", "noise", "speech"]
    assert [p.name for p in cache.iterdir()] == ["musan"]


def test_a_short_musan_download_leaves_no_tarball(tmp_path, monkeypatch):
    import requests

    from fabench.noise.musan import _fetch

    class Short:
        def __init__(self):
            self.headers = {"Content-Length": "10"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"12345"

    monkeypatch.setattr(requests, "get", lambda *a, **k: Short())
    dest = tmp_path / "musan.tar.gz"
    with pytest.raises(RuntimeError, match="short download"):
        _fetch("https://example.invalid/musan.tar.gz", dest)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("types, fetched", [([], False), (["white", "pink"], False),
                                            (["babble"], True), (["musan_ambient"], True)])
def test_musan_is_fetched_only_when_a_condition_uses_it(monkeypatch, types, fetched, tmp_path):
    from types import SimpleNamespace

    from fabench.noise import musan, provider

    calls = []
    monkeypatch.setattr(musan, "ensure_musan", lambda cfg: calls.append(1) or tmp_path)
    monkeypatch.setattr(musan, "list_files", lambda root, kind: [])
    cfg = SimpleNamespace(datasets={"noise": {"musan": {"enabled": True}}}, seeds={},
                          conditions_raw={"noise_types": types})
    provider.NoiseProvider.from_config(cfg)
    assert bool(calls) is fetched
