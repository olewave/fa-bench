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

#: The widths F1 and tolerance accuracy are BOTH swept over, so the two can be
#: read against each other at one width. 20 ms is here because it is what the
#: segmentation literature reports and what the paper's table shows; 25 ms is
#: here because it is tolerance accuracy's primary. Dropping either would leave
#: a width where only one of the two metrics exists, which is the gap that made
#: the F1-versus-TA comparison impossible to state.
SWEEP_TOL_S = (0.010, 0.020, 0.025, 0.050, 0.100)


def hits_by_tolerance(gold, hyp, tols_s=SWEEP_TOL_S) -> dict[int, int]:
    """Hit count at each width, keyed by the width in whole ms.

    Only `hits` depends on the tolerance. n_gold and n_hyp do not, so the
    caller pools those once and pairs them with whichever hit count it wants.
    """
    return {round(t * 1000): count_hits(gold, hyp, t) for t in tols_s}


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


def hits_by_tol_pairs(
    gold: Sequence[float], hyp: Sequence[float], tols_s=SWEEP_TOL_S
) -> dict[int, int]:
    """`count_hits` at several tolerances in one pass.

    The greedy takes candidate pairs in order of increasing distance, so a run
    at the widest tolerance chooses, among the pairs closer than a narrower
    one, exactly what a run at that narrower tolerance would choose. The pairs
    it adds beyond that width come later and cannot displace them. So one run
    at the widest width answers every width, which is what makes a five-width
    sweep over six boundary classes affordable inside the scorer.
    """
    if not tols_s:
        return {}
    widest = max(tols_s)
    g = sorted(gold)
    h = sorted(hyp)
    # Only the hypothesis boundaries inside the window around a reference one
    # can pair with it, and both sides are sorted, so the window's left edge
    # only moves forward. The all-pairs scan this replaces is quadratic in the
    # utterance, and the scorer runs it once per boundary class per tier per
    # utterance, which put hours on a Buckeye rescore.
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


def labelled_hits_by_tol(
    gold_ivs, hyp_ivs, pairs, tols_s=SWEEP_TOL_S
) -> dict[int, int]:
    """Hits that also agree about WHICH boundary was hit, keyed by width in ms.

    WHY. A time-only hit says a hypothesis boundary landed within the tolerance
    of SOME reference boundary. It does not say the system found *that*
    boundary. `evals/analyze_boundary_pairing.py` measured the price on Track 1,
    where hypothesis unit i corresponds to gold unit i by construction: 1% of
    Olign's word hits credit a neighbouring boundary on Buckeye and 35% of
    NeMo-FA's. So a time-only F1 gap between a good and a coarse system
    understates the real one.

    THE RULE, and it checks BOTH SIDES. A boundary is the thing between two
    units, so it is identified by the pair of units it separates. Gold boundary
    ``i`` sits between gold units ``i-1`` and ``i``; it is hit when some
    hypothesis boundary ``j`` is within the tolerance AND ``pairs`` lines up
    ``i-1`` with ``j-1`` and ``i`` with ``j``. Checking one side credits a
    boundary that has the right word on the left and the wrong one on the
    right, which is the case this metric exists to catch. kalpy's own
    boundary extraction takes the same view: it scores no boundary whose
    neighbouring alignment step is an insertion or a deletion.

    The correspondence is one-to-one for free. ``pairs`` is monotonic and
    injective, so each gold boundary reaches at most one hypothesis boundary
    and no two reach the same one. No greedy closest-first pass is needed, and
    unlike `count_hits` this cannot pair across ranks in the first place.

    ZERO-LENGTH UNITS. `boundaries_from_intervals` dedups coincident times, so
    a unit whose start equals its predecessor's contributes no boundary and is
    not in the denominator. This has to skip it for the same reason, or the
    count is taken against a denominator that never included it: FALCON, which
    is handed the gold phone sequence and so matches every label, scored a
    label-checked $F_1$ of 0.628 against a time-only 0.581, which is
    impossible for a rule that can only withdraw credit.

    ``pairs`` selects the variant. The label-equal set (``Alignment.matched``)
    gives the STRICT score, where a substitution costs the two boundaries
    beside it. The full aligned set (``Alignment.aligned``) gives the
    POSITIONAL one, which asks only that the units correspond. On Track 1 the
    two coincide, because the transcript is the reference.
    """
    g2h = dict(pairs)
    dists = []
    for i in range(1, len(gold_ivs)):
        j, j_prev = g2h.get(i), g2h.get(i - 1)
        # j_prev + 1 != j means an insertion sits between the two hypothesis
        # units, so the hypothesis has an extra boundary there and no single
        # one of its boundaries is this gold boundary.
        if j is None or j_prev is None or j != j_prev + 1:
            continue
        # Neither side may be a boundary that the dedup above removed.
        if abs(float(gold_ivs[i].start) - float(gold_ivs[i - 1].start)) <= 1e-9:
            continue
        if abs(float(hyp_ivs[j].start) - float(hyp_ivs[j - 1].start)) <= 1e-9:
            continue
        dists.append(abs(float(hyp_ivs[j].start) - float(gold_ivs[i].start)))
    return {round(t * 1000): sum(1 for d in dists if d <= t) for t in tols_s}


