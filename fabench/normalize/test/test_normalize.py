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

"""Phone-set normalization (Plan S2) — map correctness + manner classes."""

import pytest

from fabench.normalize import (
    CANONICAL_39,
    DELETE,
    UNMAPPED,
    canonicalize,
    make_canon,
    manner_class_paper,
    manner_of,
    unmapped_rate,
)


def test_canonical_inventory_size_and_manner_total():
    assert len(CANONICAL_39) == 39
    assert len(set(CANONICAL_39)) == 39
    # every canonical phone has a manner class
    for p in CANONICAL_39:
        assert manner_of(p) in {
            "silence", "stop", "fricative", "nasal", "liquid", "vowel"
        }


def test_manner_class_paper_taxonomy():
    """Paper (arXiv:2606.18466) exclusion taxonomy: flap->stop, rhotic collapsed
    with rhotic vowels, sibilants/affricates split from plain fricatives."""
    # every canonical phone classified into one of the 8 paper classes
    classes = {manner_class_paper(p) for p in CANONICAL_39}
    assert classes <= {
        "silence", "stop", "nasal", "approximant", "rhotic",
        "fricative", "sibilant_affricate", "vowel",
    }
    assert manner_class_paper("dx") == "stop"              # flap -> stop
    assert manner_class_paper("r") == manner_class_paper("er") == "rhotic"  # collapsed
    # sibilants + affricates are one class, distinct from plain fricatives
    assert manner_class_paper("s") == manner_class_paper("ch") == "sibilant_affricate"
    assert manner_class_paper("f") == manner_class_paper("th") == "fricative"
    assert manner_class_paper("s") != manner_class_paper("f")
    assert manner_class_paper("l") == manner_class_paper("w") == "approximant"
    assert manner_class_paper("r") != manner_class_paper("l")  # rhotic != approximant


def test_per_aligner_mapping_gaps_fixed():
    """Charsiu [SIL] and BFA espeak rhotics/syllabics/markers must normalize, not
    fall through to UNMAPPED."""
    assert canonicalize("[SIL]", "arpabet") == "sil"      # charsiu silence
    assert canonicalize("ɑːɹ", "ipa") == "er"             # r-colored vowel -> rhotic
    assert canonicalize("ʊɹ", "ipa") == "er"
    assert canonicalize("əl", "ipa") == "l"               # syllabic l
    assert canonicalize("n̩", "ipa") == "n"                # syllabic n
    assert canonicalize("ᵻ", "ipa") == "ih"               # barred i
    assert canonicalize("-", "ipa") == DELETE             # espeak boundary marker


@pytest.mark.parametrize(
    "label,expect",
    [
        ("ao", "aa"),   # folded to aa
        ("ax", "ah"),
        ("ix", "ih"),
        ("axr", "er"),
        ("zh", "sh"),
        ("ux", "uw"),
        ("hv", "hh"),
        ("el", "l"),
        ("em", "m"),
        ("en", "n"),
        ("nx", "n"),
        ("eng", "ng"),
        ("h#", "sil"),  # boundary silence
        ("pau", "sil"),
        ("kcl", "sil"), # closure -> silence
        ("iy", "iy"),
    ],
)
def test_timit61_folding(label, expect):
    assert canonicalize(label, "timit") == expect


def test_timit_glottal_stop_deleted():
    assert canonicalize("q", "timit") == DELETE


def test_arpabet_stress_stripped():
    assert canonicalize("AH0", "arpabet") == "ah"
    assert canonicalize("IY1", "arpabet") == "iy"
    assert canonicalize("ER2", "mfa") == "er"
    assert canonicalize("spn", "mfa") == "sil"


def test_buckeye_specifics():
    assert canonicalize("tq", "buckeye") == DELETE   # glottal stop
    assert canonicalize("nx", "buckeye") == "n"
    assert canonicalize("NOISE", "buckeye") == "sil"
    assert canonicalize("IVER", "buckeye") == DELETE


def test_ipa_common():
    assert canonicalize("ʃ", "charsiu") == "sh"
    assert canonicalize("θ", "charsiu") == "th"
    assert canonicalize("ɪ", "charsiu") == "ih"
    assert canonicalize("ŋ", "charsiu") == "ng"


def test_unmapped_is_flagged_not_crashed():
    assert canonicalize("zzzz", "timit") == UNMAPPED
    rate, counter = unmapped_rate(["iy", "ao", "zzzz", "blah"], "timit")
    assert rate == pytest.approx(0.5)  # 2 of 4 unmapped
    assert counter["zzzz"] == 1 and counter["blah"] == 1


def test_make_canon_binds_source():
    f = make_canon("timit")
    assert f("ao") == "aa"
    assert f("q") == DELETE


def test_full_timit61_inventory_maps():
    # the entire canonical TIMIT-61 symbol set must map (rate 0), sanity for S2.
    timit61 = [
        "aa","ae","ah","ao","aw","ax","ax-h","axr","ay","b","bcl","ch","d","dcl",
        "dh","dx","eh","el","em","en","eng","epi","er","ey","f","g","gcl","h#",
        "hh","hv","ih","ix","iy","jh","k","kcl","l","m","n","ng","nx","ow","oy",
        "p","pau","pcl","q","r","s","sh","t","tcl","th","uh","uw","ux","v","w",
        "y","z","zh",
    ]
    rate, unmapped = unmapped_rate(timit61, "timit")
    assert rate == 0.0, f"unmapped TIMIT-61 symbols: {unmapped}"
