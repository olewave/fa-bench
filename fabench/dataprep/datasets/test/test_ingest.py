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

"""S1 ingestion: parsers on synthetic fixtures, SPHERE I/O, guards.

No restricted corpora are needed — fixtures reproduce each corpus's native
format so the parsers are verified data-independently.
"""

from pathlib import Path

import numpy as np
import pytest

from fabench.normalize import make_canon
from fabench.schema import validate_utterance

FIX = Path(__file__).resolve().parent / "fixtures"


# --------------------------------------------------------------------------
# TIMIT
# --------------------------------------------------------------------------
def test_timit_phn_sample_to_seconds():
    from fabench.dataprep.datasets.en.timit import _parse_intervals

    ivs = _parse_intervals(FIX / "timit_sample.PHN")
    assert ivs[0].label == "h#"
    assert ivs[1].label == "sh"
    # 2000 samples / 16000 = 0.125 s
    assert ivs[1].start == pytest.approx(0.125)
    assert ivs[1].end == pytest.approx(0.25)
    # last end 16000 -> 1.0 s
    assert ivs[-1].end == pytest.approx(1.0)


def test_timit_parse_utterance_and_validate(tmp_path):
    from fabench.dataprep.datasets.en.timit import parse_utterance

    # copy fixture PHN/WRD next to a fake stem
    stem = tmp_path / "SA1"
    (stem.with_suffix(".PHN")).write_text((FIX / "timit_sample.PHN").read_text())
    (stem.with_suffix(".WRD")).write_text((FIX / "timit_sample.WRD").read_text())
    u = parse_utterance(stem.with_suffix(".PHN"), split="test", dr="DR1", spk="mdab0")
    assert u.utt_id == "timit_test_dr1_mdab0_sa1"
    assert u.source_corpus == "timit" and u.register == "read"
    assert [w.label for w in u.words] == ["she", "had"]
    # phones tile [0,1]; validate structure (TIMIT: no gaps)
    u.duration_s = 1.0
    rep = validate_utterance(u, require_phone_no_gaps=True)
    assert rep.ok, rep.errors


def test_timit_glottal_stop_folds_to_delete():
    # 'q' in the fixture must canonicalize to DELETE (dropped by folding)
    from fabench.normalize import DELETE

    canon = make_canon("timit")
    assert canon("q") == DELETE


def test_timit_subsets_never_include_sa(tmp_path):
    """EVERY subset excludes the 2 SA sentences -- TIMIT states they must not be
    used for training or test.

    This invariant is why ``subset='all'`` was removed: it was the one subset
    that pulled SA in (630 spk x 10 = 6,300, against 630 x 8 = 5,040 without).
    Membership now comes from datasets/languages/en/timit/split/<subset>.list and no list
    carries an SA id, so an unknown subset must fail loudly rather than
    silently ingesting everything.
    """
    import pytest

    from fabench.dataprep.datasets.en.timit import iter_utterances
    from fabench.dataprep.datasets.en.timit.processor import _SPLIT_DIR

    phn = "0 8000 h#\n8000 16000 iy\n"

    def mk(rel):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(phn)

    def first_id(subset):
        """A REAL utt id from the split list -- membership is list-driven, so a
        synthetic id would simply never be ingested and prove nothing."""
        for ln in (_SPLIT_DIR / f"{subset}.list").read_text().splitlines():
            if ln.strip() and not ln.startswith("#"):
                return ln.split()[1]
        raise AssertionError(f"{subset}.list is empty")

    # utt_id timit_<split>_<dr>_<spk>_<sent> -> <SPLIT>/<DR>/<SPK>/<SENT>.PHN
    def stage(utt_id):
        _, split, dr, spk, sent = utt_id.split("_")
        mk(f"{split.upper()}/{dr.upper()}/{spk}/{sent.upper()}.PHN")
        return spk, sent

    core_id, train_id = first_id("core_test"), first_id("train")
    core_spk, _ = stage(core_id)
    stage(train_id)
    # An SA sentence for a real, in-list speaker: on disk, never in any list.
    mk(f"TEST/DR7/{core_spk}/SA1.PHN")

    for subset in ("core_test", "dev", "train"):
        bad = [u.utt_id for u in iter_utterances(tmp_path, subset=subset)
               if "_sa" in u.utt_id]
        assert not bad, f"subset={subset!r} ingested SA sentences: {bad}"

    # no list carries an SA id in the first place -- the invariant at the source
    for lst in sorted(_SPLIT_DIR.glob("*.list")):
        ids = [ln.split()[1] for ln in lst.read_text().splitlines()
               if ln.strip() and not ln.startswith("#")]
        assert not [i for i in ids if "_sa" in i], f"{lst.name} carries an SA id"

    assert [u.utt_id for u in iter_utterances(tmp_path, subset="core_test")] == [core_id]
    assert [u.utt_id for u in iter_utterances(tmp_path, subset="train")] == [train_id]

    with pytest.raises(ValueError, match="unknown TIMIT subset"):
        list(iter_utterances(tmp_path, subset="all"))


