#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""How often does a time-only F1 hit credit the WRONG reference boundary?

F1 pairs boundaries by time and ignores labels, which is the segmentation
literature's convention and the only rule a system emitting no labels can be
scored under. It buys that generality at a price: a hit says a hypothesis
boundary landed within the tolerance of SOME reference boundary, not that it
landed near the one it corresponds to.

This measures the price. On Track 1 every system is handed the reference
transcript, so hypothesis word i corresponds to gold word i and a hit that pairs
across ranks is crediting the neighbour. The share is not a constant of the
metric. It is near zero for accurate aligners and large for coarse ones, which
means F1 is most generous to the systems that need it least:

    TIMIT core-test, clean      Olign 0%   MFA 0%   MMS-FA  4%   NeMo-FA 29%
    Buckeye dev, clean          Olign 1%   MFA 1%   MMS-FA 15%   NeMo-FA 35%

So an F1 gap between a good and a bad aligner understates the real one, and
that is the argument for reporting tolerance accuracy beside it rather than
instead of it.

    analyze_boundary_pairing.py
    analyze_boundary_pairing.py --tol-ms 50
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fabench.schema import Interval
from fabench.score.segmentation import boundaries_from_intervals

#: (label, gold manifest glob, cell path under a tool directory)
CASES = [
    ("timit core_test clean",  "timit__*core_test*.jsonl",    "en/timit/core_test/origin"),
    ("timit core_test babble", "timit__*core_test*.jsonl",    "en/timit/core_test/babble"),
    ("buckeye dev clean",      "buckeye__paper__dev__*.jsonl", "en/buckeye/dev/origin"),
    ("buckeye dev babble",     "buckeye__paper__dev__*.jsonl", "en/buckeye/dev/babble"),
]
TOOLS = [("Olign", "evals/aligners/olign/exps/noisy"),
         ("MFA", "evals/aligners/mfa"),
         ("MMS-FA", "evals/aligners/mms_fa"),
         ("NeMo-FA 80ms", "evals/aligners/nemo_fa"),
         ("NeMo-FA 40ms", "evals/aligners/nemo_fa/exps/conformer")]


def load_gold(pattern: str) -> dict[str, list[Interval]]:
    out = {}
    for f in glob.glob(str(ROOT / "data/work/canonical" / pattern)):
        for line in open(f):
            r = json.loads(line)
            out[r["utt_id"]] = [
                Interval(w[0] if isinstance(w, list) else w["label"],
                         w[1] if isinstance(w, list) else w["start"],
                         w[2] if isinstance(w, list) else w["end"])
                for w in r["words"]]
    return out


def greedy_pairs(g: list[float], h: list[float], tol_s: float):
    """The same one-to-one closest-first pairing count_hits uses, but it
    returns WHICH indices were paired rather than only how many."""
    cands = sorted((abs(b - a), i, j)
                   for i, a in enumerate(g) for j, b in enumerate(h)
                   if abs(b - a) <= tol_s)
    used_g, used_h, out = set(), set(), []
    for _, i, j in cands:
        if i in used_g or j in used_h:
            continue
        used_g.add(i)
        used_h.add(j)
        out.append((i, j))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tol-ms", type=float, default=20.0)
    a = ap.parse_args(argv)
    tol = a.tol_ms / 1000.0
    print(f"cross-rank share of F1 hits at {a.tol_ms:.0f} ms, Track 1")
    for label, pattern, cell in CASES:
        gold = load_gold(pattern)
        cols = []
        for name, d in TOOLS:
            p = ROOT / d / cell / "hyp.jsonl"
            if not p.is_file():
                continue
            off = collections.Counter()
            for line in p.read_text().splitlines():
                r = json.loads(line)
                uid = r.get("utt_id") or str(r["item_id"]).split("__")[0]
                ws = [Interval(w["label"], w["start"], w["end"])
                      for w in (r.get("words") or [])]
                if uid not in gold or not ws:
                    continue
                gb = boundaries_from_intervals(gold[uid])
                hb = boundaries_from_intervals(ws)
                # Ranks are only comparable when both sides have the same number
                # of boundaries. Utterances where they differ are skipped rather
                # than guessed at.
                if len(gb) != len(hb):
                    continue
                for i, j in greedy_pairs(gb, hb, tol):
                    off[i - j] += 1
            total = sum(off.values())
            if total:
                cols.append(f"{name} {100 * (total - off.get(0, 0)) / total:.0f}%")
        print(f"  {label:24s} " + "   ".join(cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
