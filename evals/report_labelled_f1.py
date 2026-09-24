#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Time-only boundary F1 against the label-checked one, every system and cell.

WHAT THE SECOND NUMBER ADDS. Time-only F1 pairs boundaries by time and ignores
labels, so a hit says a hypothesis boundary landed within the tolerance of SOME
reference boundary, not that the system found the boundary it was supposed to.
The label-checked score requires the units on BOTH sides of the boundary to be
the aligned, same-labelled units, so a boundary credited to a neighbour is not
credited at all. WRONG is the share of time-only hits that the identity check
withdraws.

    report_labelled_f1.py                 # word tier, clean
    report_labelled_f1.py --tier phone
    report_labelled_f1.py --cond noisy    # mean of the four degradations
    report_labelled_f1.py --csv out.csv   # every cell, long form
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CELLS = (("timit", "dev"), ("timit", "core_test"),
         ("buckeye", "dev"), ("buckeye", "test"))
CELL_LABEL = {("timit", "dev"): "TIMIT dev", ("timit", "core_test"): "TIMIT test",
              ("buckeye", "dev"): "Buck dev", ("buckeye", "test"): "Buck test"}
CONDS = ("reverb", "noise", "music", "babble")
#: Column trio per tier: the time-only baseline, the label-checked score, and
#: the positional one. The word tier's baseline is the silence-filtered
#: `nosil` variant, because the label-checked score runs on those sequences
#: and only equal denominators can be differenced.
TIERS = {"word": ("wbnd_f1_nosil_20ms", "wbnd_f1_lbl_20ms", "wbnd_f1_pos_20ms", "wbnd_f1"),
         "phone": ("bnd_f1", "bnd_f1_lbl_20ms", "bnd_f1_pos_20ms", "bnd_f1")}


def num(row, key):
    v = (row.get(key) or "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def read(kind, corpus, subset, cond):
    p = ROOT / "summary" / kind / "en" / corpus / subset / cond / "leaderboard.csv"
    if not p.is_file():
        return {}
    return {r["aligner"]: r for r in csv.DictReader(p.open())}


def collect(tier):
    """``{tool: {(cell, cond): (plain, lbl, pos)}}`` over both tracks."""
    base, lbl, pos, _ = TIERS[tier]
    out: dict[str, dict] = {}
    for kind in ("aligners", "timestamp_asrs"):
        for cell in CELLS:
            for cond in ("origin",) + CONDS:
                for tool, r in read(kind, cell[0], cell[1], cond).items():
                    out.setdefault(tool, {})[(cell, cond)] = (
                        num(r, base), num(r, lbl), num(r, pos))
    return out


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def fmt(v, w=6):
    return f"{v:{w}.3f}" if v is not None else " " * (w - 1) + "-"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tier", choices=("word", "phone"), default="word")
    ap.add_argument("--cond", choices=("clean", "noisy"), default="clean")
    ap.add_argument("--csv", help="write every cell and condition here instead")
    a = ap.parse_args(argv)

    data = collect(a.tier)
    if not data:
        print("no leaderboards; run evals/rescore_all.sh", file=sys.stderr)
        return 1

    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tool", "corpus", "split", "condition", "tier",
                        "f1_time_only", "f1_label_checked", "f1_positional",
                        "wrong_hit_pct"])
            for tool, cells in sorted(data.items()):
                for (cell, cond), (p, l, ps) in sorted(cells.items(), key=str):
                    wrong = 100 * (1 - l / p) if (p and l is not None) else None
                    w.writerow([tool, cell[0], cell[1], cond, a.tier,
                                p, l, ps, wrong])
        print(f"wrote {a.csv}")
        return 0

    def cellval(cells, cell):
        if a.cond == "clean":
            return cells.get((cell, "origin"), (None, None, None))
        got = [cells.get((cell, c), (None, None, None)) for c in CONDS]
        return tuple(mean([g[i] for g in got]) for i in range(3))

    print(f"{a.tier.upper()} TIER, {a.cond}. F1 at 20 ms: time-only | "
          f"label-checked | positional, and the share of time-only hits the "
          f"identity check withdraws.\n")
    head = f"  {'system':<24}"
    for cell in CELLS:
        head += f"{CELL_LABEL[cell]:>25}"
    print(head)
    print(f"  {'':<24}" + "".join(f"{'time':>7}{'lbl':>7}{'wrong':>11}"
                                  for _ in CELLS))
    rows = []
    for tool, cells in data.items():
        vals = [cellval(cells, c) for c in CELLS]
        if all(v[0] is None for v in vals):
            continue
        rows.append((mean([v[1] for v in vals]) or -1, tool, vals))
    for _, tool, vals in sorted(rows, reverse=True):
        line = f"  {tool:<24}"
        for p, l, _ps in vals:
            wrong = f"{100 * (1 - l / p):9.1f}%" if (p and l is not None) else " " * 10
            line += f"{fmt(p, 7)}{fmt(l, 7)}{wrong}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
