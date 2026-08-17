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

"""Boundary-detection metrics: P / R / F1 at a tolerance, OS, and R-value.

WHY THESE EXIST ALONGSIDE MAE. MAE is defined on the *matched* path — pairs the
label alignment could line up — so a system that drops hard phones removes them
from its own average rather than being charged for them. These metrics use a
completely different pairing and close that hole:

  * MAE pairs by LABEL (Levenshtein over phone strings), then measures time.
  * These pair by TIME ALONE, within a tolerance, ignoring labels entirely.

The consequences are complementary, which is the point of reporting both:

  * a substitution is FREE here (right time, wrong name) but is excluded from
    FA-Bench's MAE, and
  * an insertion costs precision here, while in MAE it is only visible
    indirectly, through the displaced edges of its surviving neighbours.

R-value (Rasanen, Laine & Altosaar, Interspeech 2009,
DOI 10.21437/Interspeech.2009-538) exists specifically because hit rate and F1
can be inflated by proposing extra boundaries; it penalises over-segmentation
explicitly rather than letting recall pay for it.

STRICT MATCHING. One hypothesis boundary may satisfy at most one reference
boundary and vice versa. Strgar & Harwath (SLT 2022, arXiv:2211.01461) showed
the lenient alternative -- letting one predicted boundary count against several
references inside the tolerance -- moves reported precision by 3-4 points
supervised and 5-7 unsupervised, so the scheme must be stated with any number.
We implement STRICT, matched greedily in order of increasing distance, which is
optimal for the 1-D monotone case here.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# The field's default tolerance for phone-boundary detection (UnsupSeg,
# SegFeat, SCPC all report at 20 ms).
DEFAULT_TOL_S = 0.020


@dataclass(frozen=True)
class SegmentationScore:
    n_gold: int
    n_hyp: int
    hits: int
    tol_s: float

    @property
    def precision(self) -> float:
        return self.hits / self.n_hyp if self.n_hyp else float("nan")

    @property
    def recall(self) -> float:
        return self.hits / self.n_gold if self.n_gold else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if not (p > 0) or not (r > 0):
            return 0.0 if (self.n_gold or self.n_hyp) else float("nan")
        return 2 * p * r / (p + r)

    @property
    def os(self) -> float:
        """Over-segmentation = R/P - 1 = n_hyp/n_gold - 1.

        Positive means more boundaries proposed than exist. Defined from the
        counts directly so it is still meaningful when hits == 0.
        """
        return self.n_hyp / self.n_gold - 1.0 if self.n_gold else float("nan")

    @property
    def r_value(self) -> float:
        """1 - (|r1| + |r2|)/2. 1.0 is perfect; over-segmenting drives it down."""
        r = self.recall
        if math.isnan(r):
            return float("nan")
        os_ = self.os
        if math.isnan(os_):
            return float("nan")
        r1 = math.sqrt((1.0 - r) ** 2 + os_**2)
        r2 = (-os_ + r - 1.0) / math.sqrt(2.0)
        return 1.0 - (abs(r1) + abs(r2)) / 2.0

    def as_dict(self) -> dict:
        return {
            "n_gold_bnd": self.n_gold,
            "n_hyp_bnd": self.n_hyp,
            "hits": self.hits,
            "tol_ms": round(self.tol_s * 1000, 3),
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "os": self.os,
            "r_value": self.r_value,
        }


def count_hits(
    gold: Sequence[float], hyp: Sequence[float], tol_s: float = DEFAULT_TOL_S
) -> int:
    """Strict one-to-one hits: each side consumed at most once.

    Candidate pairs within tolerance are taken in order of increasing distance,
    so the closest available pairing wins and neither boundary can be reused.
    """
    g = sorted(gold)
    h = sorted(hyp)
    cands = []
    for i, gt in enumerate(g):
        for j, ht in enumerate(h):
            d = abs(ht - gt)
            if d <= tol_s:
                cands.append((d, i, j))
    cands.sort()
    used_g: set[int] = set()
    used_h: set[int] = set()
    hits = 0
    for _, i, j in cands:
        if i in used_g or j in used_h:
            continue
        used_g.add(i)
        used_h.add(j)
        hits += 1
    return hits


def boundaries_from_intervals(intervals, *, include_edges: bool = False) -> list[float]:
    """Distinct boundary times of a phone sequence.

    Internal transitions only by default: the utterance's outer edges are an
    artefact of where the file was cut, not something an aligner decided, and
    counting them inflates every system's recall equally.
    """
    if not intervals:
        return []
    ts = []
    for k, iv in enumerate(intervals):
        if include_edges or k > 0:
            ts.append(float(iv.start))
    if include_edges:
        ts.append(float(intervals[-1].end))
    out: list[float] = []
    for t in sorted(ts):
        if not out or abs(t - out[-1]) > 1e-9:
            out.append(t)
    return out


def score_segmentation(
    gold_intervals,
    hyp_intervals,
    *,
    tol_s: float = DEFAULT_TOL_S,
    include_edges: bool = False,
) -> SegmentationScore:
    g = boundaries_from_intervals(gold_intervals, include_edges=include_edges)
    h = boundaries_from_intervals(hyp_intervals, include_edges=include_edges)
    return SegmentationScore(
        n_gold=len(g), n_hyp=len(h), hits=count_hits(g, h, tol_s), tol_s=tol_s
    )
