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

"""Build the four Kaldi noise conditions for TIMIT and Buckeye.

Python port of ``make_noisy.sh``, which is kept alongside it. The two are
verified to produce byte-identical audio (see ``## Equivalence`` below); the
shell version stays as the reference this was checked against.

Follows Kaldi's ``egs/voxceleb/v2/run.sh`` exactly -- same scripts, same
parameters -- so these conditions match what the field trains on rather than an
invented SNR sweep
(https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh):

    reverb   simulated RIRs 0.5 smallroom + 0.5 mediumroom, rvb-prob 1,
             pointsource/isotropic noise probability 0  (reverb ONLY)
    noise    MUSAN noise,  --fg-interval 1  --fg-snrs 15:10:5:0
    music    MUSAN music,  --bg-snrs 15:10:8:5      --num-bg-noises 1
    babble   MUSAN speech, --bg-snrs 20:17:15:13    --num-bg-noises 3:4:5:6:7

REUSES the kaldi data dirs the gold-prep recipe already built
(``<recipe>/data/golden/<split>``), because their wav.scp already encodes
the exact ffmpeg pipeline -- including the ``adelay`` pad -- that produced the
audio the GOLD ALIGNMENTS were made against. Rebuilding them here would risk a
different pad and silently shift every boundary.

Output: real .wav files under
``/scratch/data/speech/english/{TIMIT,Buckeye}/noisy/<type>/<utt_id>.wav``
so the existing split lists index them unchanged.

## Equivalence with make_noisy.sh

Determinism is what makes the comparison meaningful: kaldi's
``augment_data_dir.py`` and ``reverberate_data_dir.py`` both call
``random.seed(args.random_seed)`` with ``default=123``, so the SNR and
noise-file choices are fixed. Two runs of the same recipe must therefore emit
byte-identical ``wav.scp`` commands and byte-identical audio.

Three shell behaviours are load-bearing and are reproduced exactly:

* ``sed 's/\\t/ /'`` replaces only the FIRST tab per line (no ``/g``). The
  gold-prep recipe writes ``f"{utt}\\t{cmd}"`` and the command itself may
  contain tabs; a global replace would corrupt it.
* ``set -uo pipefail`` WITHOUT ``-e`` -- a failing split must not abort the
  remaining splits.
* Success is judged by ``wav.scp`` being non-empty, NOT by exit code (see the
  fix_data_dir note in ``_augment``).

## One deliberate difference: where path.sh is sourced

The shell sourced ``path.sh`` before ``cd "$STAGE"``. ``path.sh`` ends with

    for _d in steps utils; do [ -e "$_d" ] || ln -sfn $KALDI_ROOT/egs/wsj/s5/$_d "$_d"; done

so it created ``steps`` and ``utils`` symlinks into pkaldi in whatever
directory the script was invoked from -- normally the FA-Bench repo root. That
is how a ``fa-bench/utils -> pkaldi/egs/wsj/s5/utils`` symlink appeared and
silently swallowed a later ``git mv`` into it. This port cds to the stage
FIRST, so the symlinks land in the stage where they are wanted. The audio is
unaffected; only the stray links are.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TYPES = ("reverb", "noise", "music", "babble")
DEFAULT_SPLITS = (
    "timit_train timit_dev timit_core_test "        # no full_test: removed as a
                                                    # strict superset of dev+core_test
    "buckeye_train buckeye_dev buckeye_test"
)
HERE = Path(__file__).resolve().parent


def env_defaults() -> argparse.Namespace:
    """Same knobs, same names, same precedence as the shell's ``${X:-default}``."""
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add = p.add_argument
    repo = str(Path(__file__).resolve().parents[3])
    add("--ref", default=os.environ.get("REF", ""))  # a Kaldi-style egs dir with path.sh
    add("--fb", default=os.environ.get("FB", repo))
    add("--musan", default=os.environ.get("MUSAN", "data/musan/musan"))
    add("--rirs", default=os.environ.get("RIRS", "data/RIRS_NOISES"))
    add("--out", default=os.environ.get("OUT", "data/noisy"))
    add("--work", default=os.environ.get("WORK", "data/noisy_work"))
    add("--nj", type=int, default=int(os.environ.get("NJ", "16")))
    add("--splits", default=os.environ.get("SPLITS", DEFAULT_SPLITS))
    add("--types", default=os.environ.get("TYPES", " ".join(TYPES)))
    return p.parse_args()


