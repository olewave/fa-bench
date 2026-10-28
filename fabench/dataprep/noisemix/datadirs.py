# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Write the Kaldi data dirs ``make_noisy.py --ref`` reads.

``make_noisy.py`` draws its noise per ``wav.scp`` line, in line order, so
these files are part of the seed. This module writes them from the tracked
split lists and a staged corpus, in the format the published conditions were
built from::

    <ref>/data/golden/<split>/wav.scp    <id>\\t<ffmpeg pipe> |
    <ref>/data/golden/<split>/utt2spk    <utt>\\t<speaker>
    <ref>/data/golden/<split>/reco2spk   <recording>\\t<speaker>

TIMIT has one line per utterance (``dr1_felc0_si1386``), every utterance of
the split list. Buckeye has one line per recording (``s0701a``), every
recording of the split's speakers, and its utterances are the whole
recordings, because the noise is drawn and mixed per recording. Every file is
sorted. Each source goes through ``ffmpeg ... -af "adelay=475,apad=..."``,
which pads 475 ms at both ends, and ``shadow_root.py`` takes the pad off again.

"""

from __future__ import annotations

import shlex
from pathlib import Path

from fabench.dataprep.datasets.en.timit.processor import _find_audio, _resolve_split_dir
from fabench.paths import split_dir

PAD = '-af "adelay=475,apad=pad_dur=0.475"'
_REPO = Path(__file__).resolve().parents[3]


def subsets(corpus: str) -> list[str]:
    """The subsets a corpus has, one per tracked ``split/<subset>.list``."""
    return sorted(p.stem for p in split_dir(_REPO, "en", corpus).glob("*.list"))


def _split_column(corpus: str, subset: str, col: int) -> set[str]:
    path = split_dir(_REPO, "en", corpus) / f"{subset}.list"
    if not path.is_file():
        raise FileNotFoundError(f"no split list {path}")
    return {ln.split()[col] for ln in path.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")}


def _pipe(path: Path) -> str:
    # The command goes to a shell unquoted, as the published wav.scp had it.
    if shlex.quote(str(path)) != str(path):
        raise ValueError(f"{path}: the corpus path must not need shell quoting "
                         "(no spaces or shell characters)")
    return f"ffmpeg -hide_banner -loglevel error -i {path} -ar 16000 -ac 1 {PAD} -f wav - |"


def timit(root: Path, subset: str) -> dict[str, list[str]]:
    """One line per utterance of ``split/<subset>.list``."""
    want = _split_column("timit", subset, 1)          # timit_test_dr1_felc0_si1386
    phn: dict[str, Path] = {}
    for portion in sorted({w.split("_")[1] for w in want}):
        base = _resolve_split_dir(root, portion.upper())
        if base is None:
            raise FileNotFoundError(f"TIMIT {portion.upper()}/ not found under {root}")
        for p in base.rglob("*"):
            if p.suffix.upper() == ".PHN":
                uid = f"timit_{portion}_{p.parent.parent.name}_{p.parent.name}_{p.stem}".lower()
                if uid in want:
                    phn[uid] = p
    gone = want - phn.keys()
    if gone:
        raise FileNotFoundError(f"TIMIT {subset}: {len(gone)} of {len(want)} listed "
                                f"utterances not under {root}, e.g. {min(gone)}")
    wav, spk = [], []
    for uid in sorted(want, key=lambda u: u.split("_", 2)[2]):
        utt = uid.split("_", 2)[2]                   # dr1_felc0_si1386
        audio = _find_audio(phn[uid].with_suffix(""))
        if audio is None:
            raise FileNotFoundError(f"no audio beside {phn[uid]}")
        wav.append(f"{utt}\t{_pipe(audio)}")
        spk.append(f"{utt}\t{utt.split('_')[1]}")
    return {"wav.scp": wav, "utt2spk": spk, "reco2spk": spk}


def buckeye(root: Path, subset: str) -> dict[str, list[str]]:
    """One line per recording of the split's speakers, each its own utterance."""
    speakers = _split_column("buckeye", subset, 0)
    wav, spk, seen = [], [], {}
    for ph in sorted(root.rglob("*.phones")):
        rec = ph.stem                                  # s0701a, speaker s07
        if rec[:3] not in speakers:
            continue
        if rec in seen:           # e.g. a shadow root built inside the corpus root
            raise ValueError(f"two copies of {rec} under {root}, {seen[rec]} and {ph}")
        seen[rec] = ph
        audio = ph.with_suffix(".wav")
        if not audio.is_file():
            raise FileNotFoundError(f"no audio beside {ph}")
        wav.append(f"{rec}\t{_pipe(audio)}")
        spk.append(f"{rec}\t{rec[:3]}")
    if not wav:
        raise FileNotFoundError(f"no Buckeye recordings of {sorted(speakers)} under {root}")
    return {"wav.scp": sorted(wav), "utt2spk": sorted(spk), "reco2spk": sorted(spk)}


def write(ref: Path, corpus: str, subset: str, root: Path) -> dict[str, Path]:
    """Write ``<ref>/data/golden/<corpus>_<subset>/``; return ``{wav.scp id: source audio}``."""
    files = (timit if corpus == "timit" else buckeye)(Path(root).absolute(), subset)
    d = Path(ref) / "data" / "golden" / f"{corpus}_{subset}"
    d.mkdir(parents=True, exist_ok=True)
    for name, lines in files.items():
        (d / name).write_text("".join(f"{ln}\n" for ln in lines))
    return {ln.split("\t", 1)[0]: Path(ln.split(" -i ", 1)[1].split(" ", 1)[0])
            for ln in files["wav.scp"]}
