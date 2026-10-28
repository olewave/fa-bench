# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Matched-set construction (Plan 5.1) — hand-checked alignments."""

from fabench.score.matched import (
    boundary_aware_align,
    edit_counts,
    matched_indices,
    nw_align,
)


def test_boundary_aware_matcher_breaks_ties_by_time():
    """Paper's boundary-distance matcher (arXiv:2606.18466) pairs a phone with the
    time-nearest same-label candidate; label-only NW can pick the time-far one."""
    from fabench.schema import Interval as I

    # one gold 'a' at 0.05-0.15; two hyp 'a's — a near one (0.02) and a far one (0.8)
    gold = [I("a", 0.05, 0.15)]
    hyp = [I("a", 0.02, 0.12), I("a", 0.80, 0.90)]
    vowel = lambda c: "vowel"

    aln = boundary_aware_align(gold, ["a"], hyp, ["a", "a"], vowel)
    assert (0, 0) in aln.pairs and (0, 1) not in aln.pairs   # picks the near one

    nw = nw_align(["a"], ["a", "a"])
    assert (0, 1) in nw.pairs   # label-only picks the far one (the error it fixes)


def test_identical_sequences_all_match():
    a = ["sil", "s", "iy", "sil"]
    m = matched_indices(a, a)
    assert m == [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert edit_counts(a, a) == (4, 0, 0, 0)  # PER == 0 by construction (gate #5)


def test_substitution_not_matched():
    gold = ["A", "B", "C"]
    hyp = ["A", "X", "C"]
    m = matched_indices(gold, hyp)
    # A and C match; B<->X is a substitution (different class) => unmatched.
    assert m == [(0, 0), (2, 2)]
    assert edit_counts(gold, hyp) == (2, 1, 0, 0)


def test_insertion():
    gold = ["A", "B"]
    hyp = ["A", "Q", "B"]  # Q inserted
    m = matched_indices(gold, hyp)
    assert m == [(0, 0), (1, 2)]
    assert edit_counts(gold, hyp) == (2, 0, 0, 1)


def test_deletion():
    gold = ["A", "B", "C"]
    hyp = ["A", "C"]  # B deleted
    m = matched_indices(gold, hyp)
    assert m == [(0, 0), (2, 1)]
    assert edit_counts(gold, hyp) == (2, 0, 1, 0)


def test_repeated_label_monotonic():
    # gold has two A's, hyp one A -> exactly one match, order preserved.
    gold = ["A", "A"]
    hyp = ["A"]
    assert edit_counts(gold, hyp) == (1, 0, 1, 0)


def test_alignment_is_monotonic():
    gold = ["A", "B", "C", "D"]
    hyp = ["A", "C", "B", "D"]  # transposition
    aln = nw_align(gold, hyp)
    gis = [gi for gi, _ in aln.pairs if gi is not None]
    his = [hj for _, hj in aln.pairs if hj is not None]
    assert gis == sorted(gis)
    assert his == sorted(his)
