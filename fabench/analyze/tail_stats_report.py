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

"""Tail statistics: for every aligner/corpus/level, persist the full error
DISTRIBUTION and a decomposition of MAE by error bucket.

Orchestration only — the compute is fabench.analyze.tail_stats. Writes
summary/analysis/{tail_percentiles,mae_decomposition}.csv. Run from the repo
root:  .venv/bin/python -m fabench.analyze.tail_stats_report
"""
from __future__ import annotations

import csv

from fabench.analyze._analysis_common import REPO, load_gold, phone_errors, systems, word_errors
from fabench.analyze.tail_stats import BUCKETS, mae_decomposition, tail_percentiles

PCT_FIELDS = ["corpus", "level", "aligner", "n", "mae", "median",
              "p75", "p90", "p95", "p99", "max",
              "ta10", "ta25", "ta50", "pct_gt50", "pct_gt100", "pct_gt200"]
_PCT_DP = {"mae": 2, "median": 2, "p75": 2, "p90": 2, "p95": 2, "p99": 2, "max": 1,
           "ta10": 1, "ta25": 1, "ta50": 1, "pct_gt50": 2, "pct_gt100": 2, "pct_gt200": 2}

DECOMP_FIELDS = ["corpus", "level", "aligner", "n"] + \
    [f"{k}_{b}" for b in (n for n, _, _ in BUCKETS) for k in ("pct", "contrib")]
_DECOMP_DP = {**{f"pct_{n}": 1 for n, _, _ in BUCKETS},
              **{f"contrib_{n}": 2 for n, _, _ in BUCKETS}}


def _round(row, dp):
    return {k: (round(v, dp[k]) if k in dp else v) for k, v in row.items()}


def main() -> None:
    pct_rows, decomp_rows = [], []
    for corpus in ("timit", "buckeye"):
        gold, gold_canon = load_gold(corpus)
        for name, path, has_phones in systems(corpus):
            levels = []
            if has_phones:
                levels.append(("phone", [a for a, _s, _sil in phone_errors(gold, gold_canon, path)]))
            levels.append(("word", [a for a, _sil in word_errors(gold, path)]))
            for level, abs_ms in levels:
                if not abs_ms:
                    continue
                head = {"corpus": corpus, "level": level, "aligner": name}
                pct_rows.append({**head, **tail_percentiles(abs_ms)})
                decomp_rows.append({**head, **mae_decomposition(abs_ms)})
            print(f"  scored {corpus:8s} {name}", flush=True)

    pct_rows.sort(key=lambda r: (r["corpus"], r["level"], r["mae"]))
    decomp_rows.sort(key=lambda r: (r["corpus"], r["level"], r["aligner"]))

    outdir = REPO / "summary" / "analysis"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "tail_percentiles.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PCT_FIELDS)
        w.writeheader()
        for r in pct_rows:
            w.writerow(_round({k: r[k] for k in PCT_FIELDS}, _PCT_DP))
    with open(outdir / "mae_decomposition.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DECOMP_FIELDS)
        w.writeheader()
        for r in decomp_rows:
            w.writerow(_round({k: r[k] for k in DECOMP_FIELDS}, _DECOMP_DP))

    print(f"\nwrote {len(pct_rows)} rows -> {outdir/'tail_percentiles.csv'}")
    print(f"wrote {len(decomp_rows)} rows -> {outdir/'mae_decomposition.csv'}\n")
    hdr = (f"{'corpus':8s} {'level':5s} {'aligner':8s} {'MAE':>7s} {'med':>6s} "
           f"{'p95':>7s} {'p99':>8s} {'max':>9s} {'%>100':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for r in pct_rows:
        print(f"{r['corpus']:8s} {r['level']:5s} {r['aligner']:8s} {r['mae']:7.2f} "
              f"{r['median']:6.2f} {r['p95']:7.2f} {r['p99']:8.2f} {r['max']:9.1f} {r['pct_gt100']:6.2f}")


if __name__ == "__main__":
    main()
