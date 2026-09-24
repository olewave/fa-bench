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
"""The label-checked boundary score: does a hit credit the RIGHT boundary?

Every expectation below is worked out in the comment above it, so the file is
the specification of the rule rather than a lock on whatever it happens to
return. The rule checks BOTH sides of a boundary, and these tests are mostly
about what that buys over checking one side or none.
"""

from fabench.schema import Interval, Utterance
from fabench.score.core import score_pair
from fabench.score.matched import nw_align
from fabench.score.segmentation import (
    boundaries_from_intervals,
    count_hits,
    labelled_hits_by_tol,
)

TOLS = (0.020,)


def ivs(seq):
    return [Interval(lab, s, e) for lab, s, e in seq]


def hits(gold, hyp, *, positional=False, tol=0.020):
    """Label-checked hit count at one width, over two label sequences."""
    gl = [i.label for i in gold]
    hl = [i.label for i in hyp]
    aln = nw_align(gl, hl)
    pairs = aln.aligned() if positional else aln.matched(gl, hl)
    return labelled_hits_by_tol(gold, hyp, pairs, (tol,))[round(tol * 1000)]


def plain(gold, hyp, tol=0.020):
    return count_hits(boundaries_from_intervals(gold),
                      boundaries_from_intervals(hyp), tol)


# Four tiled units, three internal boundaries at 0.10, 0.20 and 0.40.
GOLD = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.20),
            ("c", 0.20, 0.40), ("d", 0.40, 0.50)])


def test_identical_sequences_match_the_time_only_count():
    """Nothing to disagree about: every boundary is right and every unit is the
    same unit, so the identity check costs nothing. 3 boundaries, 3 hits."""
    assert plain(GOLD, GOLD) == 3
    assert hits(GOLD, GOLD) == 3


def test_small_offsets_inside_the_tolerance_still_hit():
    """Boundaries moved by 5, 8 and 5 ms, all inside 20 ms, labels untouched."""
    hyp = ivs([("a", 0.00, 0.105), ("b", 0.105, 0.208),
               ("c", 0.208, 0.405), ("d", 0.405, 0.50)])
    assert plain(GOLD, hyp) == 3
    assert hits(GOLD, hyp) == 3


def test_substitution_costs_the_two_boundaries_beside_it():
    """THE REVIEWER'S CASE. Times are perfect, but the hypothesis calls unit
    "c" an "x". The boundary at 0.20 has "b" on its left and the wrong unit on
    its right, and the one at 0.40 has the wrong unit on its left, so neither
    is credited. Only 0.10, with "a" and "b" on its sides, survives.

    Time-only scores all three, which is the inflation being measured. The
    POSITIONAL variant also scores all three: the units correspond, it is only
    their labels that differ, which is exactly the difference between the two
    variants.
    """
    hyp = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.20),
               ("x", 0.20, 0.40), ("d", 0.40, 0.50)])
    assert plain(GOLD, hyp) == 3
    assert hits(GOLD, hyp) == 1
    assert hits(GOLD, hyp, positional=True) == 3


def test_one_sided_check_would_have_credited_the_substitution():
    """Why both sides. With "x" substituted for "c", the boundary at 0.20 has
    the right unit on its LEFT. A rule that checked only the left neighbour
    would credit it; checking both does not. This asserts the count that
    separates the two rules, so a regression to one-sided checking fails here.
    """
    hyp = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.20),
               ("x", 0.20, 0.40), ("d", 0.40, 0.50)])
    left_only = sum(
        1 for i in (1, 2, 3)
        if abs(hyp[i].start - GOLD[i].start) <= 0.020
        and GOLD[i - 1].label == hyp[i - 1].label
    )
    assert left_only == 2      # 0.10 and 0.20 -- 0.20 wrongly
    assert hits(GOLD, hyp) == 1


def test_insertion_kills_the_boundary_it_splits():
    """The hypothesis splits "c" into "c" and "e". Gold's 0.20 boundary still
    has b|c around it and is credited. Gold's 0.40 boundary now has "e" before
    "d" in the hypothesis, not "c", so it is not. The inserted boundary at 0.30
    has no gold counterpart at all and costs precision through n_hyp.
    """
    hyp = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.20), ("c", 0.20, 0.30),
               ("e", 0.30, 0.40), ("d", 0.40, 0.50)])
    assert hits(GOLD, hyp) == 2
    assert len(boundaries_from_intervals(hyp)) == 4   # one more than gold


