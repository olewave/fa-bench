#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""What would Track 2 look like if every system's clock were corrected?

WHY. Fig. 1 shows that most Track 2 systems carry a constant offset in their
word times, and boundary MAE cannot see it because it takes the magnitude
before averaging. This asks the obvious follow-up. Give each system its own two
constants, one for word starts and one for word ends, and score it again.

HOW IT STAYS HONEST. The two constants are estimated on the DEV split of the
same corpus and applied to the TEST split, so nothing is fitted on the data it
is scored on. A system with no real bias therefore LOSES a little, which is the
correct behaviour and the control that makes the gainers believable.

The shifted hypotheses are scored by the real scorer, not by a reimplementation
of it. A scratch root is built holding `fabench/` (symlinked) and `evals/` with
one recipe per tool, so `Config.repo_root()` resolves there and `fabench score`
reads the shifted hyp files. Scoring the UNSHIFTED hypotheses through the same
path reproduces the published leaderboard, which is what `--verify` checks.

    measure_debiased_track2.py                 # stage, score, print
    measure_debiased_track2.py --verify        # also score the unshifted control
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fabench.paths import tool_index                        # noqa: E402
from fabench.score.core import _SILENCE_WORDS               # noqa: E402
from fabench.score.matched import nw_align                  # noqa: E402

_spec = importlib.util.spec_from_file_location("mob", ROOT / "evals/measure_onset_bias.py")
mob = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mob)

#: Track 2 as Table 1 prints it, in table order. Read off gen_paper_tables'
#: row list rather than guessed, so a row the paper drops drops from here too.
TRACK2 = ["whisper_ts", "whisper3", "parakeet_tdt", "whisperx_asr", "torchaudio_asr",
          "crisperwhisper", "qwen3_asr", "mfa3_on_qwen3asr", "speechmatics", "deepgram",
          "azure", "ibm", "assemblyai", "aws", "elevenlabs", "google_stt_chirp2",
          "olign_on_qwen3asr", "olign_on_chirp2", "olign_on_parakeettdt"]
NAME = {"whisper_ts": "Whisper-ts", "whisper3": "Whisper", "parakeet_tdt": "Parakeet",
        "whisperx_asr": "W->WhisperX", "torchaudio_asr": "TorchAudio",
        "crisperwhisper": "CrisperW", "qwen3_asr": "Q->Qwen3-FA",
        "mfa3_on_qwen3asr": "Q->MFA", "speechmatics": "Speechmatics",
        "deepgram": "Deepgram", "azure": "Azure", "ibm": "IBM",
        "assemblyai": "AssemblyAI", "aws": "Amazon", "elevenlabs": "ElevenLabs",
        "google_stt_chirp2": "Google", "olign_on_qwen3asr": "Q->Olign",
        "olign_on_chirp2": "G->Olign", "olign_on_parakeettdt": "P->Olign"}
#: test cell -> the dev cell the two constants are estimated on, and its gold glob.
CELLS = {("timit", "core_test"): ("timit", "dev", "timit__dev__*.jsonl"),
         ("buckeye", "test"): ("buckeye", "dev", "buckeye__paper__dev__*.jsonl")}
#: Fewer matched pairs than this and the mean is not a constant worth removing.
MIN_PAIRS = 100


def dev_offsets(hyp: pathlib.Path, pattern: str):
    """Mean signed word onset and offset error on the dev split, in seconds."""
    gold = mob.gold_of(pattern, "words")
    on, off = [], []
    for line in open(hyp):
        r = json.loads(line)
        g, h = gold.get(r.get("utt_id")), mob._ivs(r, "words")
        if not g or not h:
            continue
        gi = [x for x in g if x.label.lower() not in _SILENCE_WORDS]
        hi = [x for x in h if x.label.lower() not in _SILENCE_WORDS]
        gl = [x.label.lower() for x in gi]
        hl = [x.label.lower() for x in hi]
        for a, b in nw_align(gl, hl).matched(gl, hl):
            on.append(hi[b].start - gi[a].start)
            off.append(hi[b].end - gi[a].end)
    if len(on) < MIN_PAIRS:
        return None
    return statistics.fmean(on), statistics.fmean(off)


def shift_file(src: pathlib.Path, dst: pathlib.Path, d_on: float, d_off: float) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src) as fi, open(dst, "w") as fo:
        for line in fi:
            r = json.loads(line)
            for key in ("words", "phones"):
                for w in (r.get(key) or []):
                    if not isinstance(w, dict):
                        continue
                    if w.get("start") is not None:
                        w["start"] -= d_on
                    if w.get("end") is not None:
                        w["end"] -= d_off
            fo.write(json.dumps(r) + "\n")


