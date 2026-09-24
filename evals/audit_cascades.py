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
"""Prove every cascade cell aligned the ASR's words, not the reference gold.

WHY THIS EXISTS. A cascade is only a track-2 measurement because the aligner
was handed another tool's transcript. If it silently receives gold instead, the
cell still runs, still scores, and still looks like a success -- while actually
reporting a track-1 number under a track-2 name. That is the one error the
two-track split exists to prevent, and no log shows it.

It has happened. `params.transcript_hyp` is honoured by fabench/aligners/
runner.py; a machine running an older copy of that file ignores the key it does
not know and falls back to `" ".join(w.label for w in gold.words)`. Eighteen
cells were aligned against gold that way before anyone noticed, because the
only visible symptom is in the CONTENT of hyp.jsonl.

THE TEST IS COMPARATIVE, not exact-match. Aligners legitimately alter tokens:
Charsiu emits [sil] in the word tier and sometimes repeats a leading word, MAPS
and BFA reshape edge tokens. So a cell is judged by whether its words resemble
the ASR hypothesis MORE than they resemble gold. Matching gold more closely
than the transcript it was supposedly given is only explicable one way.

Exits non-zero if any cell fails, so it can gate publishing.

    evals/audit_cascades.py                # audit every cascade cell
    evals/audit_cascades.py --tool olign_on_qwen3asr
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Word-tier tokens that belong to an aligner's own topology rather than to the
#: transcript it was given, and so must not count against provenance.
SILENCE = {"[sil]", "sil", "<sil>", "sp", "spn", "[sp]", "", "<eps>", "!sil"}

#: Canonical gold manifest per (corpus, subset). Buckeye carries the paper's
#: segmentation in its name, so the mapping is explicit rather than derived.
#: Below this many transcript-vs-gold differences, the comparison is noise.
MIN_DISCRIMINATING = 10

GOLD_GLOB = {
    ("timit", "core_test"): "timit__core_test__*.jsonl",
    ("timit", "dev"): "timit__dev__*.jsonl",
    ("buckeye", "test"): "buckeye__paper__test__*.jsonl",
    ("buckeye", "dev"): "buckeye__paper__dev__*.jsonl",
}


def _words(rec: dict) -> list[str]:
    """Word labels, lowercased.

    Lowercased because the scorer is (fabench/score/word.py aligns on
    lowercased labels), so a case difference is not a provenance difference.
    Comparing raw labels made the gate disagree with the thing it guards: on
    TIMIT dev it counted 16 of 43 as matching the transcript where a
    case-insensitive comparison counts 50 of 50.
    """
    out = [w["label"] if isinstance(w, dict) else w[0] for w in (rec.get("words") or [])]
    return [w.lower() for w in out if w.lower() not in SILENCE]


def _by_utt(path: pathlib.Path) -> dict[str, list[str]]:
    """utt_id -> word labels, from the WORD-tier records only.

    Keyed without filtering, a tool that emits more than one mode overwrote its
    word records with its later ones: torchaudio_fa also runs mode B, where the
    gold phone sequence is supplied and the record carries no words at all. The
    audit then compared an empty list against both transcripts, matched neither,
    and still passed -- the verdict only fires when gold beats asr, and 0 does
    not beat 0. A cascade could have been aligned against gold and cleared this
    gate. Mode A is the word tier, which is what provenance is checked on.
    """
    out: dict[str, list[str]] = {}
    with path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("mode") not in (None, "A"):
                continue
            out[rec["utt_id"]] = _words(rec)
    return out


def audit(root: pathlib.Path, only: str | None = None) -> list[tuple]:
    rows, gold_cache = [], {}
    for tool_dir in sorted((root / "evals/timestamp_asrs").glob("*_on_*")):
        if only and tool_dir.name != only:
            continue
        for hyp in sorted(tool_dir.glob("en/*/*/*/hyp.jsonl")):
            corpus, subset, cond = hyp.relative_to(tool_dir / "en").parts[:3]
            # The upstream comes from the CELL CONFIG, which is what the runner
            # actually read. Deriving it from the tool name silently audited the
            # wrong thing: "olign_on_parakeettdt" gave "parakeettdt", the
            # directory is "parakeet_tdt", the lookup missed, and the old
            # qwen3_asr fallback compared a Parakeet cascade against Qwen3's
            # words -- reported as a gold fallback for two cells that were fine.
            # No fallback now: an upstream that cannot be located is NO-UPSTREAM,
            # never a different tool's transcript.
            asr = None
            cfg = hyp.parent / "config.yaml"
            if cfg.is_file():
                for line in cfg.read_text().splitlines():
                    key, sep, val = line.partition("transcript_hyp:")
                    if sep:
                        asr = root / val.strip().strip('"\'')
                        break
            if asr is None or not asr.is_file():
                rows.append((tool_dir.name, f"{corpus}/{subset}/{cond}", 0, 0, 0,
                             "NO-UPSTREAM"))
                continue
            key = (corpus, subset)
            if key not in gold_cache:
                found = sorted((root / "data/work/canonical").glob(GOLD_GLOB.get(key, "")))
                gold_cache[key] = ({json.loads(x)["utt_id"]: _words(json.loads(x))
                                    for x in found[0].read_text().splitlines()}
                                   if found else {})
            gold, asr_w, casc = gold_cache[key], _by_utt(asr), _by_utt(hyp)
            shared = [u for u in casc if u in asr_w and u in gold]
            if not shared:
                continue
            # Only utterances where the transcript and gold DIFFER can tell the
            # two apart. Counting the rest is what made this gate cry wolf:
            # Parakeet-TDT matches gold on 350 of 400 TIMIT dev utterances, so
            # those 350 landed in both tallies and a 3-utterance wobble read as
            # a gold fallback. On the 50 that did discriminate, the cascade
            # matched the transcript 50 times and gold 0.
            disc = [u for u in shared if asr_w[u] != gold[u]]
            n_asr = sum(1 for u in disc if casc[u] == asr_w[u])
            n_gold = sum(1 for u in disc if casc[u] == gold[u])
            if len(disc) < MIN_DISCRIMINATING:
                # Too few informative utterances to judge -- say so rather than
                # pass or fail on noise.
                verdict = f"UNDECIDABLE({len(disc)})"
            else:
                verdict = "GOLD-FALLBACK" if n_gold > n_asr else "ok"
            rows.append((tool_dir.name, f"{corpus}/{subset}/{cond}",
                         len(disc), n_asr, n_gold, verdict))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--tool", default=None, help="audit one cascade only")
    ap.add_argument("--quiet", action="store_true", help="print only failures")
    a = ap.parse_args(argv)

    rows = audit(pathlib.Path(a.root), a.tool)
    bad = [r for r in rows if not r[5].startswith(("ok", "UNDECIDABLE"))]
    if not a.quiet:
        print(f"  {'tool':<24}{'cell':<30}{'diff':>6}{'asr':>7}{'gold':>7}  verdict")
        for r in rows:
            print(f"  {r[0]:<24}{r[1]:<30}{r[2]:>6}{r[3]:>7}{r[4]:>7}  {r[5]}")
    print(f"\n{len(rows)} cascade cells audited, {len(bad)} not ASR-driven")
    for r in bad:
        print(f"  FAIL {r[0]} {r[1]}: resembles gold ({r[4]}) more than the "
              f"transcript it was given ({r[3]}) -- re-run this cell",
              file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