def test_deletion_removes_the_boundary_from_recall():
    """The hypothesis drops "b", so "a" runs to 0.20. Gold's 0.10 boundary has
    no hypothesis counterpart and gold's 0.20 boundary has a|c in the
    hypothesis rather than b|c. Only 0.40 is credited, against three gold
    boundaries, so recall is 1/3 and the metric charges for the deletion.
    """
    hyp = ivs([("a", 0.00, 0.20), ("c", 0.20, 0.40), ("d", 0.40, 0.50)])
    assert hits(GOLD, hyp) == 1
    assert len(boundaries_from_intervals(GOLD)) == 3


def test_a_hit_on_the_neighbouring_boundary_is_not_credited():
    """The case the metric exists for. The hypothesis puts its b|c boundary at
    0.395, which is 5 ms from GOLD's C|D boundary at 0.40 and 195 ms from the
    b|c boundary it should have found. Time-only pairing credits it, because
    some reference boundary is within the tolerance. The identity check does
    not, because the units around 0.395 are b|c and the units around gold's
    0.40 are c|d.
    """
    hyp = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.395),
               ("c", 0.395, 0.45), ("d", 0.45, 0.50)])
    assert plain(GOLD, hyp) == 2          # 0.10 exactly, and 0.395 ~ 0.40
    assert hits(GOLD, hyp) == 1           # only 0.10


def test_zero_length_unit_is_not_a_boundary_on_either_side():
    """A unit whose start equals its predecessor's is dedupped out of the
    time-only boundary list, so it must not be counted here either. FALCON hit
    this: handed the gold phone sequence it matches every label, and counting
    the collapsed boundaries gave it a label-checked score ABOVE its time-only
    one, which the rule cannot produce.

    Gold "a b c d" with a zero-length "b": starts 0.0, 0.1, 0.1, 0.2, so the
    distinct boundaries are 0.1 and 0.2, and both counts must be 2.
    """
    gold = ivs([("a", 0.00, 0.10), ("b", 0.10, 0.10),
                ("c", 0.10, 0.20), ("d", 0.20, 0.30)])
    assert len(boundaries_from_intervals(gold)) == 2
    assert plain(gold, gold) == 2
    assert hits(gold, gold) == 2


def test_never_exceeds_the_time_only_count():
    """The invariant that makes the pair readable: the identity check can only
    withdraw credit, never add it, at every width and on every shape above.
    """
    cases = [
        ivs([("a", 0.00, 0.10), ("b", 0.10, 0.20), ("x", 0.20, 0.40), ("d", 0.40, 0.50)]),
        ivs([("a", 0.00, 0.20), ("c", 0.20, 0.40), ("d", 0.40, 0.50)]),
        ivs([("a", 0.00, 0.10), ("b", 0.10, 0.395), ("c", 0.395, 0.45), ("d", 0.45, 0.50)]),
        ivs([("a", 0.00, 0.11), ("b", 0.11, 0.23), ("c", 0.23, 0.38), ("d", 0.38, 0.50)]),
    ]
    for hyp in cases:
        for tol in (0.010, 0.020, 0.050, 0.100):
            assert hits(GOLD, hyp, tol=tol) <= plain(GOLD, hyp, tol), (hyp, tol)
            assert hits(GOLD, hyp, tol=tol) <= hits(GOLD, hyp, positional=True, tol=tol)


# ---------------------------------------------------------------------------
# Through score_pair, where the word tier drops silence pseudo-words
# ---------------------------------------------------------------------------

def utt(words, uid="u"):
    return Utterance(uid, "timit", "read", "s", "", 16000, 1.0,
                     words=words, phones=[])


