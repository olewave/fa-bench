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

"""TIMIT ingestion (Plan S1).

TIMIT gold: ``.PHN`` / ``.WRD`` hold ``start_sample end_sample label`` at 16 kHz
(divide by 16000 for seconds); ``.TXT`` holds the orthographic sentence. Hand-
corrected phone boundaries — the canonical English read-speech gold.
"""

from __future__ import annotations

from pathlib import Path

from fabench.audio import read_audio
from fabench.schema import Interval, Utterance

TIMIT_SR = 16000

# Standard core test set: 24 speakers (2M + 1F per dialect region), 192 utts.
CORE_TEST_SPEAKERS = {
    "mdab0", "mwbt0", "felc0",   # DR1
    "mtas1", "mwew0", "fpas0",   # DR2
    "mjmp0", "mlnt0", "fpkt0",   # DR3
    "mlll0", "mtls0", "fjlm0",   # DR4
    "mbpm0", "mklt0", "fnlp0",   # DR5
    "mcmj0", "mjdh0", "fmgd0",   # DR6
    "mgrt0", "mnjm0", "fdhc0",   # DR7
    "mjln0", "mpam0", "fmld0",   # DR8
}


def _parse_intervals(path: Path, sr: int = TIMIT_SR) -> list[Interval]:
    ivs: list[Interval] = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            s, e = int(parts[0]), int(parts[1])
            label = " ".join(parts[2:])
            ivs.append(Interval(label=label, start=s / sr, end=e / sr))
    return ivs


# TIMIT annotates each stop as a silent closure + a burst; Buckeye labels the
# whole stop as one phone. `merge_closures` makes TIMIT Buckeye-style: fold each
# closure into its following burst as a single [closure.start, burst.end] stop,
# so closures stop counting as silence phones (~14% of TIMIT phones otherwise).
_TIMIT_BURSTS = frozenset({"b", "d", "g", "p", "t", "k", "jh", "ch", "dx"})
# homorganic stop for each closure; also used to relabel an *orphan* closure
# (unreleased/co-articulated stop, no annotated burst) to the stop itself rather
# than leaving it as silence — so Buckeye-style TIMIT has no closure phones at all.
_TIMIT_CLOSURE_TO_STOP = {"bcl": "b", "dcl": "d", "gcl": "g", "pcl": "p", "tcl": "t", "kcl": "k"}
_TIMIT_CLOSURES = frozenset(_TIMIT_CLOSURE_TO_STOP)


