# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0
"""The label-checked boundary F1: does a hit credit the RIGHT boundary?

Every expectation below is worked out in the comment above it, so the file is
the specification of the rule rather than a lock on whatever it happens to
return. A boundary can score only when the units on BOTH sides of it match,
and every boundary of the utterance, the two edges included, is in the
denominator.
"""

from fabench.schema import Interval, Utterance
from fabench.score.core import score_pair
from fabench.score.matched import nw_align
from fabench.score.segmentation import f1_all


def ivs(seq):
    return [Interval(lab, s, e) for lab, s, e in seq]


def utt(words, uid="u"):
    return Utterance(uid, "timit", "read", "s", "", 16000, 1.0,
                     words=words, phones=[])


def _all(gold, hyp, *units, **kw):
    gl, hl = [w.label for w in gold], [w.label for w in hyp]
    return f1_all(gold, hyp, nw_align(gl, hl).matched(gl, hl), *units, **kw)


def test_a_substitution_costs_the_two_boundaries_beside_it():
    """A B C against A X C, times exact. The two edges score, A|B and B|C sit
    beside the wrong word and cannot, and all four are in the denominator on
    each side."""
    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5)])
    hyp = ivs([("a", 0.0, 0.5), ("x", 0.5, 1.0), ("c", 1.0, 1.5)])
    assert _all(gold, hyp) == {"n_gold": 4, "n_hyp": 4, "hits": 2}
    assert _all(gold, gold) == {"n_gold": 4, "n_hyp": 4, "hits": 4}


def test_every_boundary_is_charged_for_the_words_too():
    """A B C D against A Y D, times exact where the words survive. Only the
    two edges and A|B have a matched word on each side, so only they can
    score, and the denominator is all five reference boundaries. A system
    that timed everything it recognized perfectly still cannot reach 1.0."""
    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 1.5), ("d", 1.5, 2.0)])
    hyp = ivs([("a", 0.0, 0.5), ("y", 0.5, 1.5), ("d", 1.5, 2.0)])
    r = _all(gold, hyp)
    assert r == {"n_gold": 5, "n_hyp": 4, "hits": 2}
    assert abs(2 * r["hits"] / (r["n_gold"] + r["n_hyp"]) - 4 / 9) < 1e-12


def test_a_hit_must_lie_within_20_ms():
    """The same words, the inner boundary 25 ms late and the end 15 ms late.
    The end is a hit and the inner boundary is not."""
    gold = ivs([("a", 0.0, 0.5), ("b", 0.5, 1.0)])
    hyp = ivs([("a", 0.0, 0.525), ("b", 0.525, 1.015)])
    assert _all(gold, hyp) == {"n_gold": 3, "n_hyp": 3, "hits": 2}


def test_phones_are_classed_by_their_own_labels():
    """Words A B against A B, both matched, but the phones are a1 a2 b1 b2
    against a1 a2 X b2. Inheriting the words' flags marks every phone matched
    and all five boundaries can score. With the phone alignment's own matched
    sets the two boundaries beside X cannot, which is the rule the word tier
    applies and the one the paper states."""
    gold = ivs([("a", 0.0, 1.0), ("b", 1.0, 2.0)])
    gph = ivs([("a1", 0.0, 0.5), ("a2", 0.5, 1.0), ("b1", 1.0, 1.5), ("b2", 1.5, 2.0)])
    hph = ivs([("a1", 0.0, 0.5), ("a2", 0.5, 1.0), ("x", 1.0, 1.5), ("b2", 1.5, 2.0)])
    assert _all(gold, gold, gph, hph)["hits"] == 5
    gpl, hpl = [u.label for u in gph], [u.label for u in hph]
    pm = nw_align(gpl, hpl).matched(gpl, hpl)
    r = _all(gold, gold, gph, hph, gold_unit_matched={g for g, _ in pm},
             hyp_unit_matched={h for _, h in pm})
    assert r == {"n_gold": 5, "n_hyp": 5, "hits": 3}


def test_word_tier_drops_silence_pseudowords_from_both_sides():
    """Gold is "one two", the hypothesis inserts a "[sil]" between them. A
    pseudo-word is not a word, so it is dropped before the identity check and
    all three boundaries, the 10 ms late inner one included, are credited."""
    gold = utt([Interval("one", 0.10, 0.30), Interval("two", 0.30, 0.60)])
    hyp = utt([Interval("one", 0.10, 0.30), Interval("[sil]", 0.30, 0.31),
               Interval("two", 0.31, 0.60)])
    us = score_pair(gold, hyp, condition="c", aligner="a", mode="A")
    assert us.wbnd_all == {"n_gold": 3, "n_hyp": 3, "hits": 3}


def test_word_tier_substitution_is_charged():
    """A misrecognised third word. Times are exact, but both boundaries
    touching the wrong word lose their credit. This is the Track 2 case the
    paper reports."""
    gold = utt([Interval("one", 0.0, 0.1), Interval("two", 0.1, 0.2),
                Interval("three", 0.2, 0.3), Interval("four", 0.3, 0.4)])
    hyp = utt([Interval("one", 0.0, 0.1), Interval("two", 0.1, 0.2),
               Interval("tree", 0.2, 0.3), Interval("four", 0.3, 0.4)])
    us = score_pair(gold, hyp, condition="c", aligner="a", mode="A")
    assert us.wbnd_all == {"n_gold": 5, "n_hyp": 5, "hits": 3}