def test_word_tier_drops_silence_pseudowords_from_both_sides():
    """Gold is "she had", the hypothesis inserts a "[sil]" between them. A
    pseudo-word is not a word, so it is dropped before the identity check and
    the one real boundary is credited -- rather than being destroyed by an
    insertion that only exists in the aligner's output format.

    The time-only score over the RAW sequences sees three hypothesis
    boundaries against one gold, which is why the label-checked score carries
    its own denominators: 1 gold, 1 hyp.
    """
    gold = utt([Interval("she", 0.10, 0.30), Interval("had", 0.30, 0.60)])
    hyp = utt([Interval("she", 0.10, 0.30), Interval("[sil]", 0.30, 0.31),
               Interval("had", 0.31, 0.60)])
    us = score_pair(gold, hyp, condition="c", aligner="a", mode="A")
    assert us.n_gold_wbnd_lbl == 1 and us.n_hyp_wbnd_lbl == 1
    assert us.n_wbnd_hits_lbl_by_tol[20] == 1
    # and the raw time-only tier still counts the pseudo-word's boundaries
    assert us.n_hyp_wbnd == 2


def test_word_tier_substitution_is_charged():
    """A misrecognised middle word. Times are exact, but both boundaries
    touching the wrong word lose their credit, while the time-only score keeps
    all three. This is the Track 2 case the paper reports.
    """
    gold = utt([Interval("she", 0.0, 0.1), Interval("had", 0.1, 0.2),
                Interval("your", 0.2, 0.3), Interval("suit", 0.3, 0.4)])
    hyp = utt([Interval("she", 0.0, 0.1), Interval("had", 0.1, 0.2),
               Interval("you", 0.2, 0.3), Interval("suit", 0.3, 0.4)])
    us = score_pair(gold, hyp, condition="c", aligner="a", mode="A")
    assert us.n_wbnd_hits_by_tol[20] == 3        # time-only: all three
    assert us.n_wbnd_hits_lbl_by_tol[20] == 1    # only she|had survives
    assert us.n_wbnd_hits_pos_by_tol[20] == 3    # the units still correspond


def test_phone_tier_reports_the_same_denominators_as_the_time_only_score():
    """The two phone-tier scores must be differenceable, which means identical
    denominators -- only the credit rule may differ."""
    g = [Interval("s", 0.0, 0.1), Interval("iy", 0.1, 0.3), Interval("sil", 0.3, 0.4)]
    h = [Interval("s", 0.0, 0.1), Interval("iy", 0.1, 0.31), Interval("sil", 0.31, 0.4)]
    us = score_pair(Utterance("u", "timit", "read", "s", "", 16000, 1.0,
                              words=[], phones=g),
                    Utterance("u", "timit", "read", "s", "", 16000, 1.0,
                              words=[], phones=h),
                    condition="c", aligner="a", mode="B")
    assert us.n_gold_bnd == 2 and us.n_hyp_bnd == 2
    assert us.n_bnd_hits_by_tol[20] == 2
    assert us.n_bnd_hits_lbl_by_tol[20] == 2