# --------------------------------------------------------------------------
# Buckeye
# --------------------------------------------------------------------------
def test_buckeye_cumulative_parse():
    from fabench.dataprep.datasets.en.buckeye import parse_tier

    ivs = parse_tier(FIX / "buckeye_sample.phones")
    labels = {iv.label: (iv.start, iv.end) for iv in ivs}
    assert labels["dh"] == pytest.approx((0.1, 0.25))
    assert labels["ah"] == pytest.approx((0.25, 0.4))
    assert labels["k"] == pytest.approx((0.55, 0.7))


def test_buckeye_word_label_strips_annotation():
    from fabench.dataprep.datasets.en.buckeye import parse_tier

    words = parse_tier(FIX / "buckeye_sample.words")
    labs = [w.label for w in words]
    assert "the" in labs and "cat" in labs  # ';'-annotations stripped
    assert "<SIL>" in labs


def test_buckeye_segmentation_splits_at_breaks():
    from fabench.dataprep.datasets.en.buckeye import parse_tier, segment_track

    words = parse_tier(FIX / "buckeye_sample.words")
    phones = parse_tier(FIX / "buckeye_sample.phones")
    # relaxed thresholds to exercise the splitter on the tiny fixture
    chunks = segment_track(words, phones, min_chunk_s=0.2, min_phones=1)
    assert len(chunks) == 2  # "the" and "cat"
    (_t0, _t1, cw, _cp) = chunks[0]
    assert [w.label for w in cw] == ["the"]
    # rebased to chunk start
    assert cw[0].start == pytest.approx(0.0)
    # default thresholds drop these sub-0.5s chunks
    assert segment_track(words, phones) == []


def test_buckeye_paper_segmentation():
    """Paper protocol (arXiv:2606.18466): split at >=300ms silence and at every
    non-silence break (IVER); keep <300ms silences internal; pad +/-200ms into
    real silence; drop utts with <4 words or any cutoff/excised/unknown word."""
    from fabench.dataprep.datasets.en.buckeye import segment_track_paper
    from fabench.schema import Interval as I

    phones = [
        I("SIL", 0.00, 0.50),   # leading silence (paddable, >=300ms)
        I("dh", 0.50, 0.60), I("ah", 0.60, 0.70),
        I("SIL", 0.70, 0.75),   # 50ms internal pause -> kept in utterance
        I("k", 0.75, 0.85), I("ae", 0.85, 0.95), I("t", 0.95, 1.05),
        I("s", 1.05, 1.15), I("ae", 1.15, 1.25), I("t", 1.25, 1.35),
        I("d", 1.35, 1.45), I("aw", 1.45, 1.55), I("n", 1.55, 1.65),
        I("SIL", 1.65, 2.10),   # 450ms silence -> split (paddable)
        I("hh", 2.10, 2.20), I("ay", 2.20, 2.30),      # utt "hi": 1 word -> dropped
        I("IVER", 2.30, 3.00),  # interviewer -> hard break, NOT paddable
        I("ay", 3.00, 3.10), I("k", 3.10, 3.20), I("ae", 3.20, 3.30),
        I("n", 3.30, 3.40), I("t", 3.40, 3.50),        # utt with cutoff -> dropped
        I("SIL", 3.50, 3.90),
    ]
    words = [
        I("the", 0.50, 0.70), I("cat", 0.75, 1.05),
        I("sat", 1.05, 1.35), I("down", 1.35, 1.65),
        I("hi", 2.10, 2.30),
        I("<IVER>", 2.30, 3.00),
        I("i", 3.00, 3.10), I("<CUTOFF-cant>", 3.10, 3.50),
    ]
    segs = segment_track_paper(words, phones, track_end=3.90)
    assert len(segs) == 1                       # only "the cat sat down" survives
    t0, t1, cw, cp = segs[0]
    assert t0 == pytest.approx(0.30)            # 200ms pad into the 500ms lead silence
    assert t1 == pytest.approx(1.85)            # 200ms pad into the 450ms trailing silence
    assert [w.label for w in cw] == ["the", "cat", "sat", "down"]
    assert cw[0].start == pytest.approx(0.20)   # rebased to padded origin (0.50-0.30)
    assert cp[0].label == "dh" and cp[0].start == pytest.approx(0.20)
    assert any(p.label == "!sil" for p in cp)   # internal 50ms silence,
    #                                        renamed to the kaldi swbd word form


