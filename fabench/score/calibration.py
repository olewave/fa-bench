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

"""Confidence calibration (Plan 5.7).

Only for systems that emit a per-boundary confidence. Three views, each robust
to a different pathology:

* **Spearman(conf, -|error|)** — monotonic trend (rank, not Pearson: error is
  heavy-tailed).
* **AUROC(conf -> within-20ms)** — the "confidently wrong" penalty.
* **ECE** vs empirical within-20ms rate — only where conf is a true probability
  (CTC posteriors in [0,1]); N/A (nan) for e.g. MFA log-likelihoods.

Systems emitting no confidence are marked N/A upstream (no fabricated scores).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _clean(conf: Sequence[float | None], abs_err_s: Sequence[float]):
    c, e = [], []
    for ci, ei in zip(conf, abs_err_s):
        if ci is None:
            continue
        cf = float(ci)
        if np.isnan(cf):
            continue
        c.append(cf)
        e.append(float(ei))
    return np.asarray(c, float), np.asarray(e, float)


def spearman(conf: np.ndarray, neg_abs_err: np.ndarray) -> float:
    if conf.size < 3 or np.ptp(conf) == 0 or np.ptp(neg_abs_err) == 0:
        return float("nan")
    from scipy.stats import spearmanr

    rho, _ = spearmanr(conf, neg_abs_err)
    return float(rho)


def auroc(conf: np.ndarray, positive: np.ndarray) -> float:
    """AUROC of conf as a score for the binary label ``positive``.

    Computed via the Mann-Whitney U statistic with tie-averaged ranks, so no
    sklearn dependency.
    """
    pos = positive.astype(bool)
    n_pos = int(pos.sum())
    n_neg = int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    from scipy.stats import rankdata

    ranks = rankdata(conf)
    auc = (ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def ece(conf: np.ndarray, positive: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error. Requires conf in [0,1]; else nan (N/A)."""
    if conf.size == 0:
        return float("nan")
    if conf.min() < 0.0 or conf.max() > 1.0:
        return float("nan")  # not a probability -> ECE undefined
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # include right edge in last bin
    idx = np.clip(np.digitize(conf, edges[1:-1], right=False), 0, n_bins - 1)
    total = conf.size
    e = 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        acc = positive[m].mean()
        avg_conf = conf[m].mean()
        e += (m.sum() / total) * abs(acc - avg_conf)
    return float(e)


def calibration_metrics(
    conf: Sequence[float | None],
    abs_err_s: Sequence[float],
    within_tau_s: float = 0.020,
    n_bins: int = 10,
) -> dict:
    c, err = _clean(conf, abs_err_s)
    n = int(c.size)
    if n == 0:
        return {
            "n_conf": 0,
            "spearman": float("nan"),
            "auroc": float("nan"),
            "ece": float("nan"),
        }
    positive = err <= within_tau_s
    return {
        "n_conf": n,
        "spearman": spearman(c, -err),
        "auroc": auroc(c, positive),
        "ece": ece(c, positive, n_bins=n_bins),
    }