def test_hits_by_class_partition_the_positional_hits():
    """A B C against A X C, every time exact. Boundary A|B has the right unit
    on its left only and boundary B|C on its right only, so both are in the
    ``one`` class, the strict score credits neither, and the classes together
    are exactly the positional hits."""
    from fabench.score.segmentation import labelled_hits_by_class

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    aln = nw_align(gl, hl)
    by = labelled_hits_by_class(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert (by["both"]["n"], by["one"]["n"], by["none"]["n"]) == (0, 2, 0)
    assert by["one"]["hits"][20] == 2
    strict = labelled_hits_by_tol(gold, hyp, aln.matched(gl, hl), TOLS)[20]
    positional = labelled_hits_by_tol(gold, hyp, aln.aligned(), TOLS)[20]
    assert strict == by["both"]["hits"][20] == 0
    assert positional == sum(by[c]["hits"][20] for c in ("both", "one", "none")) == 2


def test_hits_by_class_two_substitutions_make_a_none_boundary():
    """A B C against X Y C. X|Y separates two substitutions and is ``none``,
    Y|C has the right unit on one side. A boundary beside an insertion or a
    deletion is in no class at all."""
    from fabench.score.segmentation import labelled_hits_by_class

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("x", 0.0, 0.5), ("y", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    aln = nw_align(gl, hl)
    by = labelled_hits_by_class(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert (by["both"]["n"], by["one"]["n"], by["none"]["n"]) == (0, 1, 1)
    # a deletion: A B C against A C, the boundary A|C answers to no single gold boundary
    hyp2 = ivs([("a", 0.0, 0.5), ("c", 0.5, 1.5)])
    hl2 = [w.label for w in hyp2]
    aln2 = nw_align(gl, hl2)
    by2 = labelled_hits_by_class(gold, hyp2, aln2.aligned(), aln2.matched(gl, hl2), TOLS)
    assert sum(by2[c]["n"] for c in ("both", "one", "none")) == 0


def test_hits_by_class_edges_are_classed_by_their_one_neighbour():
    """A B C against A X C with include_edges: the utterance-initial boundary
    has A on its one side, right, so it is a no-mismatch boundary; the final
    one has C, also right. Both edges hit. Against X B C the initial edge has
    a substituted neighbour and is a one-mismatch boundary, and against
    Z A B C, where the hypothesis starts with an inserted word, the gold edge
    has no counterpart and is in no class."""
    from fabench.score.segmentation import labelled_hits_by_class

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    by = labelled_hits_by_class(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS, include_edges=True)
    assert (by["both"]["n"], by["one"]["n"], by["none"]["n"], by["edges"]["n"]) == (2, 2, 0, 2)
    assert by["both"]["hits"][20] == 2 and by["edges"]["hits"][20] == 2
    hyp = ivs([("x", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    by = labelled_hits_by_class(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS, include_edges=True)
    assert (by["both"]["n"], by["one"]["n"]) == (2, 2)      # B|C and the final edge; X|B and the initial edge
    hyp = ivs([("z", 0.0, 0.2), ("a", 0.2, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    by = labelled_hits_by_class(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS, include_edges=True)
    assert by["edges"]["n"] == 1                               # the final edge only


def _f1(r, c, tol=20):
    h = r[c]["hits"][tol]; d = r[c]["n_gold"] + r[c]["n_hyp"]
    return 2 * h / d if d else None


def test_f1_by_category_substitution_and_edges():
    """A B C against A X C, every time exact. Gold boundaries: the start edge
    (silence, A right) and the end edge (C right, silence) are ``both``; A|B
    and B|C each have one wrong side. The hypothesis splits the same way.
    Every boundary corresponds and is on time, so both categories score 1.0
    and ``none`` is empty."""
    from fabench.score.segmentation import labelled_f1_by_category

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    aln = nw_align(gl, hl)
    r = labelled_f1_by_category(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert (r["both"]["n_gold"], r["one"]["n_gold"], r["none"]["n_gold"]) == (2, 2, 0)
    assert (r["both"]["n_hyp"], r["one"]["n_hyp"], r["none"]["n_hyp"]) == (2, 2, 0)
    assert _f1(r, "both") == 1.0 and _f1(r, "one") == 1.0 and _f1(r, "none") is None


def test_f1_by_category_deletion_is_a_miss_and_a_false_alarm():
    """A B C against A C with B dropped. Gold: two edges in ``both``, A|B and
    B|C in ``one`` since B is unmatched. Hypothesis: two edges and A|C, all
    ``both``. The edges hit. A|C has no gold boundary, so ``both`` is 2 hits
    over 2 gold and 3 hypothesis boundaries, 0.8, and ``one`` is 0 hits over
    2 gold boundaries, 0, the deletion charged to recall."""
    from fabench.score.segmentation import labelled_f1_by_category

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("a", 0.0, 0.5), ("c", 0.5, 1.5)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    aln = nw_align(gl, hl)
    r = labelled_f1_by_category(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert (r["both"]["n_gold"], r["both"]["n_hyp"], r["both"]["hits"][20]) == (2, 3, 2)
    assert (r["one"]["n_gold"], r["one"]["n_hyp"], r["one"]["hits"][20]) == (2, 0, 0)
    assert abs(_f1(r, "both") - 0.8) < 1e-9 and _f1(r, "one") == 0.0


def test_f1_by_category_edge_beside_a_wrong_word_is_one():
    """X B C against A B C: the start edge has silence on one side and a wrong
    word on the other, so it is ``one`` on both tiers, and it still hits when
    the time is right. An inserted leading word, Z A B C, leaves the gold start
    edge with no counterpart and adds a hypothesis edge in ``one``."""
    from fabench.score.segmentation import labelled_f1_by_category

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl = [w.label for w in gold]
    hyp = ivs([("x", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    r = labelled_f1_by_category(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert (r["one"]["n_gold"], r["one"]["n_hyp"], r["one"]["hits"][20]) == (2, 2, 2)   # start edge and A|B
    hyp = ivs([("z", 0.0, 0.2), ("a", 0.2, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    r = labelled_f1_by_category(gold, hyp, aln.aligned(), aln.matched(gl, hl), TOLS)
    assert r["both"]["n_gold"] == 4 and r["both"]["hits"][20] == 3                     # gold start edge misses
    assert r["one"]["n_hyp"] == 2 and r["one"]["n_gold"] == 0                          # hyp start edge and Z|A


def test_word_context_groups_are_fixed_by_the_transcript():
    """A B C against A X C, times exact. Reference groups: the two edges are
    ``both``, A|B and B|C are ``one``. The recognized side splits the same
    way. Everything hits within its group. Against A C with B dropped the
    reference groups are unchanged in size, since they depend only on the
    words, and ``one`` has no recognized boundaries at all."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert (r["both"]["n_gold"], r["one"]["n_gold"], r["none"]["n_gold"]) == (2, 2, 0)
    assert (r["both"]["n_hyp"], r["one"]["n_hyp"]) == (2, 2)
    assert r["both"]["hits"][20] == 2 and r["one"]["hits"][20] == 2
    hyp = ivs([("a", 0.0, 0.5), ("c", 0.5, 1.5)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert (r["both"]["n_gold"], r["one"]["n_gold"]) == (2, 2)     # same reference groups as above
    assert (r["both"]["n_hyp"], r["one"]["n_hyp"]) == (3, 0)       # A|C is a both-group false alarm
    assert r["both"]["hits"][20] == 2 and r["one"]["hits"][20] == 0


def test_word_context_phones_inherit_their_words_group():
    """Words A B against A X, two phones each. Phone boundaries: the start edge
    and a1|a2 are ``both``, a2|b1 sits between a matched and an unmatched word
    and is ``one``, b1|b2 is inside the unmatched word and is ``none``, and
    the end edge, silence beside B, is ``one``."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 1.0), ("b", 1.0, 2.0)])
    hyp = ivs([("a", 0.0, 1.0), ("x", 1.0, 2.0)])
    gph = ivs([("a1", 0.0, 0.5), ("a2", 0.5, 1.0), ("b1", 1.0, 1.5), ("b2", 1.5, 2.0)])
    hph = ivs([("p", 0.0, 0.5), ("q", 0.5, 1.0), ("r", 1.0, 1.5), ("s", 1.5, 2.0)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), gph, hph, tols_s=TOLS)
    assert (r["both"]["n_gold"], r["one"]["n_gold"], r["none"]["n_gold"]) == (2, 2, 1)
    assert (r["both"]["hits"][20], r["one"]["hits"][20], r["none"]["hits"][20]) == (2, 2, 1)


def test_mae_by_word_context_is_edge_based_not_boundary_based():
    """Every word matched, so every edge is ``both``. This function charges the
    two edges of each aligned pair, so a contiguous run of 3 words gives 6
    entries, while `word_abs_errors` reports the 4 distinct boundaries. The two
    therefore differ by the shared interior times, counted twice here."""
    from fabench.score.segmentation import mae_by_word_context
    from fabench.score.word import word_abs_errors

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("a", 0.01, 0.52), ("b", 0.52, 1.03), ("c", 1.03, 1.54)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    aln = nw_align(gl, hl)
    r = mae_by_word_context(gold, hyp, aln.matched(gl, hl), aln.aligned())
    assert r["both"]["n"] == 6 and r["one"]["n"] == 0 and r["none"]["n"] == 0
    assert len(word_abs_errors(gold, hyp)) == 4


def test_mae_by_word_context_charges_each_edge_to_its_boundarys_group():
    """A B C D against A X Y D. Edges and the A|B, C|D boundaries are as the
    F1 groups them, and B|C, between two substituted words, is ``none``. The
    onset of A and the offset of D are ``both``; A's offset, X's onset, Y's
    offset and D's onset are ``one``; X's offset and Y's onset are ``none``.
    Against A D, with B and C deleted, the deleted words contribute nothing
    and ``none`` is empty though its reference boundary is still there."""
    from fabench.score.segmentation import mae_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 1.5, 2.0)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.01, 0.52), ("x", 0.52, 1.03), ("y", 1.03, 1.54), ("d", 1.54, 2.00)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    r = mae_by_word_context(gold, hyp, aln.matched(gl, hl), aln.aligned())
    assert (r["both"]["n"], r["one"]["n"], r["none"]["n"]) == (2, 4, 2)
    assert abs(r["both"]["sum_abs"] - 0.01) < 1e-9          # A onset .01, D offset 0
    assert abs(r["one"]["sum_abs"] - 0.12) < 1e-9           # A off .02, X on .02, Y off .04, D on .04
    assert abs(r["none"]["sum_abs"] - 0.06) < 1e-9          # X off .03, Y on .03
    hyp = ivs([("a", 0.0, 0.5), ("d", 1.5, 2.0)])
    hl = [w.label for w in hyp]; aln = nw_align(gl, hl)
    r = mae_by_word_context(gold, hyp, aln.matched(gl, hl), aln.aligned())
    assert (r["both"]["n"], r["one"]["n"], r["none"]["n"]) == (2, 2, 0)


def test_mae_by_word_context_phones_inherit_their_words_group():
    """Words A B against A X, two phones each, all phone labels equal and the
    hyp phones 10 ms late. a1's two edges and a2's onset are ``both``, a2's
    offset, b1's onset and b2's offset are ``one``, b1's offset and b2's
    onset, inside the unmatched word, are ``none``."""
    from fabench.score.segmentation import mae_by_word_context

    gold = ivs([("a", 0.0, 1.0), ("b", 1.0, 2.0)])
    hyp = ivs([("a", 0.0, 1.0), ("x", 1.0, 2.0)])
    gph = ivs([("p", 0.0, 0.5), ("q", 0.5, 1.0), ("r", 1.0, 1.5), ("s", 1.5, 2.0)])
    hph = ivs([("p", 0.01, 0.51), ("q", 0.51, 1.01), ("r", 1.01, 1.51), ("s", 1.51, 2.01)])
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    gpl, hpl = [p.label for p in gph], [p.label for p in hph]
    r = mae_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), nw_align(gpl, hpl).aligned(), gph, hph)
    assert (r["both"]["n"], r["one"]["n"], r["none"]["n"]) == (3, 3, 2)
    assert all(abs(r[k]["sum_abs"] - 0.01 * r[k]["n"]) < 1e-9 for k in r)


def test_word_context_pool_gathers_the_three_groups():
    """A B C against A X C. The three groups hold 2, 2 and 0 reference
    boundaries and ``all`` holds the 4 of them, every boundary of the
    utterance with the edges in. Pooling can only add hits, never lose one,
    since a group's pairing is available to the pool as well."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert r["pool"]["n_gold"] == sum(r[c]["n_gold"] for c in ("both", "one", "none")) == 4
    assert r["pool"]["n_hyp"] == 4 and r["pool"]["hits"][20] == 4
    assert r["pool"]["hits"][20] >= sum(r[c]["hits"][20] for c in ("both", "one", "none"))
    # all shares the pool's denominators and only the both group's hits
    assert r["all"]["n_gold"] == 4 and r["all"]["n_hyp"] == 4
    assert r["all"]["hits"][20] == r["both"]["hits"][20] == 2


def test_word_context_pool_can_beat_the_groups_added_up():
    """A B C D against A Y D, B and C lost to one word. The reference B|C
    boundary is ``none``, both its words being unmatched, and the recognized
    side has no ``none`` boundary at all, so within the group it is a certain
    miss. The recognized Y|D boundary sits exactly on it and the grouping
    files that one under ``one``, so only the pool can pair them."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 1.5, 2.0)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.0, 0.5), ("y", 0.5, 1.0), ("d", 1.0, 2.0)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert r["none"]["n_gold"] == 1 and r["none"]["n_hyp"] == 0 and r["none"]["hits"][20] == 0
    assert sum(r[c]["hits"][20] for c in ("both", "one", "none")) == 3
    assert r["pool"]["hits"][20] == 4


def test_word_context_all_charges_every_boundary_for_the_words_too():
    """A B C D against A Y D again, times exact where the words survive. Only
    the two edges and A|B are ``both``, so only they can score, and the
    denominator is all five reference boundaries. A system that timed
    everything it recognized perfectly still cannot reach 1.0 here, which is
    the point of the column."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 1.5, 2.0)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.0, 0.5), ("y", 0.5, 1.5), ("d", 1.5, 2.0)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert r["all"]["n_gold"] == 5 and r["all"]["n_hyp"] == 4
    assert r["both"]["n_gold"] == 2 and r["all"]["hits"][20] == r["both"]["hits"][20] == 2
    assert abs(2 * 2 / (5 + 4) - 2 * r["all"]["hits"][20] / (r["all"]["n_gold"] + r["all"]["n_hyp"])) < 1e-12


def test_word_context_splits_the_two_edges_apart():
    """A B C, only B matched, so both edges are wrong, and A B C against
    A B X, where the start edge is right and the end edge wrong. The classes
    have to tell speech onset from speech offset, and an edge whose word is
    wrong belongs to neither."""
    from fabench.score.segmentation import f1_by_word_context

    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    gl = [w.label for w in gold]
    hyp = ivs([("x", 0.0, 0.5), ("b", 0.5, 1.0), ("y", 1.0, 1.5)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert r["start_ok"]["n_gold"] == 0 and r["end_ok"]["n_gold"] == 0
    assert r["edge_bad"]["n_gold"] == 2 and r["int_one"]["n_gold"] == 2
    hyp = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("x", 1.0, 1.5)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    assert r["start_ok"]["n_gold"] == 1 and r["end_ok"]["n_gold"] == 0
    assert r["edge_bad"]["n_gold"] == 1
    assert r["int_both"]["n_gold"] == 1 and r["int_one"]["n_gold"] == 1


def test_word_context_classes_partition_every_boundary():
    """The six classes add up to the pool on both sides, and the unions are
    the sums they claim to be. rest is the interior with nothing matched
    together with the edges whose word is wrong, so it is not none."""
    from fabench.score.segmentation import CTX_CLASSES, f1_by_word_context

    gold = ivs([("a", 0.0, 0.4), ("b", 0.4, 0.8), ("c", 0.8, 1.2), ("d", 1.2, 1.6)])
    gl = [w.label for w in gold]
    hyp = ivs([("x", 0.0, 0.4), ("y", 0.4, 0.8), ("c", 0.8, 1.2), ("z", 1.2, 1.6)])
    hl = [w.label for w in hyp]
    r = f1_by_word_context(gold, hyp, nw_align(gl, hl).matched(gl, hl), tols_s=TOLS)
    for side in ("n_gold", "n_hyp"):
        assert sum(r[c][side] for c in CTX_CLASSES) == r["pool"][side]
        assert r["both"][side] == sum(r[c][side] for c in ("int_both", "start_ok", "end_ok"))
        assert r["one"][side] == r["int_one"][side] + r["edge_bad"][side]
        assert r["rest"][side] == r["int_none"][side] + r["edge_bad"][side]
    assert r["rest"]["n_gold"] != r["none"]["n_gold"]   # the two edges are wrong here


def test_mae_by_word_context_classes_partition_the_edges():
    """Every aligned unit gives two edges and each lands in one class, so the
    classes add up to all and the unions add up as declared."""
    from fabench.score.segmentation import CTX_CLASSES, mae_by_word_context

    gold = ivs([("a", 0.0, 0.4), ("b", 0.4, 0.8), ("c", 0.8, 1.2)])
    gl = [w.label for w in gold]
    hyp = ivs([("a", 0.01, 0.42), ("x", 0.42, 0.83), ("c", 0.83, 1.21)])
    hl = [w.label for w in hyp]
    aln = nw_align(gl, hl)
    r = mae_by_word_context(gold, hyp, aln.matched(gl, hl), aln.aligned())
    assert sum(r[c]["n"] for c in CTX_CLASSES) == r["all"]["n"] == 6
    assert abs(sum(r[c]["sum_abs"] for c in CTX_CLASSES) - r["all"]["sum_abs"]) < 1e-12
    assert r["start_ok"]["n"] == 1 and r["end_ok"]["n"] == 1 and r["edge_bad"]["n"] == 0