def labelled_hits_by_class(
    gold_ivs, hyp_ivs, aligned_pairs, matched_pairs, tols_s=SWEEP_TOL_S,
    include_edges: bool = False,
) -> dict[str, dict]:
    """The label-checked hits split by how many of a boundary's neighbours
    carry the WRONG label, keyed ``both`` (no mismatched neighbour), ``one``
    and ``none`` (two mismatched neighbours).

    EDGES. The paper's F1 scores the boundaries between two units and leaves
    the first unit's start and the last unit's end out, numerator and
    denominator alike. With ``include_edges`` those two are scored as well,
    and since an edge has one neighbour it is classed by that one: the edge
    word right puts it in ``both``, the edge word substituted in ``one``. An
    edge only answers to the hypothesis edge, so a hypothesis that starts or
    ends with an inserted unit leaves the gold edge with no counterpart, as a
    deletion does inside. The count of edges taken in is returned under
    ``edges`` so a caller can quote their weight; it is not a fourth class.

    WHY. `labelled_hits_by_tol` with the matched set credits a boundary only
    when the unit on each side of it is the aligned, same-labelled unit, and
    with the aligned set it credits any boundary whose two neighbours merely
    correspond. The gap between the two is every boundary that sits beside a
    substituted unit, and this splits that gap in two: a boundary with the
    right unit on ONE side and a substitution on the other, and a boundary
    between TWO substitutions. On the word tier the first is a misread word
    pulling its neighbour's boundary, on the phone tier it is what a
    dictionary pronunciation costs against a talker's realisation. The three
    classes partition the boundaries that have a single hypothesis boundary
    opposite them at all; a boundary beside an insertion or a deletion has
    none and is in no class, though it stays in the gold denominator.

    Each class reports ``n``, its gold boundaries, and ``hits``, those within
    each tolerance, so a caller can quote the class's own accuracy or
    accumulate the classes into the strict, the half-matched and the
    positional F1 in turn. Zero-length units are skipped on the same terms
    as in `labelled_hits_by_tol`.
    """
    g2h = dict(aligned_pairs)
    mset = set(matched_pairs)
    out = {c: {"n": 0, "dists": []} for c in ("both", "one", "none")}
    for i in range(1, len(gold_ivs)):
        j, j_prev = g2h.get(i), g2h.get(i - 1)
        if j is None or j_prev is None or j != j_prev + 1:
            continue
        if abs(float(gold_ivs[i].start) - float(gold_ivs[i - 1].start)) <= 1e-9:
            continue
        if abs(float(hyp_ivs[j].start) - float(hyp_ivs[j - 1].start)) <= 1e-9:
            continue
        k = ((i - 1, j_prev) in mset) + ((i, j) in mset)
        c = ("none", "one", "both")[k]
        out[c]["n"] += 1
        out[c]["dists"].append(abs(float(hyp_ivs[j].start) - float(gold_ivs[i].start)))
    edges = {"n": 0, "dists": []}
    if include_edges and gold_ivs and hyp_ivs:
        n_g, n_h = len(gold_ivs), len(hyp_ivs)
        # the utterance-initial boundary: the first gold unit against the
        # first hypothesis unit, and only then
        if g2h.get(0) == 0:
            c = "both" if (0, 0) in mset else "one"
            d = abs(float(hyp_ivs[0].start) - float(gold_ivs[0].start))
            out[c]["n"] += 1; out[c]["dists"].append(d); edges["n"] += 1; edges["dists"].append(d)
        # the utterance-final boundary: last against last
        if g2h.get(n_g - 1) == n_h - 1 and n_g > 0:
            c = "both" if (n_g - 1, n_h - 1) in mset else "one"
            d = abs(float(hyp_ivs[-1].end) - float(gold_ivs[-1].end))
            out[c]["n"] += 1; out[c]["dists"].append(d); edges["n"] += 1; edges["dists"].append(d)
    for c, rec in out.items():
        d = rec.pop("dists")
        rec["hits"] = {round(t * 1000): sum(1 for x in d if x <= t) for t in tols_s}
    d = edges.pop("dists")
    edges["hits"] = {round(t * 1000): sum(1 for x in d if x <= t) for t in tols_s}
    out["edges"] = edges
    return out