def test_buckeye_paper_skips_slices_past_short_audio(tmp_path):
    """Some Buckeye tracks (e.g. s1901b) have audio shorter than their labels;
    utterances past the audio must be skipped, not written as empty slices that
    crash batch aligners (MAPS preemphasis / BFA chopping)."""
    import soundfile as sf

    from fabench.dataprep.datasets.en.buckeye import iter_utterances

    d = tmp_path / "s19"
    d.mkdir(parents=True)
    # 0.7 s of audio, but labels run to 1.4 s (0.7 s of annotation past the WAV)
    sf.write(str(d / "s1901b.wav"), np.zeros(int(0.7 * 16000), dtype="float32"), 16000)
    (d / "s1901b.phones").write_text(
        "#\n"
        "0.10 122 dh\n0.20 122 ah\n0.30 122 k\n0.40 122 ae\n0.50 122 t\n"
        "0.90 122 SIL\n"                                   # >=300ms split
        "1.00 122 ae\n1.10 122 n\n1.20 122 d\n1.30 122 hh\n1.40 122 iy\n"
    )
    (d / "s1901b.words").write_text(
        "#\n"
        "0.15 122 the\n0.28 122 cat\n0.40 122 sat\n0.50 122 down\n"
        "0.90 122 <SIL>\n"
        "1.05 122 and\n1.15 122 then\n1.28 122 i\n1.40 122 went\n"
    )
    utts = list(iter_utterances(tmp_path, tmp_path / "work", protocol="paper"))
    # the second utterance is entirely past the 0.7 s audio -> dropped
    assert len(utts) == 1
    # every written slice has real samples (no 44-byte header-only WAVs)
    # buckeye_audio__<root-digest>, not a flat buckeye_audio: the directory is
    # keyed by source root so a noisy shadow-root ingest cannot overwrite the
    # clean slices. Glob the prefix rather than pinning the digest.
    slices = [w for d in (tmp_path / "work").glob("buckeye_audio*")
              for w in d.glob("*.wav")]
    assert len(slices) == 1
    assert sf.info(str(slices[0])).frames >= int(0.1 * 16000)


# --------------------------------------------------------------------------
# SPHERE audio round-trip
# --------------------------------------------------------------------------
def test_sphere_roundtrip(tmp_path):
    from fabench.audio import read_audio, write_sphere_pcm

    sr = 16000
    t = np.arange(sr) / sr
    x = 0.3 * np.sin(2 * np.pi * 220 * t)
    p = tmp_path / "a.WAV"
    write_sphere_pcm(p, x, sr)
    y, sr2 = read_audio(p)
    assert sr2 == sr
    assert len(y) == len(x)
    assert np.max(np.abs(y - x)) < 1e-3  # 16-bit quantization


