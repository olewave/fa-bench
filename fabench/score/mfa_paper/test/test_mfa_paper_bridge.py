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

"""Tests for the kalpy subprocess bridge (mfa_paper protocol), in two tiers:

* no-env (always run): feed the FA-Bench-side converter verbatim kalpy output
  captured this session, and check the sign flip / edge tagging / gold_phone_idx
  recovery — no micromamba or kalpy needed.
* env-gated: actually invoke the real bridge against the `mfa` micromamba env,
  checking the exact live behaviors verified this session (insertion/deletion-
  adjacent boundary drop; closure merging via custom_mapping).
"""

import pytest

from fabench.schema import Interval
from fabench.score.mfa_paper.bridge import batch_align_phones, bridge_available
from fabench.score.mfa_paper.cell import _nearest_gold_idx, to_boundary_error

_HAS_MFA_ENV = bridge_available()
_skip_no_env = pytest.mark.skipif(not _HAS_MFA_ENV, reason="mfa micromamba env with kalpy.evaluation not available")

# Verbatim kalpy output captured this session for
# ref=[sil(0-.20), dh(.20-.28), ah(.28-.35), sil(.35-.60)]
# test=[sil(0-.16), sp(.16-.24, inserted), dh(.24-.30), ah(.30-.37), sil(.37-.60)]
_CAPTURED_BOUNDARY_ERRORS = [
    {
        "following_reference_phone": "ah", "following_test_phone": "ah",
        "previous_reference_phone": "dh", "previous_test_phone": "dh",
        "boundary_error": -0.02, "reference_boundary": 0.28, "test_boundary": 0.3,
    },
    {
        "following_reference_phone": "sil", "following_test_phone": "sil",
        "previous_reference_phone": "ah", "previous_test_phone": "ah",
        "boundary_error": -0.02, "reference_boundary": 0.35, "test_boundary": 0.37,
    },
]
_GOLD_IVS = [
    Interval("sil", 0.00, 0.20), Interval("dh", 0.20, 0.28),
    Interval("ah", 0.28, 0.35), Interval("sil", 0.35, 0.60),
]


def test_to_boundary_error_sign_flip():
    # kalpy's boundary_error is gold - hyp; fabench's .signed is hyp - gold.
    raw = _CAPTURED_BOUNDARY_ERRORS[0]  # reference_boundary=0.28, boundary_error=-0.02
    be = to_boundary_error(raw, "timit", _GOLD_IVS)
    assert be.gold_time == pytest.approx(0.28)
    assert be.hyp_time == pytest.approx(0.30)          # 0.28 - (-0.02)
    assert be.signed == pytest.approx(0.02)            # hyp - gold, aligner lags
    assert be.abs == pytest.approx(0.02)


def test_to_boundary_error_edge_and_manner():
    be = to_boundary_error(_CAPTURED_BOUNDARY_ERRORS[0], "timit", _GOLD_IVS)
    assert be.edge == "boundary"          # kalpy's single-edge convention, not onset/offset
    assert be.left_manner == "fricative"  # "dh" (previous_reference_phone)
    assert be.right_manner == "vowel"     # "ah" (following_reference_phone)


def test_to_boundary_error_gold_phone_idx_recovery():
    be = to_boundary_error(_CAPTURED_BOUNDARY_ERRORS[1], "timit", _GOLD_IVS)
    # reference_boundary=0.35 matches _GOLD_IVS[3] ("sil", start=0.35) exactly
    assert be.gold_phone_idx == 3


def test_nearest_gold_idx_tolerates_kalpy_3_decimal_rounding():
    # kalpy rounds to 3 decimals; a gold start of 0.2800001 should still match
    # index 1 (start=0.28) within the 0.6ms tolerance.
    ivs = [Interval("x", 0.2800001, 0.30)]
    assert _nearest_gold_idx(ivs, 0.280) == 0


def test_nearest_gold_idx_returns_minus_one_when_nothing_close():
    ivs = [Interval("x", 0.0, 0.1)]
    assert _nearest_gold_idx(ivs, 5.0) == -1


@_skip_no_env
def test_live_bridge_insertion_adjacent_drop():
    gold = [Interval("sil", 0.00, 0.20), Interval("dh", 0.20, 0.28),
            Interval("ah", 0.28, 0.35), Interval("sil", 0.35, 0.60)]
    hyp = [Interval("sil", 0.00, 0.16), Interval("sp", 0.16, 0.24),
           Interval("dh", 0.24, 0.30), Interval("ah", 0.30, 0.37), Interval("sil", 0.37, 0.60)]
    result = batch_align_phones([("u1", gold, hyp)], silence_phones={"sil"}, custom_mapping={})
    boundaries = result["u1"]["boundary_errors"]
    assert len(boundaries) == 2  # sil|dh dropped (adjacent to the "sp" insertion)


@_skip_no_env
def test_live_bridge_closure_merge_via_custom_mapping():
    gold = [Interval("iy", 0.00, 0.10), Interval("bcl", 0.10, 0.15),
            Interval("b", 0.15, 0.18), Interval("aa", 0.18, 0.30)]
    hyp = [Interval("IY0", 0.00, 0.11), Interval("B", 0.11, 0.19), Interval("AA0", 0.19, 0.30)]
    mapping = {"B": {"b", "bcl", "bcl b"}, "AA0": {"aa", "aan", "ao", "aon"}, "IY0": {"iy", "iyn"}}

    without = batch_align_phones([("u1", gold, hyp)], silence_phones={"sil"}, custom_mapping={})
    with_mapping = batch_align_phones([("u1", gold, hyp)], silence_phones={"sil"}, custom_mapping=mapping)

    # without the mapping, the raw DP's choice of which token to strand as a
    # deletion drops the aa|AA0 boundary entirely; with it, both survive.
    assert len(without["u1"]["boundary_errors"]) == 1
    assert len(with_mapping["u1"]["boundary_errors"]) == 2
