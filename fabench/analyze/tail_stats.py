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

"""Tail statistics: the error DISTRIBUTION (not just its mean), plus a
decomposition of MAE by error bucket. Separates a system's typical boundary
(median, TA) from its tail (p99, max, %>100 ms) — the mean-vs-tail view that
explains crossovers where a sharper aligner wins MAE but loses median.

All inputs/outputs are in ms. Full precision; callers round for presentation."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from fabench.analyze.base import Analytic, register

# (name, lower_exclusive_ms, upper_inclusive_ms). First bucket includes 0.
BUCKETS = (
    ("le10", 0.0, 10.0),
    ("10_25", 10.0, 25.0),
    ("25_50", 25.0, 50.0),
    ("50_100", 50.0, 100.0),
    ("gt100", 100.0, float("inf")),
)


def tail_percentiles(abs_ms: Sequence[float]) -> dict:
    a = np.asarray(abs_ms, dtype=float)
    return {
        "n": int(a.size),
        "mae": float(a.mean()),
        "median": float(np.median(a)),
        "p75": float(np.percentile(a, 75)),
        "p90": float(np.percentile(a, 90)),
        "p95": float(np.percentile(a, 95)),
        "p99": float(np.percentile(a, 99)),
        "max": float(a.max()),
        "ta10": float((a <= 10).mean() * 100),
        "ta25": float((a <= 25).mean() * 100),
        "ta50": float((a <= 50).mean() * 100),
        "pct_gt50": float((a > 50).mean() * 100),
        "pct_gt100": float((a > 100).mean() * 100),
        "pct_gt200": float((a > 200).mean() * 100),
    }


def mae_decomposition(abs_ms: Sequence[float]) -> dict:
    """Per bucket: share of boundaries (pct_*) and additive contribution to MAE
    (contrib_*). The contrib_* sum to MAE exactly."""
    a = np.asarray(abs_ms, dtype=float)
    n = a.size
    row: dict = {"n": int(n)}
    for name, lo, hi in BUCKETS:
        mask = (a <= hi) if lo == 0.0 else ((a > lo) & (a <= hi))
        row[f"pct_{name}"] = float(mask.mean() * 100) if n else float("nan")
        row[f"contrib_{name}"] = float(a[mask].sum() / n) if n else float("nan")
    return row


register(Analytic(
    "tail_percentiles",
    "Error-distribution percentiles",
    "n, MAE, median, p75/p90/p95/p99, max, TA@10/25/50, and over-threshold rates.",
    tail_percentiles,
))
register(Analytic(
    "mae_decomposition",
    "MAE decomposition by error bucket",
    "Per bucket (<=10,10-25,25-50,50-100,>100 ms): share of boundaries and "
    "additive contribution to MAE (contribs sum to MAE).",
    mae_decomposition,
))
