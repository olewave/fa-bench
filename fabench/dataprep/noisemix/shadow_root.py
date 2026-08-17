#!/usr/bin/env python3
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

"""Build a *shadow corpus root*: clean gold, noisy audio, all symlinks.

WHY THIS AND NOT A NEW MANIFEST PATH. FA-Bench's ``conditions`` machinery
mixes noise ON THE FLY (``fabench/noise/mixer.py`` -> ``build_manifest``
writes its own wavs). That is a different noise from the Kaldi conditions
built by ``make_noisy.py``, and there is no ``audio_root`` override to point
an eval at pre-built audio.

The cheapest correct route is to leave every code path alone and hand the
existing processors a root that LOOKS like the corpus but whose audio is the
noisy version:

    <shadow>/TRAIN/DR1/FCJF0/SA1.PHN  -> symlink to the real TIMIT gold
    <shadow>/TRAIN/DR1/FCJF0/SA1.wav  -> symlink to noisy/<type>/<utt>.wav

Ingest, utterance slicing, split lists and gold all then work unmodified, and
a config only changes ``root:``. This works because the noise pipeline
preserves duration to the millisecond, so the clean gold stays valid.

Two layout problems it solves, which is the whole reason it exists:

* TIMIT noisy files are FLAT (``noisy/<type>/dr1_felc0_si1386.wav``) while the
  processor wants ``TRAIN/DR1/FCJF0/SA1.WAV``. The utt-id encodes the path, so
  the mapping is recoverable.
* Buckeye noisy audio is per-RECORDING, but FA-Bench evaluates per-UTTERANCE
  slices that its processor cuts from the recording. Pointing the shadow at
  noisy recordings makes that slicing produce noisy utterances for free --
  no re-slicing code, and the segment boundaries are by construction the same.

Usage:
    shadow_root.py --corpus timit   --type noise --out <dir>
    shadow_root.py --corpus buckeye --type babble --out <dir>
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Machine-specific roots come from the environment (see evals/gen_config.py).
NOISY_ROOT = os.environ.get("FABENCH_NOISY_ROOT", "data/noisy")
CLEAN = {"timit": os.environ.get("FABENCH_TIMIT_ROOT", f"{NOISY_ROOT}/TIMIT"),
         "buckeye": os.environ.get("FABENCH_BUCKEYE_ROOT", "data/buckeye")}
TYPES = ("reverb", "noise", "music", "babble")


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.symlink_to(src)


#: seconds of silence the gold-prep recipe's wav.scp prepends (`-af "adelay=475,..."`).
PAD_HEAD_S = 0.475


def _trim_audio(src: Path, dst: Path, head_s: float = PAD_HEAD_S) -> bool:
    """Copy `src` to `dst` with the leading pad removed.

    THE NOISY AUDIO IS ON A DIFFERENT TIMELINE FROM FA-Bench's GOLD, and a
    symlink would silently score every boundary `head_s` late.

    make_noisy.py reuses the gold-prep recipe's wav.scp, which applies
    `-af "adelay=475,apad=pad_dur=0.475"`. That is correct for that recipe,
    whose gold was annotated against the padded audio. FA-Bench's gold comes
    from TIMIT `.PHN` / Buckeye `.phones`, which are on the UNPADDED timeline.
    Measured: TIMIT source 5.523 s vs noisy 6.473 s (+0.950 = 475 head + 475
    tail); a Buckeye noisy slice began with 450 ms of silence the aligner
    dutifully labelled `[sil]`.

    Cross-correlating the raw source against the trimmed noisy file gives a
    best lag of 0 samples, so trimming the head restores sample-exact
    alignment. The tail pad is left alone -- it extends past the last boundary
    and costs nothing.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return True
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
         "-af", f"atrim=start={head_s},asetpts=PTS-STARTPTS",
         "-ar", "16000", "-ac", "1", str(dst)],
        capture_output=True, text=True, check=False)
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 0


