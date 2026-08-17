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

"""extract_boundary_errors() (mfa_paper protocol) — a faithful re-expression of
kalpy's own align_phones boundary-extraction loop, with its two hardcoded
exclusions (utterance-edge, gap-adjacency) exposed as independent toggles.

Fixture is the verbatim alignment_path captured this session for
ref=[sil(0-.20), dh(.20-.28), ah(.28-.35), sil(.35-.60)]
test=[sil(0-.16), sp(.16-.24, inserted), dh(.24-.30), ah(.30-.37), sil(.37-.60)]
"""

from fabench.score.mfa_paper.cell import extract_boundary_errors
from fabench.score.mfa_paper.manner_categories import (
    UTTERANCE_EDGE,
    categorize_ref,
    categorize_test,
)

_ALIGNMENT_PATH = [
    {"ref_label": "sil", "ref_begin": 0.0, "ref_end": 0.2,
     "test_label": "sil", "test_begin": 0.0, "test_end": 0.16},
    {"ref_label": "-", "ref_begin": None, "ref_end": None,
     "test_label": "sp", "test_begin": 0.16, "test_end": 0.24},
    {"ref_label": "dh", "ref_begin": 0.2, "ref_end": 0.28,
     "test_label": "dh", "test_begin": 0.24, "test_end": 0.3},
    {"ref_label": "ah", "ref_begin": 0.28, "ref_end": 0.35,
     "test_label": "ah", "test_begin": 0.3, "test_end": 0.37},
    {"ref_label": "sil", "ref_begin": 0.35, "ref_end": 0.6,
     "test_label": "sil", "test_begin": 0.37, "test_end": 0.6},
]

# kalpy's own native boundary_errors for this exact alignment (captured this
# session, cross-checked live against the real bridge — see test_mfa_paper_bridge.py)
_NATIVE_KALPY_OUTPUT = [
    {"following_reference_phone": "ah", "following_test_phone": "ah",
     "previous_reference_phone": "dh", "previous_test_phone": "dh",
     "boundary_error": -0.02, "reference_boundary": 0.28, "test_boundary": 0.3},
    {"following_reference_phone": "sil", "following_test_phone": "sil",
     "previous_reference_phone": "ah", "previous_test_phone": "ah",
     "boundary_error": -0.02, "reference_boundary": 0.35, "test_boundary": 0.37},
]


def test_both_flags_off_matches_kalpys_native_output_exactly():
    """The whole point: with both flags off, this must be byte-identical to
    what kalpy itself returns — a faithful re-expression, not an approximation."""
    out = extract_boundary_errors(_ALIGNMENT_PATH)
    assert out == _NATIVE_KALPY_OUTPUT


def test_include_gap_adjacent_recovers_the_dropped_worst_boundary():
    out = extract_boundary_errors(_ALIGNMENT_PATH, include_gap_adjacent=True)
    assert len(out) == 3
    recovered = out[0]
    assert recovered["following_reference_phone"] == "dh"
    assert recovered["previous_reference_phone"] == "-"    # literal gap step's ref label
    assert recovered["previous_test_phone"] == "sp"         # the inserted phone
    assert recovered["boundary_error"] == -0.04              # the largest error of the three
    # the two natively-scored boundaries are unaffected
    assert out[1:] == _NATIVE_KALPY_OUTPUT


def test_include_utterance_edges_recovers_the_first_boundary():
    out = extract_boundary_errors(_ALIGNMENT_PATH, include_utterance_edges=True)
    assert len(out) == 3
    recovered = out[0]
    assert recovered["following_reference_phone"] == "sil"
    assert recovered["previous_reference_phone"] == UTTERANCE_EDGE
    assert recovered["previous_test_phone"] == UTTERANCE_EDGE
    assert recovered["reference_boundary"] == 0.0
    assert out[1:] == _NATIVE_KALPY_OUTPUT


def test_both_recovery_flags_together_yield_all_four():
    out = extract_boundary_errors(
        _ALIGNMENT_PATH, include_utterance_edges=True, include_gap_adjacent=True
    )
    assert len(out) == 4
    assert [b["following_reference_phone"] for b in out] == ["sil", "dh", "ah", "sil"]


def test_utterance_edge_sentinel_categorizes_as_silence():
    assert categorize_ref(UTTERANCE_EDGE, "timit") == "silence"
    assert categorize_test(UTTERANCE_EDGE, "ay", "arpa", "timit") == "silence"


def test_insertion_or_deletion_step_itself_never_yields_a_boundary():
    # index 1 (the "-"/sp insertion step) must never itself produce a
    # following_reference_phone == "-" entry, under any flag combination.
    for kwargs in ({}, {"include_gap_adjacent": True}, {"include_utterance_edges": True}):
        out = extract_boundary_errors(_ALIGNMENT_PATH, **kwargs)
        assert all(b["following_reference_phone"] != "-" for b in out)
        assert all(b["following_test_phone"] != "-" for b in out)
