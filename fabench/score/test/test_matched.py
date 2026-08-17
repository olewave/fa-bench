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

"""Matched-set construction (Plan 5.1) — hand-checked alignments."""

from fabench.score.matched import (
    boundary_aware_align,
    matched_indices,
    nw_align,
    recall_counts,
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
    n_m, n_g, n_h = recall_counts(a, a)
    assert (n_m, n_g, n_h) == (4, 4, 4)  # ARR == 1.0 by construction (gate #5)


def test_substitution_not_matched():
    gold = ["A", "B", "C"]
    hyp = ["A", "X", "C"]
    m = matched_indices(gold, hyp)
    # A and C match; B<->X is a substitution (different class) => unmatched.
    assert m == [(0, 0), (2, 2)]
    n_m, n_g, n_h = recall_counts(gold, hyp)
    assert (n_m, n_g, n_h) == (2, 3, 3)


def test_insertion():
    gold = ["A", "B"]
    hyp = ["A", "Q", "B"]  # Q inserted
    m = matched_indices(gold, hyp)
    assert m == [(0, 0), (1, 2)]
    n_m, n_g, n_h = recall_counts(gold, hyp)
    assert (n_m, n_g, n_h) == (2, 2, 3)


def test_deletion():
    gold = ["A", "B", "C"]
    hyp = ["A", "C"]  # B deleted
    m = matched_indices(gold, hyp)
    assert m == [(0, 0), (2, 1)]
    n_m, n_g, n_h = recall_counts(gold, hyp)
    assert (n_m, n_g, n_h) == (2, 3, 2)


def test_repeated_label_monotonic():
    # gold has two A's, hyp one A -> exactly one match, order preserved.
    gold = ["A", "A"]
    hyp = ["A"]
    n_m, n_g, n_h = recall_counts(gold, hyp)
    assert (n_m, n_g, n_h) == (1, 2, 1)


def test_alignment_is_monotonic():
    gold = ["A", "B", "C", "D"]
    hyp = ["A", "C", "B", "D"]  # transposition
    aln = nw_align(gold, hyp)
    gis = [gi for gi, _ in aln.pairs if gi is not None]
    his = [hj for _, hj in aln.pairs if hj is not None]
    assert gis == sorted(gis)
    assert his == sorted(his)