def _run_trims(jobs: list[tuple[Path, Path]], nj: int = 16) -> None:
    """Trim every queued file. ffmpeg is the bottleneck, so run nj at a time."""
    if not jobs:
        return
    bad = 0
    with ThreadPoolExecutor(max_workers=nj) as ex:
        for ok in ex.map(lambda j: _trim_audio(*j), jobs):
            bad += 0 if ok else 1
    print(f"   trimmed {len(jobs) - bad}/{len(jobs)} (head {PAD_HEAD_S}s removed)"
          + (f", {bad} FAILED" if bad else ""))


def timit(clean: Path, noisy: Path, out: Path) -> tuple[int, int, int]:
    """utt-id ``dr1_felc0_si1386`` <-> ``<split>/DR1/FELC0/SI1386.*``."""
    linked = missing = excluded = 0
    jobs: list[tuple[Path, Path]] = []
    for phn in sorted(clean.rglob("*.PHN")) or sorted(clean.rglob("*.phn")):
        rel = phn.relative_to(clean)              # TRAIN/DR1/FCJF0/SA1.PHN
        parts = rel.parts
        if len(parts) < 4:
            continue
        _split, dr, spk, fname = parts[0], parts[1], parts[2], parts[-1]
        stem = Path(fname).stem
        utt = f"{dr}_{spk}_{stem}".lower()
        wav = noisy / f"{utt}.wav"
        if not wav.is_file():
            # SA sentences are EXPECTED to be absent, not a gap: TIMIT states
            # the 2 SA prompts per speaker must not be used for training or
            # test, FA-Bench's splits exclude them, so the noise build never
            # saw them. 630 speakers x 2 = exactly 1260.
            if stem.upper().startswith("SA"):
                excluded += 1
            else:
                missing += 1
            continue
        # gold + transcript come from the REAL corpus (symlink, free); audio is
        # TRIMMED, not symlinked -- see _trim_audio for why a symlink is wrong.
        for ext in (".PHN", ".WRD", ".TXT", ".phn", ".wrd", ".txt"):
            s = phn.with_suffix(ext)
            if s.is_file():
                _link(s, out / rel.with_suffix(ext))
        jobs.append((wav, out / rel.with_suffix(".wav")))
        linked += 1
    _run_trims(jobs)
    return linked, missing, excluded


def buckeye(clean: Path, noisy: Path, out: Path) -> tuple[int, int, int]:
    """Per-recording: link .phones/.words from clean, .wav from noisy."""
    linked = missing = 0
    jobs: list[tuple[Path, Path]] = []
    for ph in sorted(clean.rglob("*.phones")):
        rel = ph.relative_to(clean)
        rec = ph.stem
        wav = noisy / f"{rec}.wav"
        if not wav.is_file():
            missing += 1
            continue
        for ext in (".phones", ".words", ".txt", ".log"):
            s = ph.with_suffix(ext)
            if s.is_file():
                _link(s, out / rel.with_suffix(ext))
        jobs.append((wav, out / rel.with_suffix(".wav")))
        linked += 1
    _run_trims(jobs)
    return linked, missing, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", required=True, choices=("timit", "buckeye"))
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clean", default=None, help="override the clean root")
    ap.add_argument("--noisy-root", default=NOISY_ROOT)
    a = ap.parse_args(argv)

    corp_dir = "TIMIT" if a.corpus == "timit" else "Buckeye"
    clean = Path(a.clean or CLEAN[a.corpus])
    noisy = Path(a.noisy_root) / corp_dir / "noisy" / a.type
    out = Path(a.out)
    for p, what in ((clean, "clean root"), (noisy, "noisy dir")):
        if not p.is_dir():
            print(f"  no {what} at {p}", file=sys.stderr)
            return 1

    fn = timit if a.corpus == "timit" else buckeye
    linked, missing, excluded = fn(clean, noisy, out)
    print(f"  {a.corpus}/{a.type}: {linked} linked"
          + (f", {excluded} SA excluded (expected)" if excluded else "")
          + (f", {missing} MISSING" if missing else ""))
    return 0 if linked and not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