def labelled_f1_by_category(
    gold_ivs, hyp_ivs, aligned_pairs, matched_pairs, tols_s=SWEEP_TOL_S
) -> dict[str, dict]:
    """Precision, recall and F1 counts in three disjoint categories of boundary,
    keyed ``both``, ``one`` and ``none`` by how many of the boundary's two
    sides carry a matched unit.

    A SIDE IS MATCHED when the unit on it is label-matched to an aligned unit
    on the other tier. A substituted unit is an unmatched side, and so is a
    deleted or an inserted one, since there is no same-labelled unit opposite
    it either. The utterance edges are boundaries too, between silence and the
    first or last unit, and silence matches silence, so an edge is classed by
    its one real neighbour: the edge word right puts it in ``both``, the edge
    word wrong in ``one``, and an edge can never be ``none``.

    Both tiers are categorised the same way, gold boundaries by their gold
    neighbours and hypothesis boundaries by their hypothesis neighbours, so
    each category has its own denominators. A HIT is a gold boundary whose
    two neighbours are aligned to two consecutive hypothesis units, which
    puts one hypothesis boundary opposite it, within the tolerance; an edge
    hits through the hypothesis edge. A hit is in the same category on both
    tiers, because aligned units share their match status. So a boundary
    beside a deleted word is a miss charged to recall in ``one`` or ``none``,
    and a boundary beside an inserted word a false alarm charged to precision
    there, which is what an F1 per category has to do to remain an F1.

    Returns ``{category: {"n_gold", "n_hyp", "hits": {ms: count}}}``.
    Zero-length units contribute no boundary, as everywhere else in this file.
    """
    g_matched = {gi for gi, _ in matched_pairs}
    h_matched = {hj for _, hj in matched_pairs}
    g2h = dict(aligned_pairs)
    cats = ("none", "one", "both")

    def sides(ivs, matched, k):
        """Categories of the boundaries of one tier, start-edge, interior,
        end-edge, as a list of (category, time) with zero-length units
        skipped."""
        out = []
        n = len(ivs)
        if n == 0:
            return out
        out.append((cats[1 + (0 in matched)], float(ivs[0].start), "start"))
        for i in range(1, n):
            if abs(float(ivs[i].start) - float(ivs[i - 1].start)) <= 1e-9:
                continue
            out.append((cats[(i - 1 in matched) + (i in matched)], float(ivs[i].start), i))
        out.append((cats[1 + (n - 1 in matched)], float(ivs[-1].end), "end"))
        return out

    res = {c: {"n_gold": 0, "n_hyp": 0, "dists": []} for c in cats}
    for c, _, _ in sides(hyp_ivs, h_matched, None):
        res[c]["n_hyp"] += 1
    n_g, n_h = len(gold_ivs), len(hyp_ivs)
    for c, t, where in sides(gold_ivs, g_matched, None):
        res[c]["n_gold"] += 1
        if where == "start":
            if n_h and g2h.get(0) == 0:
                res[c]["dists"].append(abs(float(hyp_ivs[0].start) - t))
        elif where == "end":
            if n_h and g2h.get(n_g - 1) == n_h - 1:
                res[c]["dists"].append(abs(float(hyp_ivs[-1].end) - t))
        else:
            i = where
            j, j_prev = g2h.get(i), g2h.get(i - 1)
            if j is None or j_prev is None or j != j_prev + 1:
                continue
            if abs(float(hyp_ivs[j].start) - float(hyp_ivs[j - 1].start)) <= 1e-9:
                continue
            res[c]["dists"].append(abs(float(hyp_ivs[j].start) - t))
    for c in cats:
        d = res[c].pop("dists")
        res[c]["hits"] = {round(tol * 1000): sum(1 for x in d if x <= tol) for tol in tols_s}
    return res


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

