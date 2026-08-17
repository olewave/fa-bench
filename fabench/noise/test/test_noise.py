# Copyright 2026  Olewave, LLC

# See LICENSE at the repository root for the full terms
#
# Licensed under the PolyForm Noncommercial License 1.0.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Noncommercial use is permitted -- research, teaching, personal study, and work
# by charitable, educational, public-safety, environmental and government
# organisations. Any commercial use requires a separate licence from Olewave, LLC.
#
# AS FAR AS THE LAW ALLOWS, THE SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR
# CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING
# OUT OF THESE TERMS OR THE USE OR NATURE OF THE SOFTWARE, UNDER ANY KIND OF
# LEGAL CLAIM.

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
# musan cache: the final musan/ dir must only ever appear complete
# --------------------------------------------------------------------------
def _musan_tar(tmp_path, name, kinds):
    import tarfile

    src = tmp_path / f"src_{name}" / "musan"
    for k in kinds:
        (src / k).mkdir(parents=True)
        (src / k / f"{k}0.wav").write_bytes(b"RIFF")
    tarball = tmp_path / f"{name}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(src, arcname="musan")
    return tarball


def test_musan_extract_is_atomic(tmp_path):
    from fabench.noise.musan import _extract

    # an archive missing a corpus kind is refused, and NOTHING lands at
    # cache/musan — ensure_musan takes that path's existence as "fetched"
    cache = tmp_path / "cache1"
    cache.mkdir()
    with pytest.raises(RuntimeError, match="incomplete"):
        _extract(_musan_tar(tmp_path, "partial", ["noise"]), cache)
    assert not (cache / "musan").exists()

    # a truncated tarball raises out cleanly, same guarantee
    good = _musan_tar(tmp_path, "good", ["noise", "speech", "music"])
    trunc = tmp_path / "trunc.tar.gz"
    trunc.write_bytes(good.read_bytes()[: good.stat().st_size // 2])
    cache2 = tmp_path / "cache2"
    cache2.mkdir()
    with pytest.raises(Exception):  # noqa: B017  the mixer raises bare Exception here by design
        _extract(trunc, cache2)
    assert not (cache2 / "musan").exists()

    # the complete archive lands with all three kinds in place
    cache3 = tmp_path / "cache3"
    cache3.mkdir()
    _extract(good, cache3)
    assert all((cache3 / "musan" / k).is_dir() for k in ("noise", "speech", "music"))
