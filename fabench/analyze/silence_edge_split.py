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

"""Silence-edge split: for every aligner/corpus, decompose boundary MAE into
INTERIOR (speech-to-speech) vs SILENCE/EDGE boundaries, at phone and word level.

Orchestration only — the compute is fabench.analyze.silence_edge. Writes
summary/analysis/silence_edge_split.csv and prints a compact table. Run from the
repo root:  .venv/bin/python -m fabench.analyze.silence_edge_split
"""
from __future__ import annotations

import csv

from fabench.analyze._analysis_common import REPO, load_gold, phone_errors, systems, word_errors
from fabench.analyze.silence_edge import silence_edge_split

FIELDS = ["corpus", "level", "aligner", "n", "n_interior", "n_edge",
          "mae_all", "mae_interior", "mae_edge", "pct_edge"]
# per-column decimal places for the CSV (presentation only)
_DP = {"mae_all": 2, "mae_interior": 2, "mae_edge": 2, "pct_edge": 1}


def _row(corpus, level, aligner, errs):
    r = {"corpus": corpus, "level": level, "aligner": aligner}
    r.update(silence_edge_split(errs))
    return r


def main() -> None:
    rows = []
    for corpus in ("timit", "buckeye"):
        gold, gold_canon = load_gold(corpus)
        for name, path, has_phones in systems(corpus):
            if has_phones:
                pe = [(a, sil) for a, _signed, sil in phone_errors(gold, gold_canon, path)]
                rows.append(_row(corpus, "phone", name, pe))
            rows.append(_row(corpus, "word", name, word_errors(gold, path)))
            print(f"  scored {corpus:8s} {name}", flush=True)

    rows.sort(key=lambda r: (r["corpus"], r["level"], r["mae_all"]))
    out = REPO / "summary" / "analysis" / "silence_edge_split.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(r[k], _DP[k]) if k in _DP else r[k]) for k in FIELDS})

    print(f"\nwrote {len(rows)} rows -> {out}\n")
    hdr = f"{'corpus':8s} {'level':5s} {'aligner':8s} {'MAE':>7s} {'interior':>9s} {'edge':>7s} {'%edge':>6s}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['corpus']:8s} {r['level']:5s} {r['aligner']:8s} "
              f"{r['mae_all']:7.2f} {r['mae_interior']:9.2f} {r['mae_edge']:7.2f} {r['pct_edge']:6.1f}")


if __name__ == "__main__":
    main()
