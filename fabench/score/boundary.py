# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Boundary MAE (Plan 5.2).

Units are matched to the reference by label first, and a boundary is scored
when every unit beside it matched. Each reference boundary is counted once,
so the easy interior is not weighted twice against the utterance edges.

All times are seconds internally; the report converts to ms.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from fabench.schema import Interval

# Tolerance comparison guard (seconds). A hit within a width is inclusive
# (<=); times come from sample indices so real differences are multiples of
# 1/sr (>=62.5 us at 16 kHz). 1 ns absorbs float-subtraction /
# non-representable-width noise without masking any physically real difference.
TA_TOL_S = 1e-9


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
    def abs(self) -> float:
        return abs(self.hyp_time - self.gold_time)


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
    pair = dict(matched)

    def manner_at(idx) -> str:
        if idx is None or idx < 0 or idx >= n_gold:
            return "silence"  # utterance edge behaves like silence
        return manner_fn(gold_phones[idx].label)

    def add(edge, gt, ht, lm, rm, conf, gi):
        if skip_silence_adjacent and (lm == "silence" or rm == "silence"):
            return
        errs.append(BoundaryError(edge, gt, ht, lm, rm, conf, gi))

    # ONE ENTRY PER REFERENCE BOUNDARY. This used to walk the matched units and
    # charge each one's onset and its offset, so a boundary two contiguous
    # units share went in twice with the same error. TIMIT's phone tier tiles
    # the utterance, so that was every interior boundary; on the word tier it
    # is 90 to 95 percent of them. The duplicate gave the easy interior twice
    # the weight of the two utterance edges, which are the hardest boundaries
    # the benchmark has, and pulled the reported mean below the truth.
    #
    # A boundary is scored when EVERY unit beside it matched. An utterance edge
    # and a boundary beside an interior gap have one unit beside them, so that
    # one decides; silence is not a unit and matches trivially. This is the
    # rule Boundary F1 uses, so the two metrics now select the same boundaries
    # and differ only in what they do with them.
    #
    # `edge` says which side of its own unit the boundary sits on, and after
    # deduplication that is the left unit's offset wherever a left unit exists.
    sides: dict[float, list] = {}
    for i, g in enumerate(gold_phones):
        sides.setdefault(round(g.start, 9), [None, None])[1] = i
        sides.setdefault(round(g.end, 9), [None, None])[0] = i
    for left, right in sides.values():
        near = [i for i in (left, right) if i is not None]
        if not all(i in pair for i in near):
            continue
        if left is not None:
            g, h, gi, edge = gold_phones[left], hyp_phones[pair[left]], left, "offset"
            gt, ht = g.end, h.end
            lm, rm = manner_at(left), manner_at(right if right is not None else left + 1)
        else:
            g, h, gi, edge = gold_phones[right], hyp_phones[pair[right]], right, "onset"
            gt, ht = g.start, h.start
            lm, rm = manner_at(right - 1), manner_at(right)
        add(edge, gt, ht, lm, rm, h.conf, gi)
    return errs


# --------------------------------------------------------------------------
# Scalar metrics over a pool of BoundaryError
# --------------------------------------------------------------------------
def _abs_array(errs: Sequence[BoundaryError]) -> np.ndarray:
    return np.array([e.abs for e in errs], dtype=float)


def mae(errs: Sequence[BoundaryError]) -> float:
    a = _abs_array(errs)
    return float(a.mean()) if a.size else float("nan")