def stage(scratch: pathlib.Path, shift: bool) -> list[tuple]:
    """Build a scoring root. `shift` off gives the unshifted control."""
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / "evals" / "configs").mkdir(parents=True)
    os.symlink(ROOT / "fabench", scratch / "fabench")
    idx, out = tool_index(ROOT), []
    for (corpus, subset), (dcorpus, dsubset, pat) in CELLS.items():
        for tool in TRACK2:
            hit = idx.get(tool)
            if not hit:
                out.append((corpus, tool, "no recipe")); continue
            kind, d = hit
            test = d / "en" / corpus / subset / "origin" / "hyp.jsonl"
            dev = d / "en" / dcorpus / dsubset / "origin" / "hyp.jsonl"
            if not test.is_file():
                out.append((corpus, tool, "no test hyp")); continue
            tdir = scratch / "evals" / kind / tool
            tdir.mkdir(parents=True, exist_ok=True)
            if not (tdir / "config.yaml").exists():
                shutil.copy(d / "config.yaml", tdir / "config.yaml")
            d_on = d_off = 0.0
            if shift:
                if not dev.is_file():
                    out.append((corpus, tool, "no dev hyp")); continue
                got = dev_offsets(dev, pat)
                if got is None:
                    out.append((corpus, tool, "too few dev pairs")); continue
                d_on, d_off = got
            shift_file(test, tdir / "en" / corpus / subset / "origin" / "hyp.jsonl",
                       d_on, d_off)
            out.append((corpus, tool, f"{1000 * d_on:+.1f} / {1000 * d_off:+.1f} ms"))
    return out


def score(scratch: pathlib.Path) -> None:
    py = str(ROOT / ".venv/bin/python")
    tools = ",".join(sorted(p.name for p in (scratch / "evals/timestamp_asrs").iterdir()))
    import yaml
    for corpus, subset in CELLS:
        cfg = scratch / "evals/configs" / f"sc_{corpus}_{subset}.yaml"
        res = scratch / "summary/timestamp_asrs/en" / corpus / subset / "origin"
        subprocess.run([py, str(ROOT / "evals/gen_config.py"), "--corpus", corpus,
                        "--subset", subset, "--tools", tools, "--out", str(cfg)],
                       check=True, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        c = yaml.safe_load(cfg.read_text()) or {}
        c.setdefault("paths", {})["results_dir"] = str(res)
        cfg.write_text(yaml.safe_dump(c, sort_keys=False))
        subprocess.run([py, "-m", "fabench", "score", "--config", str(cfg)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL)
        print(f"[ ok ] {corpus}/{subset}", file=sys.stderr)


def leaderboard(base: pathlib.Path, corpus: str, subset: str) -> dict:
    p = base / "summary/timestamp_asrs/en" / corpus / subset / "origin" / "leaderboard.csv"
    out = {}
    if not p.is_file():
        return out
    for r in csv.DictReader(p.open()):
        try:
            out[r["aligner"]] = (float(r["wbe_ms"]), float(r["wbnd_f1_all_20ms"]))
        except (TypeError, ValueError, KeyError):
            pass
    return out


def report(plain: pathlib.Path, deb: pathlib.Path) -> str:
    L = ["# Track 2 with each system's clock offset removed", "",
         "Word tier, clean audio, $F_1$ at 20 ms. Two constants per system, one for",
         "word starts and one for word ends, estimated on the DEV split of the same",
         "corpus and subtracted from its TEST timestamps. Nothing is fitted on the",
         "split it is scored on, so an unbiased system loses a little.", ""]
    for corpus, subset, label in (("timit", "core_test", "TIMIT test"),
                                  ("buckeye", "test", "Buckeye test")):
        a, b = leaderboard(plain, corpus, subset), leaderboard(deb, corpus, subset)
        L += [f"## {label}", "",
              "| system | MAE | debiased | cut | F1 | debiased | gain |",
              "|---|---|---|---|---|---|---|"]
        dm, df = [], []
        for t in TRACK2:
            if t not in a or t not in b:
                continue
            m0, f0 = a[t]; m1, f1 = b[t]
            dm.append(100 * (m0 - m1) / m0); df.append(f1 - f0)
            L.append(f"| {NAME[t]} | {m0:.1f} | {m1:.1f} | {dm[-1]:.0f}% "
                     f"| {f0:.2f} | {f1:.2f} | {f1 - f0:+.3f} |")
        L += [f"| **mean** | | | **{statistics.fmean(dm):.0f}%** | | "
              f"| **{statistics.fmean(df):+.3f}** |", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", default=str(ROOT / "summary/local/debias"))
    ap.add_argument("--out", default=str(ROOT / "docs/paper/debiased_track2.md"))
    ap.add_argument("--verify", action="store_true",
                    help="also score the unshifted control and diff it against "
                         "the published leaderboard")
    a = ap.parse_args()
    s = pathlib.Path(a.scratch)
    for name, shift in (("plain", False), ("debiased", True)):
        rows = stage(s / name, shift)
        bad = [r for r in rows if "ms" not in r[2]]
        for r in bad:
            print(f"[skip] {r[0]} {r[1]}: {r[2]}", file=sys.stderr)
        score(s / name)
    if a.verify:
        n = mism = 0
        for corpus, subset in CELLS:
            pub = leaderboard(ROOT, corpus, subset)
            ctl = leaderboard(s / "plain", corpus, subset)
            for t in ctl:
                for i, k in enumerate(("wbe_ms", "wbnd_f1_all_20ms")):
                    if t not in pub:
                        continue
                    n += 1
                    if abs(pub[t][i] - ctl[t][i]) > 1e-6:
                        mism += 1
                        print(f"[diff] {corpus} {t} {k}: {pub[t][i]} vs {ctl[t][i]}",
                              file=sys.stderr)
        print(f"[ctrl] {n} values compared, {mism} differ", file=sys.stderr)
    text = report(s / "plain", s / "debiased")
    pathlib.Path(a.out).write_text(text + "\n")
    print(text)
    print(f"\nwrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