#: Named unions of those classes. ``both`` is every boundary with a matched
#: word on each side, silence counting as matched, which is the only set that
#: can score in ``all``. ``rest`` is the catch-all of the five-way reading,
#: the interior boundaries with nothing matched together with the edges whose
#: word is wrong.
CTX_VIEWS = {
    "both": ("int_both", "start_ok", "end_ok"),
    "one": ("int_one", "edge_bad"),
    "none": ("int_none",),
    "rest": ("int_none", "edge_bad"),
}


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


def f1_by_word_context(
    gold_words, hyp_words, matched_word_pairs, gold_units=None, hyp_units=None,
    tols_s=SWEEP_TOL_S, gold_matched=None,
    gold_unit_matched=None, hyp_unit_matched=None,
) -> dict[str, dict]:
    """Boundary F1 by recognition context, the classes fixed by the WORD
    alignment so every system scored on the same transcript sees the same
    reference classes.

    THE CLASSES ARE A PROPERTY OF THE TRANSCRIPT, NOT OF THE SYSTEM. The
    recognized words are aligned to the reference words, a word is matched
    when it is label-matched to an aligned word on the other side, and a
    substituted, deleted or inserted word is not. Every boundary then takes a
    class from the words around it, ``CTX_CLASSES``. The interior boundaries
    split three ways by how many of their two words are matched. The two
    utterance edges stand against silence, which matches silence, so an edge
    answers to its one word and splits speech onset from speech offset,
    ``start_ok`` and ``end_ok`` when that word is matched and ``edge_bad``
    when it is not. Onset and offset are kept apart because a system that
    finds the start of speech need not find the end of it, and an average over
    both hides which one it missed.

    THE PHONE TIER IS CLASSED BY ITS OWN LABELS. With ``gold_units`` and
    ``hyp_units`` given, the boundaries scored are those units' boundaries.
    With ``gold_unit_matched`` and ``hyp_unit_matched`` also given, the sets
    of unit indices the phone alignment label-matched, each unit's flag is its
    own, so a phone the system named wrongly unmatches the boundaries beside
    it exactly as a misrecognized word does on the word tier. This is what
    the scorer passes. Without those sets each unit inherits the match status
    of the word containing its midpoint, a unit inside no word counting as
    silence, which on a given transcript marks every phone matched.

    HITS ARE BY TIME, WITHIN THE CLASS. The reference and recognized times of
    a class are paired one-to-one within the tolerance, closest first, as
    `count_hits` does. The classes have already done the label work, every
    boundary in one standing on the same kinds of neighbour, so the hit rule
    has no labels left to check. What it gives up is which boundary answered,
    for which see `labelled_f1_by_category`.

    ``gold_matched``, when given, is the set of matched reference word indices
    to class the reference side by, in place of the one read off
    ``matched_word_pairs``. A caller uses it to class the reference by the
    transcript the system was GIVEN rather than by what the system returned,
    so systems that re-tokenise or drop a word still share reference classes
    exactly; the recognized side is still classed by the system's own words.

    Returns ``{key: {"n_gold", "n_hyp", "hits": {ms: count}}}`` for each of
    ``CTX_CLASSES``, for each union in ``CTX_VIEWS``, and for two
    whole-utterance keys.

    ``all`` is the bottom line. Every boundary of the utterance is in the
    denominator, the edges included, and only ``both`` can score, so a
    boundary missed for misreading the words around it is charged exactly
    like one put in the wrong place.

    ``pool`` drops the label condition instead of the classes. It pairs every
    reference boundary against every recognized one, so a reference boundary
    may be answered by a boundary the classing filed elsewhere, which makes it
    the ceiling the classes sit under. It is not their average.

    Coincident boundary times count once within a class and once in a union,
    as `boundaries_from_intervals` counts them.
    """
    g_matched = set(gold_matched) if gold_matched is not None else {gi for gi, _ in matched_word_pairs}
    h_matched = {hj for _, hj in matched_word_pairs}
    gu, gf = _context_flags(gold_words, g_matched, gold_units, gold_unit_matched)
    hu, hf = _context_flags(hyp_words, h_matched, hyp_units, hyp_unit_matched)
    gb, hb = _ctx_times(gu, gf), _ctx_times(hu, hf)

    def entry(keep):
        gt = sorted({round(t, 6) for c, t in gb if c in keep})
        ht = sorted({round(t, 6) for c, t in hb if c in keep})
        return {"n_gold": len(gt), "n_hyp": len(ht),
                "hits": hits_by_tol_pairs(gt, ht, tols_s)}

    res = {c: entry((c,)) for c in CTX_CLASSES}
    for name, keep in CTX_VIEWS.items():
        res[name] = entry(keep)
    res["pool"] = entry(CTX_CLASSES)
    res["all"] = {"n_gold": res["pool"]["n_gold"], "n_hyp": res["pool"]["n_hyp"],
                  "hits": dict(res["both"]["hits"])}
    return res


