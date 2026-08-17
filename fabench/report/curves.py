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

"""Degradation curves + robustness scalar (Plan Section 6).

For each (corpus, aligner, mode, noise_type) we tabulate a metric (MAE, TA20)
across SNR ∈ {clean, 20, 15, 10} and summarize with a **robustness scalar** =
relative MAE inflation clean→10 dB. Sanity gate #8 (monotonicity): MAE should
trend up (or hold) as SNR drops; a sharp *improvement* under noise is flagged.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from collections.abc import Iterable

from fabench.report.tables import _f, _md_table


def _snr_of(condition: str):
    if condition == "clean":
        return None
    # "<noise>_snr<db>"
    try:
        return int(condition.rsplit("snr", 1)[1])
    except (IndexError, ValueError):
        return None


def _noise_of(condition: str):
    if condition == "clean":
        return "clean"
    return condition.rsplit("_snr", 1)[0]


def curve_data(rows: Iterable[dict], metric: str = "mae_ms"):
    """Return {(corpus,aligner,mode,noise_type): {snr_or_'clean': value}}."""
    out: dict[tuple, dict] = defaultdict(dict)
    clean: dict[tuple, float] = {}
    for r in rows:
        snr = _snr_of(r["condition"])
        key = (r["corpus"], r["aligner"], r["mode"])
        if r["condition"] == "clean":
            clean[key] = r.get(metric)
    for r in rows:
        if r["condition"] == "clean":
            continue
        noise = _noise_of(r["condition"])
        snr = _snr_of(r["condition"])
        k = (r["corpus"], r["aligner"], r["mode"], noise)
        out[k][snr] = r.get(metric)
        out[k]["clean"] = clean.get((r["corpus"], r["aligner"], r["mode"]))
    return out


def robustness_scalar(clean_v, degraded_v) -> float:
    """Relative error inflation clean->10dB = degraded/clean (>1 = worse)."""
    if clean_v in (None, 0) or (isinstance(clean_v, float) and math.isnan(clean_v)):
        return float("nan")
    if degraded_v is None or (isinstance(degraded_v, float) and math.isnan(degraded_v)):
        return float("nan")
    return degraded_v / clean_v


def degradation_table(rows: Iterable[dict], corpus: str, metric: str = "mae_ms") -> tuple[str, list]:
    data = {k: v for k, v in curve_data(rows, metric).items() if k[0] == corpus}
    if not data:
        return f"_(no degradation data for {corpus})_", []
    snrs = sorted({s for v in data.values() for s in v if isinstance(s, int)}, reverse=True)
    header = ["aligner", "mode", "noise", "clean"] + [f"{s}dB" for s in snrs] + ["robust(→10dB)", "monotonic?"]
    rows_out = []
    flags = []
    for (c, aligner, mode, noise), series in sorted(data.items()):
        clean_v = series.get("clean")
        cells = [aligner, mode, noise, _f(clean_v)]
        seq = [clean_v] + [series.get(s) for s in snrs]
        for s in snrs:
            cells.append(_f(series.get(s)))
        rob = robustness_scalar(clean_v, series.get(10))
        cells.append(_f(rob, 2))
        # monotonic = non-decreasing MAE as SNR drops (allow small slack)
        mono = _is_monotone_worse(seq, metric)
        cells.append("ok" if mono else "⚠")
        flags.append({"corpus": c, "aligner": aligner, "mode": mode, "noise": noise,
                      "monotonic": mono, "robustness": rob})
        rows_out.append(cells)
    return _md_table(header, rows_out), flags


def _is_monotone_worse(seq, metric: str) -> bool:
    """MAE should not sharply improve as SNR drops. For TA (higher=better) invert."""
    vals = [v for v in seq if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(vals) < 2:
        return True
    worse_is_up = "mae" in metric or "wbe" in metric
    slack = 1.15  # allow 15% noise wobble before flagging
    for a, b in itertools.pairwise(vals):
        if worse_is_up:
            if b < a / slack:  # got notably better under worse SNR -> suspicious
                return False
        else:
            if b > a * slack:
                return False
    return True
