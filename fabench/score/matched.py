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

"""Matched-set construction (Plan 5.1).

Align a hypothesis phone/word sequence to gold via a monotonic global alignment
(Needleman-Wunsch) over **normalized canonical labels**. A pair *matches* iff the
canonical labels are equal and order is preserved. Boundary metrics are computed
over matched pairs only; unmatched gold = deletions (hurt recall/ARR), unmatched
hyp = insertions.

Labels passed in here are assumed already canonicalized (see fabench.normalize),
so this module is dependency-free and unit-testable with plain letters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# NW scores. Match must beat two gaps so equal labels are always paired when
# order allows; mismatch(==sub) beats two gaps so non-equal aligned labels
# collapse to a single substitution (they are not counted as matches either way,
# so this does not affect the matched-pair count).
MATCH = 2
MISMATCH = -1
GAP = -1


@dataclass
class Alignment:
    """One monotonic alignment. ``pairs`` lists (gold_idx, hyp_idx); a None on
    either side is an indel."""

    pairs: list[tuple[int | None, int | None]]

    def matched(self, gold_labels: Sequence[str], hyp_labels: Sequence[str]) -> list[tuple[int, int]]:
        """Aligned pairs whose canonical labels are equal (the matched set)."""
        out = []
        for gi, hj in self.pairs:
            if gi is not None and hj is not None and gold_labels[gi] == hyp_labels[hj]:
                out.append((gi, hj))
        return out


def nw_align(a: Sequence[str], b: Sequence[str]) -> Alignment:
    """Needleman-Wunsch global alignment maximizing match score.

    Deterministic traceback: on ties prefer diagonal (align), then up (consume a
    = gold-only/deletion), then left (consume b = hyp-only/insertion).
    """
    n, m = len(a), len(b)
    # dp[i][j] = best score aligning a[:i] with b[:j].
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i * GAP
    for j in range(1, m + 1):
        dp[0][j] = j * GAP
    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            s = MATCH if ai == b[j - 1] else MISMATCH
            dp[i][j] = max(
                dp[i - 1][j - 1] + s,  # align/sub
                dp[i - 1][j] + GAP,    # a[i-1] unaligned (deletion)
                dp[i][j - 1] + GAP,    # b[j-1] unaligned (insertion)
            )

    # Traceback.
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s = MATCH if a[i - 1] == b[j - 1] else MISMATCH
            if dp[i][j] == dp[i - 1][j - 1] + s:
                pairs.append((i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + GAP:
            pairs.append((i - 1, None))
            i -= 1
            continue
        # j > 0
        pairs.append((None, j - 1))
        j -= 1
    pairs.reverse()
    return Alignment(pairs=pairs)


def matched_indices(
    gold_labels: Sequence[str], hyp_labels: Sequence[str]
) -> list[tuple[int, int]]:
    """Convenience: canonical-label sequences -> list of matched (gold, hyp) idx."""
    aln = nw_align(gold_labels, hyp_labels)
    return aln.matched(gold_labels, hyp_labels)


def boundary_aware_align(
    gold_ivs,
    gcanon: Sequence[str],
    hyp_ivs,
    hcanon: Sequence[str],
    manner_fn,
    *,
    lam: float = 2.0,
    p_manner: float = 0.5,
    p_mismatch: float = 2.0,
    gap: float = 1.0,
) -> Alignment:
    """Modified-Levenshtein alignment (arXiv:2606.18466): the substitution cost
    combines **phone-label accuracy** with **boundary distance**, so among monotonic
    alignments it prefers pairing phones that agree (exact label > same manner >
    mismatch) *and* whose start/end boundaries sit closest in time. This breaks
    same-label ties toward the time-nearest candidate — the effect a label-only
    aligner misses. Returns an :class:`Alignment`, same shape as ``nw_align``.

    Cost of aligning gold[i]~hyp[j] = label_penalty + ``lam`` * (|Δstart| + |Δend|),
    where label_penalty is 0 (exact label), ``p_manner`` (same manner class), or
    ``p_mismatch`` (different manner). Indels cost ``gap``. Minimized by DP.
    """
    n, m = len(gold_ivs), len(hyp_ivs)

    def sub_cost(i: int, j: int) -> float:
        gi, hj = gcanon[i], hcanon[j]
        if gi == hj:
            lp = 0.0
        elif manner_fn(gi) == manner_fn(hj):
            lp = p_manner
        else:
            lp = p_mismatch
        d = abs(gold_ivs[i].start - hyp_ivs[j].start) + abs(gold_ivs[i].end - hyp_ivs[j].end)
        return lp + lam * d

    # dp[i][j] = min edit cost of gold[:i] vs hyp[:j]; bp = backpointer.
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bp = [[0] * (m + 1) for _ in range(n + 1)]  # 0=align, 1=gold-only, 2=hyp-only
    for i in range(1, n + 1):
        dp[i][0] = i * gap
        bp[i][0] = 1
    for j in range(1, m + 1):
        dp[0][j] = j * gap
        bp[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = dp[i - 1][j - 1] + sub_cost(i - 1, j - 1)
            up = dp[i - 1][j] + gap
            left = dp[i][j - 1] + gap
            best = min(diag, up, left)
            dp[i][j] = best
            bp[i][j] = 0 if best == diag else (1 if best == up else 2)  # prefer align

    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        move = bp[i][j]
        if move == 0:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif move == 1:
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return Alignment(pairs=pairs)


def recall_counts(
    gold_labels: Sequence[str], hyp_labels: Sequence[str]
) -> tuple[int, int, int]:
    """Return (n_matched, n_gold, n_hyp) for ARR / InsertRate (Plan 5.6)."""
    m = len(matched_indices(gold_labels, hyp_labels))
    return m, len(gold_labels), len(hyp_labels)


def edit_counts(
    gold_labels: Sequence[str], hyp_labels: Sequence[str]
) -> tuple[int, int, int, int]:
    """Return (n_match, n_sub, n_del, n_ins) from one NW alignment.

    ARR says how many gold phones went unmatched but not WHY, and the two
    reasons are different failures: a SUBSTITUTION still contributes a boundary
    at roughly the right place with the wrong label, while a DELETION
    contributes no boundary at all. ARR collapses them into one number.

    The decomposition is exact and total on the gold side:

        n_match + n_sub + n_del == n_gold

    so match% + sub% + del% == 100%, and match% is exactly ARR. Insertions have
    no gold counterpart; they are normalised by the gold count as well (the
    PER/WER convention), so sub+del+ins can exceed 100%.
    """
    aln = nw_align(gold_labels, hyp_labels)
    n_match = n_sub = n_del = n_ins = 0
    for gi, hj in aln.pairs:
        if gi is None:
            n_ins += 1
        elif hj is None:
            n_del += 1
        elif gold_labels[gi] == hyp_labels[hj]:
            n_match += 1
        else:
            n_sub += 1
    return n_match, n_sub, n_del, n_ins
