# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Boundary F1 at 20 ms with the labels checked, `f1_all`.

WHY THIS EXISTS ALONGSIDE MAE. MAE is defined on the *matched* path, the pairs
the label alignment could line up, so a system that drops hard units removes
them from its own average rather than being charged for them. This F1 keeps
every reference boundary in its denominator, the two utterance edges included,
and every system boundary in its other one, so a dropped unit costs recall and
an inserted one costs precision.

A HIT NEEDS BOTH. A boundary scores only when the units on both sides of it
are matched by label, silence matching silence at an edge, and when a system
boundary of the same kind lies within 20 ms. So a boundary placed at the right
moment beside the wrong word is a miss.

STRICT MATCHING. One hypothesis boundary may satisfy at most one reference
boundary and vice versa. Strgar & Harwath (SLT 2022, arXiv:2211.01461) showed
the lenient alternative -- letting one predicted boundary count against several
references inside the tolerance -- moves reported precision by 3-4 points
supervised and 5-7 unsupervised, so the scheme must be stated with any number.
We implement STRICT, matched greedily in order of increasing distance, which is
optimal for the 1-D monotone case here.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The F1 tolerance. 20 ms is what the segmentation literature reports (UnsupSeg,
#: SegFeat, SCPC) and what the paper's tables print.
F1_TOL_S = 0.020


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


def hits_by_tol_pairs(
    gold: Sequence[float], hyp: Sequence[float], tols_s=(F1_TOL_S,)
) -> dict[int, int]:
    """Strict one-to-one hits at each width in ``tols_s``, keyed by the width
    in whole ms, each side consumed at most once and the closest pair first.

    The greedy takes candidate pairs in order of increasing distance, so a run
    at the widest tolerance chooses, among the pairs closer than a narrower
    one, exactly what a run at that narrower tolerance would choose. The pairs
    it adds beyond that width come later and cannot displace them. So one run
    at the widest width answers every width.
    """
    if not tols_s:
        return {}
    widest = max(tols_s)
    g = sorted(gold)
    h = sorted(hyp)
    # Only the hypothesis boundaries inside the window around a reference one
    # can pair with it, and both sides are sorted, so the window's left edge
    # only moves forward. An all-pairs scan is quadratic in the utterance,
    # which put hours on a Buckeye rescore.
    cands = []
    lo = 0
    for i, gt in enumerate(g):
        while lo < len(h) and h[lo] < gt - widest:
            lo += 1
        j = lo
        while j < len(h) and h[j] <= gt + widest:
            cands.append((abs(h[j] - gt), i, j))
            j += 1
    cands.sort()
    used_g: set[int] = set()
    used_h: set[int] = set()
    dists: list[float] = []
    for d, i, j in cands:
        if i in used_g or j in used_h:
            continue
        used_g.add(i)
        used_h.add(j)
        dists.append(d)
    return {round(t * 1000): sum(1 for d in dists if d <= t) for t in tols_s}


def _context_flags(words, matched, units, unit_matched=None):
    """The units a context-grouped metric takes its boundaries from, and per
    unit whether it counts as matched. On the word tier the units are the
    words and the flag is the word's own. On the phone tier the flag is the
    phone's own when ``unit_matched`` is given, the set of unit indices the
    phone alignment matched, which is the rule the word tier already applies
    and the one the paper states. Without it the flag is that of the word
    holding the phone's midpoint, and a phone inside no word, a pause, counts
    as silence, which matches. That inherited mode is kept for callers that
    want the transcript's classes on phone boundaries; on Track 1 it marks
    every phone matched and the class view collapses to a time-only match."""
    if units is None:
        return words, [i in matched for i in range(len(words))]
    if unit_matched is not None:
        um = set(unit_matched)
        return units, [i in um for i in range(len(units))]
    out = []
    for u in units:
        mid = (float(u.start) + float(u.end)) / 2
        k = None
        for i, w in enumerate(words):
            if float(w.start) <= mid < float(w.end) or (float(w.start) == float(w.end) == mid):
                k = i
                break
        out.append(True if k is None else (k in matched))
    return units, out


#: The boundary classes, a partition of every boundary of an utterance.
#: ``int_*`` are the boundaries between two units, ``start_ok`` and ``end_ok``
#: the utterance edges whose one word is matched, and ``edge_bad`` an edge
#: whose word is not.
CTX_CLASSES = ("int_both", "int_one", "int_none", "start_ok", "end_ok", "edge_bad")


def _ctx_times(units, fl):
    """[(class, time)] over the start edge, the interior and the end edge,
    coincident times collapsed within a class."""
    n = len(units)
    if n == 0:
        return []
    out = [("start_ok" if fl[0] else "edge_bad", float(units[0].start))]
    for i in range(1, n):
        k = int(fl[i - 1]) + int(fl[i])
        out.append((("int_none", "int_one", "int_both")[k], float(units[i].start)))
    out.append(("end_ok" if fl[-1] else "edge_bad", float(units[-1].end)))
    seen, kept = set(), []
    for cls, t in out:
        key = (cls, round(t, 6))
        if key in seen:
            continue
        seen.add(key)
        kept.append((cls, t))
    return kept


#: The classes that can score in `f1_all`, every boundary with a matched unit on
#: each side, silence counting as matched.
BOTH = ("int_both", "start_ok", "end_ok")


def f1_all(
    gold_words, hyp_words, matched_word_pairs, gold_units=None, hyp_units=None,
    gold_matched=None, gold_unit_matched=None, hyp_unit_matched=None,
    tol_s=F1_TOL_S,
) -> dict:
    """The label-checked F1 counts of one utterance, ``{"n_gold", "n_hyp", "hits"}``.

    Every boundary of the utterance is in a denominator, the edges included,
    and only a boundary in `BOTH` can score, so a boundary missed for
    misreading the units around it is charged exactly like one put in the
    wrong place. Hits pair the reference and system boundaries of `BOTH`
    one-to-one within ``tol_s``, closest first. The F1 is
    ``2 * hits / (n_gold + n_hyp)``.

    The recognized words are aligned to the reference words, and a word is
    matched when it is label-matched to an aligned word on the other side.
    ``gold_matched``, when given, is the set of matched reference word indices
    to class the reference side by, in place of the one read off
    ``matched_word_pairs``. The scorer passes the words the system was GIVEN,
    so systems that re-tokenise or drop a word still share reference classes.

    THE PHONE TIER IS CLASSED BY ITS OWN LABELS. With ``gold_units`` and
    ``hyp_units`` given, the boundaries scored are those units' boundaries,
    and with ``gold_unit_matched`` and ``hyp_unit_matched``, the sets of unit
    indices the phone alignment label-matched, each unit's flag is its own.
    Without those sets each unit inherits the match status of the word
    containing its midpoint.

    Coincident boundary times count once.
    """
    g_matched = (set(gold_matched) if gold_matched is not None
                 else {gi for gi, _ in matched_word_pairs})
    h_matched = {hj for _, hj in matched_word_pairs}
    gu, gf = _context_flags(gold_words, g_matched, gold_units, gold_unit_matched)
    hu, hf = _context_flags(hyp_words, h_matched, hyp_units, hyp_unit_matched)
    gb, hb = _ctx_times(gu, gf), _ctx_times(hu, hf)

    def times(b, keep):
        return sorted({round(t, 6) for c, t in b if c in keep})

    ms = round(tol_s * 1000)
    return {"n_gold": len(times(gb, CTX_CLASSES)), "n_hyp": len(times(hb, CTX_CLASSES)),
            "hits": hits_by_tol_pairs(times(gb, BOTH), times(hb, BOTH), (tol_s,))[ms]}
