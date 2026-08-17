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

"""Ported data_prep.R manner-category tables (mfa_paper protocol) — spot-checks
against the verbatim R source, including the targeted rhotic override."""

from fabench.score.mfa_paper.manner_categories import (
    TEST_PHONE_CATEGORIES,
    UNKNOWN,
    categorize,
    categorize_ref,
    categorize_test,
)


def test_reference_categories_timit():
    assert categorize_ref("dx", "timit") == "stop"
    assert categorize_ref("bcl", "timit") == "stop"
    assert categorize_ref("sil", "timit") == "silence"
    assert categorize_ref("er", "timit") == "vowel"
    assert categorize_ref("r", "timit") == "approximant"
    assert categorize_ref("axr", "timit") == "vowel"
    assert categorize_ref("nonexistent_phone", "timit") == UNKNOWN


def test_reference_categories_buckeye_differs_slightly_from_timit():
    # buckeye's stop list includes "tq" (timit doesn't); both include "dx".
    assert categorize_ref("tq", "buckeye") == "stop"
    assert categorize_ref("tq", "timit") == UNKNOWN


def test_test_categories_arpa():
    assert categorize("B", {"stop": frozenset({"B"})}) == "stop"
    assert categorize_test("R", "w", "arpa", "timit") == "approximant"  # no override fires


def test_rhotic_override_rescues_vowel_vs_approximant_mismatch():
    """data_prep.R lines 215-217: bare ARPABET "R" plain-lookups as approximant
    (unlike "ER0-2", which arpa's own table already puts in vowel — a no-op case
    for the override). Paired against reference er/axr on timit/buckeye, the test
    category is force-overwritten to the *reference* label's own category (vowel)
    — not hardcoded, so it degrades correctly for the r-vs-R case below (already
    approximant on both sides). Buckeye's reference set has no "axr" at all (only
    TIMIT's does), so "er" is used for the buckeye case."""
    assert categorize("R", TEST_PHONE_CATEGORIES["arpa"]) == "approximant"  # sanity: plain lookup
    assert categorize_test("R", "er", "arpa", "timit") == "vowel"
    assert categorize_test("R", "axr", "arpa", "timit") == "vowel"
    assert categorize_test("R", "er", "arpa", "buckeye") == "vowel"
    # r (reference) categorizes as approximant, not vowel -> override is a no-op
    assert categorize_test("R", "r", "arpa", "timit") == "approximant"


def test_rhotic_override_does_not_fire_outside_timit_buckeye():
    # corpus guard blocks the override for any other corpus -> falls back to the
    # plain arpa lookup (approximant), not the reference-side vowel category.
    assert categorize_test("R", "er", "arpa", "seoul_corpus") == "approximant"


def test_rhotic_override_requires_both_sides_in_the_override_sets():
    # test label in override set, but ref label is not axr/r/er -> no override,
    # falls back to the plain arpa lookup (approximant).
    assert categorize_test("R", "iy", "arpa", "timit") == "approximant"


def test_bournemouth_categories():
    assert categorize_ref("b", "timit") == "stop"  # sanity: same phone, ref side
    assert categorize("ɹ", TEST_PHONE_CATEGORIES["bournemouth"]) == "approximant"
    assert categorize("dʒ", TEST_PHONE_CATEGORIES["bournemouth"]) == "sibilant"
    assert categorize("sil", TEST_PHONE_CATEGORIES["bournemouth"]) == "silence"


def test_charsiu_and_maps_silence_variants():
    assert categorize("[SIL]", TEST_PHONE_CATEGORIES["charsiu"]) == "silence"
    assert categorize("H#", TEST_PHONE_CATEGORIES["maps"]) == "silence"
