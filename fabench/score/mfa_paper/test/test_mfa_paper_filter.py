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

"""Port of data_prep.R's filtered_boundary_data predicate (mfa_paper protocol)."""

from fabench.score.mfa_paper.filter import filter_boundaries


def _rec(prev_ref, prev_test, foll_ref, foll_test, **extra):
    return {
        "previous_reference_phone": prev_ref,
        "previous_test_phone": prev_test,
        "following_reference_phone": foll_ref,
        "following_test_phone": foll_test,
        "boundary_error": 0.0,
        "reference_boundary": 0.0,
        "test_boundary": 0.0,
        **extra,
    }


def test_categories_agree_kept():
    # dh|ah boundary: both sides fricative->vowel
    recs = [_rec("dh", "DH", "ah", "AH0")]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert len(out) == 1


def test_mismatch_on_one_side_dropped():
    # previous side categories disagree: ref "dh" (fricative) vs test "B" (stop)
    recs = [_rec("dh", "B", "ah", "AH0")]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert len(out) == 0


def test_unknown_on_either_side_dropped_even_if_other_side_agrees():
    # following side categories agree (vowel==vowel), but previous test phone is
    # not in the arpa table at all -> "unknown" -> dropped despite the agreement
    # on the other side (data_prep.R requires ALL FOUR categories != unknown).
    recs = [_rec("dh", "NOT_A_REAL_PHONE", "ah", "AH0")]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert len(out) == 0


def test_silence_is_an_ordinary_category_not_specially_excluded():
    # both sides correctly agree "silence" -> kept, exactly like any other
    # manner-consistent boundary (silence is NOT excluded by label).
    recs = [_rec("sil", "sil", "dh", "DH")]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert len(out) == 1


def test_rhotic_override_changes_filter_outcome():
    # Without the override, ref "er" (vowel) vs test "ER0" (approximant, plain
    # arpa lookup) would mismatch and be dropped; the override rescues it.
    recs = [_rec("er", "ER0", "ah", "AH0")]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert len(out) == 1


def test_records_pass_through_unmodified():
    recs = [_rec("dh", "DH", "ah", "AH0", boundary_error=0.012, reference_boundary=1.23)]
    out = filter_boundaries(recs, aligner_key="arpa", corpus="timit")
    assert out[0]["boundary_error"] == 0.012
    assert out[0]["reference_boundary"] == 1.23
    assert out[0] is recs[0]  # not copied