def _merge_closures(phones: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    i = 0
    while i < len(phones):
        p = phones[i]
        nxt = phones[i + 1] if i + 1 < len(phones) else None
        if p.label in _TIMIT_CLOSURES and nxt is not None and nxt.label in _TIMIT_BURSTS:
            out.append(Interval(nxt.label, p.start, nxt.end, nxt.conf))  # closure+burst -> one stop
            i += 2
        elif p.label in _TIMIT_CLOSURES:
            out.append(Interval(_TIMIT_CLOSURE_TO_STOP[p.label], p.start, p.end, p.conf))  # orphan -> stop
            i += 1
        else:
            out.append(p)
            i += 1
    return out


def _find_audio(base: Path) -> Path | None:
    for ext in (".WAV", ".wav", ".WAV.wav", ".sph", ".SPH"):
        p = base.with_suffix(ext)
        if p.exists():
            return p
    # some distributions store *.WAV.wav (converted) alongside *.WAV (sphere)
    for cand in (base.parent.glob(base.name + ".*")):
        if cand.suffix.lower() in (".wav", ".sph"):
            return cand
    return None


def parse_utterance(phn: Path, *, split: str, dr: str, spk: str,
                    merge_closures: bool = False) -> Utterance:
    stem = phn.with_suffix("")
    phones = _parse_intervals(phn)
    if merge_closures:
        phones = _merge_closures(phones)
    wrd = stem.with_suffix(".WRD")
    if not wrd.exists():
        wrd = stem.with_suffix(".wrd")
    words = _parse_intervals(wrd) if wrd.exists() else []
    # words in TIMIT are lowercased tokens; normalize
    for w in words:
        w.label = w.label.lower()

    audio = _find_audio(stem)
    if audio is not None:
        try:
            x, sr = read_audio(audio)
            duration = len(x) / sr
        except Exception:
            duration = phones[-1].end if phones else 0.0
        audio_path = str(audio)
    else:
        duration = phones[-1].end if phones else 0.0
        audio_path = str(stem.with_suffix(".WAV"))

    sent = stem.name.lower()
    utt_id = f"timit_{split}_{dr.lower()}_{spk}_{sent}"
    return Utterance(
        utt_id=utt_id,
        source_corpus="timit",
        register="read",
        speaker_id=spk,
        audio_path=audio_path,
        sample_rate=TIMIT_SR,
        duration_s=duration,
        words=words,
        phones=phones,
    )


#: Splits live as data, not code: datasets/languages/en/timit/split/<subset>.list,
#: one "<speaker_id> <utterance_id>" per line.
#:
#: core_test.list is transcribed verbatim from the corpus's own
#: DOC/TESTSET.DOC Table 1. dev.list is Kaldi's egs/timit/s5/conf/dev_spk.list
#: -- a community convention TIMIT does not itself define. See
#: docs/literature_review.md.
#:
#: ALL FOUR EXCLUDE THE SA SENTENCES. DOC/TESTSET.DOC is explicit: "the 2 SA
#: sentences have been excluded from the core and complete test sets ... THESE
#: SENTENCES ARE INCLUDED ON THE CD-ROM, BUT SHOULD NOT BE USED FOR TRAINING
#: OR TEST PURPOSES." Every speaker reads both SA sentences, so they are
#: text-overlapped with training by construction.
from fabench.paths import split_dir as _splits_for


def _repo_root() -> Path:
    """Walk UP for the dir holding both ``fabench/`` and ``datasets/``.

    NOT a fixed ``parents[N]``: this file has already moved once
    (``fabench/dataprep/en/`` -> ``fabench/dataprep/datasets/en/``) and the
    extra level silently made ``parents[4]`` resolve to ``fabench/`` instead of
    the repo root, so the split list was not found and the ingest fell back to
    the whole corpus rather than the requested subset. Depth-counting breaks
    silently on any move; searching does not.
    """
    for d in Path(__file__).resolve().parents:
        if (d / "fabench").is_dir() and (d / "datasets").is_dir():
            return d
    raise RuntimeError("cannot locate repo root (needs fabench/ and datasets/)")


_SPLIT_DIR = _splits_for(_repo_root(), "en", "timit")

#: subset -> directories to scan. Membership comes from the .list file.
_SUBSETS = {
    "train":     ["TRAIN"],   # 462 spk, 3,696 utts
    "dev":       ["TEST"],    #  50 spk,   400 utts
    "core_test": ["TEST"],    #  24 spk,   192 utts
}
# NOT offered: TIMIT's complete 168-speaker test set. It is a strict SUPERSET
# of both `dev` (50 spk) and `core_test` (24 spk) -- verified against the split
# lists -- so a number on it is not independent of the set used to choose the
# configuration, and cannot be reported beside them as a third cell.


def _load_split(subset: str) -> set[str]:
    """Utterance ids for ``subset``, from datasets/languages/en/timit/split/<subset>.list."""
    path = _SPLIT_DIR / f"{subset}.list"
    if not path.is_file():
        raise FileNotFoundError(
            f"TIMIT split list {path} not found. The .list files define the "
            f"splits and are tracked in the repo; see datasets/languages/en/timit/split/."
        )
    return {ln.split()[1] for ln in path.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")}


def iter_utterances(root: Path, subset: str = "core_test", merge_closures: bool = False):
    """Yield Utterances from a TIMIT tree.

    ==========  =====  ===  ===============================================
    subset      utts   spk  note
    ==========  =====  ===  ===============================================
    train       3,696  462  all of TRAIN
    dev           400   50  Kaldi convention; TIMIT defines no dev set
    core_test     192   24  TIMIT's own core test, the standard set
    ==========  =====  ===  ===============================================

    TIMIT's full 168-speaker test set is deliberately absent: it contains all
    of `dev` and all of `core_test`, so it is not an independent third cell.

    Every subset excludes the 2 SA sentences, which TIMIT states must not be
    used for training or test. Membership is read from
    ``datasets/languages/en/timit/split/<subset>.list``, not hardcoded here.
    """
    root = Path(root)
    if subset not in _SUBSETS:
        raise ValueError(f"unknown TIMIT subset {subset!r}; "
                         f"choose from {sorted(_SUBSETS)}")
    split_dirs = _SUBSETS[subset]
    wanted = _load_split(subset)

    for split_dir in split_dirs:
        base = _resolve_split_dir(root, split_dir)
        if base is None:
            raise FileNotFoundError(
                f"TIMIT {split_dir}/ not found under {root}. Expected NIST layout "
                f"{root}/{split_dir}/DR1/<SPKR>/<sent>.PHN (or lowercase)."
            )
        for phn in sorted(base.rglob("*.PHN")) or sorted(base.rglob("*.phn")):
            dr = phn.parent.parent.name
            spk = phn.parent.name.lower()
            sent = phn.stem.lower()
            if f"timit_{split_dir.lower()}_{dr.lower()}_{spk}_{sent}" not in wanted:
                continue
            yield parse_utterance(phn, split=split_dir.lower(), dr=dr, spk=spk,
                                  merge_closures=merge_closures)


def _resolve_split_dir(root: Path, split_dir: str) -> Path | None:
    for cand in (
        root / split_dir,
        root / "TIMIT" / split_dir,
        root / split_dir.lower(),
        root / "data" / split_dir,
    ):
        if cand.is_dir():
            return cand
    # maybe root already IS the split dir
    if any(root.rglob("*.PHN")) or any(root.rglob("*.phn")):
        return root
    return None
