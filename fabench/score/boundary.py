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

"""Boundary metrics (Plan 5.2-5.4).

We evaluate **both edges** of every matched phone: its onset and its offset
("dual-edge", Plan 5.1). In fully-tiled sequences an internal boundary is thus
counted twice (as one phone's offset and the next phone's onset); this weights
internal boundaries 2x relative to utterance-edge boundaries but does **not**
bias the mean, and the headline bootstrap resamples *utterances* (Plan 5.9), for
which within-utterance duplication is harmless. onset-only / offset-only views
are exposed for anyone preferring the single-count internal-boundary convention.

All times are seconds internally; the report converts to ms.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from fabench.schema import Interval

# Threshold-accuracy comparison tolerance (seconds). TA_tau is inclusive (<=);
# times come from sample indices so real differences are multiples of 1/sr
# (>=62.5 us at 16 kHz). 1 ns absorbs float-subtraction / non-representable-tau
# noise without masking any physically real difference.
TA_TOL_S = 1e-9

# Coarse manner classes for the per-type breakdown (Plan 5.4).
MANNER_CLASSES = (
    "silence",
    "stop",
    "fricative",  # fricative/affricate
    "nasal",
    "liquid",     # liquid/glide (approximant)
    "vowel",
)


@dataclass
class BoundaryError:
    """One matched boundary's error and context."""

    edge: str  # "onset" | "offset"
    gold_time: float
    hyp_time: float
    left_manner: str
    right_manner: str
    conf: float | None = None
    gold_phone_idx: int = -1  # index of the gold phone this edge belongs to

    @property
    def signed(self) -> float:
        """hyp - gold, seconds (positive => aligner lags)."""
        return self.hyp_time - self.gold_time

    @property
    def abs(self) -> float:
        return abs(self.hyp_time - self.gold_time)

    @property
    def type_key(self) -> tuple[str, str]:
        return (self.left_manner, self.right_manner)


def build_boundary_errors(
    matched: Sequence[tuple[int, int]],
    gold_phones: Sequence[Interval],
    hyp_phones: Sequence[Interval],
    manner_fn: Callable[[str], str],
    *,
    skip_silence_adjacent: bool = False,
) -> list[BoundaryError]:
    """Construct dual-edge boundary errors for a matched set.

    ``matched`` is a list of (gold_idx, hyp_idx). Manner context comes from the
    *gold* neighbours (the reference defines the boundary type). Per-boundary
    ``conf`` is inherited from the hyp phone.

    ``skip_silence_adjacent`` drops any boundary touching silence (a silence
    neighbour or the utterance edge). The MFA-2026 paper's manner taxonomy has no
    silence class, so its evaluation is over speech-to-speech boundaries only;
    including silence/edge boundaries (which are hard) otherwise inflates sharp
    aligners' MAE.
    """
    errs: list[BoundaryError] = []
    n_gold = len(gold_phones)

    def manner_at(idx: int) -> str:
        if idx < 0 or idx >= n_gold:
            return "silence"  # utterance edge behaves like silence
        return manner_fn(gold_phones[idx].label)

    def add(edge, gt, ht, lm, rm, conf, gi):
        if skip_silence_adjacent and (lm == "silence" or rm == "silence"):
            return
        errs.append(BoundaryError(edge, gt, ht, lm, rm, conf, gi))

    for gi, hj in matched:
        g = gold_phones[gi]
        h = hyp_phones[hj]
        conf = h.conf
        # onset: boundary between gold[gi-1] and gold[gi]
        add("onset", g.start, h.start, manner_at(gi - 1), manner_at(gi), conf, gi)
        # offset: boundary between gold[gi] and gold[gi+1]
        add("offset", g.end, h.end, manner_at(gi), manner_at(gi + 1), conf, gi)
    return errs


# --------------------------------------------------------------------------
# Scalar metrics over a pool of BoundaryError
# --------------------------------------------------------------------------
def _abs_array(errs: Sequence[BoundaryError]) -> np.ndarray:
    return np.array([e.abs for e in errs], dtype=float)


def _signed_array(errs: Sequence[BoundaryError]) -> np.ndarray:
    return np.array([e.signed for e in errs], dtype=float)


def mae(errs: Sequence[BoundaryError]) -> float:
    a = _abs_array(errs)
    return float(a.mean()) if a.size else float("nan")


def median_abs(errs: Sequence[BoundaryError]) -> float:
    a = _abs_array(errs)
    return float(np.median(a)) if a.size else float("nan")


def signed_mean(errs: Sequence[BoundaryError]) -> float:
    a = _signed_array(errs)
    return float(a.mean()) if a.size else float("nan")


def threshold_accuracy(errs: Sequence[BoundaryError], tau_s: float) -> float:
    """TA_tau = fraction of matched boundaries within tau seconds (Plan 5.3)."""
    a = _abs_array(errs)
    if not a.size:
        return float("nan")
    return float((a <= tau_s + TA_TOL_S).mean())


def summarize(
    errs: Sequence[BoundaryError], ta_thresholds_s: Sequence[float]
) -> dict:
    """Headline boundary stats for a pool of errors."""
    out = {
        "n": len(errs),
        "mae_s": mae(errs),
        "median_s": median_abs(errs),
        "signed_mean_s": signed_mean(errs),
    }
    for tau in ta_thresholds_s:
        out[f"ta_{round(tau * 1000)}ms"] = threshold_accuracy(errs, tau)
    return out


def per_type(
    errs: Sequence[BoundaryError],
    ta20_s: float = 0.020,
    min_n: int = 1,
) -> dict[tuple[str, str], dict]:
    """MAE + TA20 per (left_manner, right_manner) bucket (Plan 5.4).

    Cells with fewer than ``min_n`` boundaries are still reported but flagged
    ``underpowered`` (Plan 5.9).
    """
    buckets: dict[tuple[str, str], list[BoundaryError]] = {}
    for e in errs:
        buckets.setdefault(e.type_key, []).append(e)
    out = {}
    for key, es in sorted(buckets.items()):
        out[key] = {
            "n": len(es),
            "mae_s": mae(es),
            "ta": threshold_accuracy(es, ta20_s),  # at the primary tolerance
            "underpowered": len(es) < min_n,
        }
    return out


def onset_only(errs: Sequence[BoundaryError]) -> list[BoundaryError]:
    return [e for e in errs if e.edge == "onset"]


def offset_only(errs: Sequence[BoundaryError]) -> list[BoundaryError]:
    return [e for e in errs if e.edge == "offset"]
