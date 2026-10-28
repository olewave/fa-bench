# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""The Kaldi data dirs ``fabench prepare`` writes, on synthetic corpora.

The published noise is drawn per wav.scp line in line order, so the format and
the order are what these tests pin. No licensed data is needed. The corpus
trees are empty files named from the tracked split lists, plus the
``buckeye_sample.phones`` fixture.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from fabench.dataprep.noisemix import datadirs, prepare

FIX = Path(__file__).resolve().parents[2] / "datasets" / "test" / "fixtures"
PIPE = '-ar 16000 -ac 1 -af "adelay=475,apad=pad_dur=0.475" -f wav - |'


def _timit(root: Path, subset: str) -> list[str]:
    """Stage every listed utterance as empty .PHN/.WAV files, plus an SA one."""
    ids = sorted(datadirs._split_column("timit", subset, 1))
    for uid in ids + [ids[0].rsplit("_", 1)[0] + "_sa1"]:
        _, portion, dr, spk, sent = uid.split("_")
        stem = root / portion.upper() / dr.upper() / spk.upper() / sent.upper()
        stem.parent.mkdir(parents=True, exist_ok=True)
        for ext in (".PHN", ".WAV"):
            stem.with_suffix(ext).touch()
    return ids


def test_timit_lines_follow_the_published_format_and_order(tmp_path):
    ids = _timit(tmp_path, "core_test")
    files = datadirs.timit(tmp_path, "core_test")
    utts = [ln.split("\t")[0] for ln in files["wav.scp"]]
    assert len(utts) == len(ids) == 192
    assert "_sa1" not in "".join(utts)
    # the published build sorted the .PHN path strings; ids sort the same way
    by_path = ["_".join(Path(p).with_suffix("").parts[-3:]).lower()
               for p in sorted(map(str, tmp_path.rglob("*.PHN"))) if "/SA" not in p]
    assert utts == by_path == sorted(utts)
    dr, spk, sent = utts[0].split("_")
    wav = tmp_path / "TEST" / dr.upper() / spk.upper() / f"{sent.upper()}.WAV"
    assert files["wav.scp"][0] == (f"{utts[0]}\tffmpeg -hide_banner -loglevel error "
                                   f"-i {wav} {PIPE}")
    assert files["utt2spk"] == files["reco2spk"] == [f"{u}\t{u.split('_')[1]}" for u in utts]


def test_timit_refuses_a_partial_corpus_or_an_unquotable_root(tmp_path):
    ids = _timit(tmp_path / "a", "core_test")
    _, portion, dr, spk, sent = ids[5].split("_")
    (tmp_path / "a" / portion.upper() / dr.upper() / spk.upper() / f"{sent.upper()}.PHN").unlink()
    with pytest.raises(FileNotFoundError, match="1 of 192"):
        datadirs.timit(tmp_path / "a", "core_test")
    _timit(tmp_path / "b c", "core_test")
    with pytest.raises(ValueError, match="shell quoting"):
        datadirs.timit(tmp_path / "b c", "core_test")


def test_buckeye_dirs_hold_each_recording_of_the_split_speakers(tmp_path):
    for rec in ("s0701a", "s0701b", "s0101a"):        # s07 is dev, s01 is train
        (tmp_path / rec[:3]).mkdir(exist_ok=True)
        (tmp_path / rec[:3] / f"{rec}.phones").write_text("#\n 1.0 121 SIL\n")
        (tmp_path / rec[:3] / f"{rec}.wav").touch()
    got = datadirs.write(tmp_path / "ref", "buckeye", "dev", tmp_path)
    d = tmp_path / "ref" / "data" / "golden" / "buckeye_dev"
    wavs = {r: tmp_path / "s07" / f"{r}.wav" for r in ("s0701a", "s0701b")}
    assert got == wavs
    assert (d / "wav.scp").read_text() == "".join(
        f"{r}\tffmpeg -hide_banner -loglevel error -i {w} {PIPE}\n" for r, w in wavs.items())
    assert (d / "reco2spk").read_text() == "s0701a\ts07\ns0701b\ts07\n"
    assert (d / "utt2spk").read_text() == "s0701a\ts07\ns0701b\ts07\n"
    assert not (d / "segments").exists()
    # a second copy of a recording, a shadow root built inside the corpus root
    # say, would be drawn twice
    (tmp_path / "out" / "s07").mkdir(parents=True)
    (tmp_path / "out" / "s07" / "s0701a.phones").write_text("#\n")
    (tmp_path / "out" / "s07" / "s0701a.wav").touch()
    with pytest.raises(ValueError, match="two copies of s0701a"):
        datadirs.buckeye(tmp_path, "dev")


def test_plan_gives_each_corpus_the_subsets_it_has():
    cfg = SimpleNamespace(datasets={"gold": {"timit": {"subset": "core_test"},
                                             "buckeye": {"subset": "dev"}}})
    both = ["timit", "buckeye"]
    assert prepare._plan(cfg, both, None) == [("timit", "core_test"), ("buckeye", "dev")]
    assert prepare._plan(cfg, both, ["core_test", "test"]) == [("timit", "core_test"),
                                                               ("buckeye", "test")]
    assert prepare._plan(cfg, ["timit"], ["dev"]) == [("timit", "dev")]
    with pytest.raises(SystemExit, match="timit has none of test"):
        prepare._plan(cfg, ["timit"], ["test"])
    with pytest.raises(SystemExit, match="no requested corpus has subset test"):
        prepare._plan(cfg, ["timit"], ["dev", "test"])


def test_prepare_refuses_a_directory_that_is_not_empty(tmp_path):
    (tmp_path / "stale.wav").touch()
    args = Namespace(config=None, out=str(tmp_path), corpus="timit", subset=None,
                     conditions="noise", jobs=1, musan=None, rirs=None, wav_reverberate=None)
    with pytest.raises(SystemExit, match="not empty"):
        prepare.cmd_prepare(args)