def mae_by_word_context(
    gold_words, hyp_words, matched_word_pairs, aligned_pairs,
    gold_units=None, hyp_units=None, gold_matched=None, gold_unit_matched=None,
) -> dict[str, dict]:
    """Boundary MAE in the classes of `f1_by_word_context`, on the same
    reference classing, the pairs taken from the alignment rather than by time.

    THE PAIRS ARE THE ALIGNMENT'S, SUBSTITUTIONS INCLUDED. The paper's MAE
    takes the onset and the offset of every matched unit, and a unit the
    system named wrongly is off that path, so a boundary with nothing matched
    beside it would carry no error at all. Here every ALIGNED pair contributes
    its two edges, matched and substituted alike, and each edge is charged to
    the reference boundary it sits on, in that boundary's class. A deleted
    reference unit has no partner and contributes nothing, as in the paper's
    MAE. Where every boundary is ``int_both`` or an ``_ok`` edge, which is
    Track 1, the ``both`` figure is the paper's MAE exactly, edges and all.

    ``aligned_pairs`` are (gold, hyp) index pairs over the units scored, from
    `Alignment.aligned`, over the words when ``gold_units`` is None and over
    the units otherwise.

    Returns ``{key: {"n": edges, "sum_abs": seconds}}`` for each of
    ``CTX_CLASSES``, each union in ``CTX_VIEWS`` and ``all``, which is every
    edge. The caller divides, so utterances can be pooled before the mean is
    taken. There is no ``pool`` here; it would equal ``all``, the pairing
    being the alignment's either way.
    """
    g_matched = set(gold_matched) if gold_matched is not None else {gi for gi, _ in matched_word_pairs}
    gu, gf = _context_flags(gold_words, g_matched, gold_units, gold_unit_matched)
    hu = hyp_words if hyp_units is None else hyp_units
    n = len(gu)
    res = {k: {"n": 0, "sum_abs": 0.0} for k in CTX_CLASSES}

    def cls_at(i, edge):
        if edge == "start":
            return "start_ok" if gf[0] else "edge_bad"
        if edge == "end":
            return "end_ok" if gf[-1] else "edge_bad"
        return ("int_none", "int_one", "int_both")[int(gf[i - 1]) + int(gf[i])]

    for gi, hj in aligned_pairs:
        g, h = gu[gi], hu[hj]
        on = cls_at(gi, "start" if gi == 0 else None)
        off = cls_at(gi + 1, "end" if gi == n - 1 else None)
        for key, err in ((on, abs(float(h.start) - float(g.start))),
                         (off, abs(float(h.end) - float(g.end)))):
            res[key]["n"] += 1
            res[key]["sum_abs"] += err
    for name, keep in CTX_VIEWS.items():
        res[name] = {"n": sum(res[k]["n"] for k in keep),
                     "sum_abs": sum(res[k]["sum_abs"] for k in keep)}
    res["all"] = {"n": sum(res[k]["n"] for k in CTX_CLASSES),
                  "sum_abs": sum(res[k]["sum_abs"] for k in CTX_CLASSES)}
    return res


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