# --------------------------------------------------------------------------
# plausibility proxy
# --------------------------------------------------------------------------
def test_plausibility_detects_silence_to_speech():
    from fabench.dataprep.datasets.plausibility import plausibility
    from fabench.schema import Interval, Utterance

    sr = 16000
    # 0.3s silence, 0.4s tone, 0.3s silence
    x = np.concatenate([
        np.zeros(int(0.3 * sr)),
        0.3 * np.sin(2 * np.pi * 300 * np.arange(int(0.4 * sr)) / sr),
        np.zeros(int(0.3 * sr)),
    ])
    phones = [
        Interval("sil", 0.0, 0.3),
        Interval("s", 0.3, 0.7),   # speech onset at 0.3, offset at 0.7
        Interval("sil", 0.7, 1.0),
    ]
    u = Utterance("u", "toy", "read", "s", "x", sr, 1.0, phones=phones)
    pl = plausibility(u, x, sr, lambda l: "sil" if l == "sil" else "s")
    assert pl["n_sil_boundaries"] == 2
    assert pl["mean_step_at_sil_db"] > pl["mean_step_random_db"]
    assert pl["plausible"] is True


# --------------------------------------------------------------------------
# fail-loud + excluded-gold guard
# --------------------------------------------------------------------------
def test_ingest_not_staged_fails_loud(tmp_path, monkeypatch):
    from fabench.config import corpus_root_env, load_config
    from fabench.dataprep.datasets import ingest_corpus

    # "Not staged" has to be arranged, not assumed. The composed defaults read
    # FABENCH_<CORPUS>_ROOT, which `fabench init` now writes and the CLI loads
    # before spawning this suite -- so on a machine that HAS TIMIT this test
    # passed under plain pytest and failed under `fabench gates`.
    monkeypatch.delenv(corpus_root_env("timit"), raising=False)
    cfg = load_config()
    with pytest.raises(FileNotFoundError) as e:
        ingest_corpus("timit", cfg, use_cache=False)
    assert "not staged" in str(e.value) and "LDC" in str(e.value)


def test_excluded_gold_root_aborts(tmp_path):
    from fabench.config import Config
    from fabench.dataprep.datasets import ingest_corpus

    # craft a config pointing timit gold at a LibriTTS path
    bad = tmp_path / "LibriTTS-R"
    bad.mkdir()
    cfg = Config(
        raw={
            "datasets": {
                "gold": {"timit": {"enabled": True, "root": str(bad)}},
                "excluded_as_gold": ["libritts", "librispeech-alignments"],
            },
            "paths": {"work_dir": str(tmp_path / "work")},
        },
        path=tmp_path / "cfg.yaml",
    )
    with pytest.raises(ValueError) as e:
        ingest_corpus("timit", cfg, use_cache=False)
    assert "banned" in str(e.value) or "invalid as ground truth" in str(e.value)


def test_merge_closures_timit_buckeye_style():
    """Buckeye-style TIMIT: closure+burst -> one stop; orphan closure -> stop
    (not silence)."""
    from fabench.dataprep.datasets.en.timit import _merge_closures
    from fabench.schema import Interval
    ph = [Interval("h#", 0.0, 0.10), Interval("tcl", 0.10, 0.20), Interval("t", 0.20, 0.22),
          Interval("iy", 0.22, 0.30), Interval("kcl", 0.30, 0.40), Interval("h#", 0.40, 0.50)]
    out = _merge_closures(ph)
    assert [p.label for p in out] == ["h#", "t", "iy", "k", "h#"]  # tcl+t merged; orphan kcl->k
    stop_t = out[1]
    assert stop_t.start == 0.10 and abs(stop_t.end - 0.22) < 1e-9  # spans closure->burst
    assert out[3].start == 0.30 and abs(out[3].end - 0.40) < 1e-9  # orphan keeps its span


def test_variant_tag_distinguishes_merge_closures():
    """The ingest cache tag must differ for Buckeye-style TIMIT, else the merged
    and standard gold collide in the cache (regression)."""
    from fabench.dataprep.datasets import _variant_tag
    std = _variant_tag("timit", {"subset": "core_test"})
    bk = _variant_tag("timit", {"subset": "core_test", "merge_closures": True})
    assert std != bk and "mergeclosures" in bk