def source_path_sh(path_sh: Path, cwd: Path) -> dict:
    """Return the environment ``path.sh`` produces, sourced FROM ``cwd``.

    path.sh sets KALDI_ROOT and a long PATH, and creates steps/utils symlinks in
    $PWD -- which is why cwd matters and why we pass the stage, not the caller's
    directory. Sourcing it in a subshell and reading back the environment is the
    only faithful way to get its PATH: it does upward directory search and
    conditional includes that would rot if transcribed into Python.
    """
    if not path_sh.exists():
        print(f"   note: no path.sh at {path_sh}; using current environment",
              file=sys.stderr)
        return dict(os.environ)
    r = subprocess.run(
        ["bash", "-c", f'. "{path_sh}" >/dev/null 2>&1; env -0'],
        cwd=cwd, capture_output=True, text=True,
    check=False)
    # A failed source silently yields the unmodified environment, and Kaldi's
    # tools then go missing several steps later with an unrelated error. Say so
    # here instead.
    if r.returncode != 0 or not r.stdout.strip():
        print(f"[make_noisy] WARNING: sourcing {path_sh} produced no environment "
              f"(rc={r.returncode}); kaldi tools will not be on PATH",
              file=sys.stderr)
    env = dict(os.environ)
    for chunk in r.stdout.split("\0"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            env[k] = v
    return env


def build_stage(a, env_ready: bool = False) -> Path:
    """Create the staging tree the kaldi scripts must run inside.

    The stage exists for two reasons that are properties of the recipe, not of
    the checkout:
      * reverb commands reference RIRS_NOISES/... RELATIVELY, so cwd must
        contain that symlink;
      * kaldi scripts resolve `utils/` and `steps/` relative to cwd.
    `utils/` stays a symlink to the live tree -- large, shared, and its
    fix_data_dir.sh conflict is fixed there, so pinning it would refreeze a bug.
    """
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    stage = work / "stage"
    stage.mkdir(parents=True, exist_ok=True)

    def link(target, name):
        p = stage / name
        if p.is_symlink() or p.exists():
            p.unlink()
        p.symlink_to(target)

    link(HERE / "kaldi" / "steps", "steps")
    link(a.rirs, "RIRS_NOISES")
    pk = Path(a.ref) / ".." / ".." / "pkaldi" / "egs" / "wsj" / "s5" / "utils"
    if not pk.resolve().is_dir():
        # the tools/kaldi submodule ships the same wsj utils
        pk = Path(a.fb) / "tools" / "kaldi" / "egs" / "wsj" / "s5" / "utils"
    link(pk.resolve(), "utils")
    return stage


def prepare_musan(a, stage: Path, env: dict) -> bool:
    work = Path(a.work)
    if (work / "musan_noise" / "wav.scp").is_file():
        return True
    print("== preparing MUSAN")
    r = subprocess.run(
        [str(stage / "steps" / "data" / "make_musan.sh"),
         "--sampling-rate", "16000", a.musan, str(work)],
        cwd=stage, env=env,
    check=False)
    if r.returncode != 0:
        print("   FAILED: make_musan.sh", file=sys.stderr)
        return False
    # Same reason as the corpus dirs: get_utt2dur.sh is broken in this checkout.
    # MUSAN wav.scp holds bare paths, so utt2dur.py reads the headers directly.
    for n in ("speech", "noise", "music"):
        subprocess.run(
            [sys.executable, str(HERE / "utt2dur.py"),
             str(work / f"musan_{n}" / "wav.scp"),
             str(work / f"musan_{n}" / "reco2dur")],
            cwd=stage, env=env,
        check=False)
    return True


def normalise_split(a, split: str, stage: Path, env: dict) -> Path | None:
    """Copy the gold-prep recipe's data dir with the first tab per line turned into a space.

    The gold-prep recipe writes its data dirs TAB-separated (``f"{utt}\\t{cmd}"``), but
    kaldi splits on whitespace-then-space and produced reco2dur keys like
    ``"dr1_felc0_si1386\\tffmpeg"`` -- every lookup then missed. Convert the
    FIRST tab only, and leave the gold-prep recipe's own dirs untouched since they work
    for it.
    """
    raw = Path(a.ref) / "data" / "golden" / split
    if not (raw / "wav.scp").is_file():
        print(f"skip {split} (no wav.scp)")
        return None
    src = Path(a.work) / f"src_{split}"
    if (src / ".norm").is_file():
        return src
    src.mkdir(parents=True, exist_ok=True)
    for f in ("wav.scp", "utt2spk", "spk2utt", "text", "segments", "reco2spk"):
        if (raw / f).is_file():
            # sed 's/\t/ /' -- FIRST tab only, hence the count arg.
            (src / f).write_text(
                "".join(ln.replace("\t", " ", 1)
                        for ln in (raw / f).read_text().splitlines(keepends=True))
            )
    if not (src / "spk2utt").is_file() and (src / "utt2spk").is_file():
        with open(src / "spk2utt", "w") as out:
            subprocess.run([str(stage / "utils" / "utt2spk_to_spk2utt.pl"),
                            str(src / "utt2spk")],
                           stdout=out, stderr=subprocess.DEVNULL, cwd=stage, env=env, check=False)
    # durations are required by augment_data_dir.py. NOT via
    # utils/data/get_utt2dur.sh: it runs wav-to-duration, which reads the wav
    # header then closes the pipe -- ffmpeg exits nonzero and kaldi treats that
    # as fatal. utt2dur.py derives duration from the source header plus the
    # adelay/apad values already encoded in the wav.scp command.
    subprocess.run([sys.executable, str(HERE / "utt2dur.py"),
                    str(src / "wav.scp"), str(src / "utt2dur")],
                   cwd=stage, env=env, check=False)
    shutil.copyfile(src / "utt2dur", src / "reco2dur")
    (src / ".norm").touch()
    return src


def augment_argv(kind: str, a, src: Path, dst: Path, stage: Path) -> list[str]:
    """The exact kaldi invocation per condition -- voxceleb/v2 parameters."""
    steps = stage / "steps" / "data"
    if kind == "reverb":
        return [str(steps / "reverberate_data_dir.py"),
                "--rir-set-parameters",
                f"0.5, {a.rirs}/simulated_rirs/smallroom/rir_list",
                "--rir-set-parameters",
                f"0.5, {a.rirs}/simulated_rirs/mediumroom/rir_list",
                "--speech-rvb-probability", "1",
                "--pointsource-noise-addition-probability", "0",
                "--isotropic-noise-addition-probability", "0",
                "--num-replications", "1", "--source-sampling-rate", "16000",
                str(src), str(dst)]
    aug = [str(steps / "augment_data_dir.py"), "--utt-suffix", ""]
    work = Path(a.work)
    if kind == "noise":
        aug += ["--fg-interval", "1", "--fg-snrs", "15:10:5:0",
                "--fg-noise-dir", str(work / "musan_noise")]
    elif kind == "music":
        aug += ["--bg-snrs", "15:10:8:5", "--num-bg-noises", "1",
                "--bg-noise-dir", str(work / "musan_music")]
    elif kind == "babble":
        aug += ["--bg-snrs", "20:17:15:13", "--num-bg-noises", "3:4:5:6:7",
                "--bg-noise-dir", str(work / "musan_speech")]
    return aug + [str(src), str(dst)]


def build_cell(a, split: str, kind: str, src: Path, stage: Path, env: dict) -> bool:
    corpus = "TIMIT" if split.startswith("timit") else (
        "Buckeye" if split.startswith("buckeye") else None)
    if corpus is None:
        print(f"   FAILED: cannot map split {split!r} to a corpus", file=sys.stderr)
        return False
    dst = Path(a.work) / f"{split}_{kind}"
    final = Path(a.out) / corpus / "noisy" / kind
    final.mkdir(parents=True, exist_ok=True)
    if (dst / ".done").is_file():
        print(f"  {split}/{kind} already built")
        return True
    print(f"== {split} / {kind}")
    shutil.rmtree(dst, ignore_errors=True)

    subprocess.run(augment_argv(kind, a, src, dst, stage), cwd=stage, env=env, check=False)

    # augment_data_dir.py / reverberate_data_dir.py raise on their closing
    # `utils/fix_data_dir.sh` call because TIMIT utt-ids are `dr1_felc0_si1386`
    # while the speaker is `felc0` -- kaldi wants speaker-ids to be utt-id
    # prefixes, which the gold-prep recipe's prep does not do. wav.scp is fully written
    # before that check, so judge success by the artefact, not the exit code.
    scp = dst / "wav.scp"
    if not scp.is_file() or scp.stat().st_size == 0:
        print(f"   FAILED: no wav.scp for {split}/{kind}", file=sys.stderr)
        return False

    # wav.scp entries are PIPES; realise them as files. One ffmpeg/sox chain per
    # utterance, nj at a time -- the pipes each spawn a process, so more than a
    # dozen in parallel thrashes.
    n = len(scp.read_text().splitlines())
    print(f"   materialising {n} utts -> {final}")
    # Run from the stage: reverb commands reference RIRS_NOISES/... relatively.
    subprocess.run([sys.executable, str(HERE / "materialise.py"),
                    str(scp), str(final), str(stage), str(a.nj)],
                   cwd=stage, env=env, check=False)
    made = len(list(final.iterdir())) if final.is_dir() else 0
    print(f"   {made} files in {final}")
    (dst / ".done").touch()
    return True


def main() -> int:
    a = env_defaults()
    stage = build_stage(a)
    # cd to the stage BEFORE sourcing path.sh -- see the module docstring.
    env = source_path_sh(Path(a.ref) / "path.sh", stage)
    if not prepare_musan(a, stage, env):
        return 1
    types = a.types.split()
    for split in a.splits.split():
        src = normalise_split(a, split, stage, env)
        if src is None:
            continue        # like the shell: a bad split does not abort the rest
        for kind in types:
            build_cell(a, split, kind, src, stage, env)
    print("NOISY_BUILD_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
