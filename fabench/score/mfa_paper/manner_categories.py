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

"""Manner-category tables for the ``mfa_paper`` scoring protocol.

Ported **verbatim** from the MFA-2026 paper's own benchmark repo
(``mfa-interspeech2026/analysis/data_prep.R``, commit ``df8e2bfc0c628a45b0de78ed
104f862d49c93c1f``, MIT license — see ``vendor/THIRD_PARTY_NOTICES.md``), *not*
reused from :func:`fabench.normalize.en.canonical.manner_class_paper`. That function
is fabench's own 8-class reconstruction of the paper's manner taxonomy from prose
and does not match this table: there is no separate "rhotic" class here (``er``/
``axr`` sit inside reference-side ``vowel``), and the categories are keyed to each
system's *raw* native alphabet, not a shared canonical one.

Only the four aligner families FA-Bench actually runs are ported: ``arpa`` (MFA —
FA-Bench's MFA adapter uses the ``english_us_arpa`` ARPABET model, not MFA 3.0's
narrow-IPA phone set, so the R script's separate ``mfa=`` table is not needed),
``charsiu``, ``maps``, ``bournemouth`` (BFA). The ``maus``/``gp``/``sppas``/
``julius``/``koreanforcedaligner`` test tables and the ``seoul_corpus``/``csj``
reference tables are out of scope (FA-Bench only covers TIMIT/Buckeye).
"""

from __future__ import annotations

from collections.abc import Mapping

CategoryTable = Mapping[str, frozenset]

# --------------------------------------------------------------------------
# test_phone_lists (data_prep.R lines 59-150) — keyed by aligner family, i.e.
# the raw label alphabet each *aligner* emits.
# --------------------------------------------------------------------------
TEST_PHONE_CATEGORIES: dict[str, CategoryTable] = {
    "arpa": {
        "vowel": frozenset({
            "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW",
            "AA1", "AE1", "AH1", "AO1", "AW1", "AY1", "EH1", "ER1", "EY1", "IH1", "IY1", "OW1", "OY1", "UH1", "UW1",
            "AA2", "AE2", "AH2", "AO2", "AW2", "AY2", "EH2", "ER2", "EY2", "IH2", "IY2", "OW2", "OY2", "UH2", "UW2",
            "AA0", "AE0", "AH0", "AO0", "AW0", "AY0", "EH0", "ER0", "EY0", "IH0", "IY0", "OW0", "OY0", "UH0", "UW0",
        }),
        "stop": frozenset({"B", "P", "D", "T", "G", "K"}),
        "approximant": frozenset({"R", "L", "Y", "W"}),
        "nasal": frozenset({"M", "N", "NG"}),
        "fricative": frozenset({"DH", "TH", "HH", "F", "V"}),
        "sibilant": frozenset({"S", "SH", "Z", "ZH", "CH", "JH"}),
        "silence": frozenset({"sil"}),
    },
    "charsiu": {
        "vowel": frozenset({
            "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW",
            "AA1", "AE1", "AH1", "AO1", "AW1", "AY1", "EH1", "ER1", "EY1", "IH1", "IY1", "OW1", "OY1", "UH1", "UW1",
            "AA2", "AE2", "AH2", "AO2", "AW2", "AY2", "EH2", "ER2", "EY2", "IH2", "IY2", "OW2", "OY2", "UH2", "UW2",
            "AA0", "AE0", "AH0", "AO0", "AW0", "AY0", "EH0", "ER0", "EY0", "IH0", "IY0", "OW0", "OY0", "UH0", "UW0",
        }),
        "stop": frozenset({"B", "P", "D", "T", "G", "K"}),
        "approximant": frozenset({"R", "L", "Y", "W"}),
        "nasal": frozenset({"M", "N", "NG"}),
        "fricative": frozenset({"DH", "TH", "HH", "F", "V"}),
        "sibilant": frozenset({"S", "SH", "Z", "ZH", "CH", "JH"}),
        "silence": frozenset({"sil", "[SIL]", "sil [SIL]", "[SIL] sil"}),
    },
    "maps": {
        "vowel": frozenset({
            "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW",
            "AA1", "AE1", "AH1", "AO1", "AW1", "AY1", "EH1", "ER1", "EY1", "IH1", "IY1", "OW1", "OY1", "UH1", "UW1",
            "AA2", "AE2", "AH2", "AO2", "AW2", "AY2", "EH2", "ER2", "EY2", "IH2", "IY2", "OW2", "OY2", "UH2", "UW2",
            "AA0", "AE0", "AH0", "AO0", "AW0", "AY0", "EH0", "ER0", "EY0", "IH0", "IY0", "OW0", "OY0", "UH0", "UW0",
        }),
        "stop": frozenset({"B", "P", "D", "T", "G", "K"}),
        "approximant": frozenset({"R", "L", "Y", "W"}),
        "nasal": frozenset({"M", "N", "NG"}),
        "fricative": frozenset({"DH", "TH", "HH", "F", "V"}),
        "sibilant": frozenset({"S", "SH", "Z", "ZH", "CH", "JH"}),
        "silence": frozenset({"sil", "H#"}),
    },
    "bournemouth": {
        "vowel": frozenset({
            "a", "a:", "æ", "aɪ", "aʊ", "ɔ", "ɔɪ", "e", "ə", "ɚ", "eɪ", "ɛ", "i", "ɪ", "i:",
            "j e", "j ɛ", "j o", "j u", "j ʌ", "ɯ", "o", "o:", "oʊ", "u", "ʊ", "u:", "ʌ",
            "w e", "w ɛ", "w i", "w ʌ",
        }),
        "stop": frozenset({"b", "d", "g", "k", "p", "q", "t"}),
        "approximant": frozenset({"j", "l", "ɹ", "ɾ", "w"}),
        "nasal": frozenset({"m", "n", "ŋ"}),
        "fricative": frozenset({"ç", "ð", "f", "h", "v", "θ"}),
        "sibilant": frozenset({"ɕ", "s", "ʃ", "z", "ʒ", "dʒ", "ts", "tʃ"}),
        "silence": frozenset({"sil"}),
    },
}

# --------------------------------------------------------------------------
# reference_phone_lists (data_prep.R lines 165-202) — keyed by corpus.
# --------------------------------------------------------------------------
REFERENCE_PHONE_CATEGORIES: dict[str, CategoryTable] = {
    "timit": {
        "vowel": frozenset({
            "aa", "aan", "ao", "aon", "ae", "aen", "ah", "ahn", "aw", "awn", "ay", "ayn",
            "eh", "ehn", "er", "ern", "ey", "eyn", "ih", "ihn", "iy", "iyn", "ow", "own",
            "oy", "oyn", "uw", "uwn", "uh", "uhn", "ax", "ax-h", "ix", "ux", "axr",
            "ih r", "iy r",
        }),
        "stop": frozenset({
            "dx", "b", "p", "t", "d", "k", "g", "q", "bcl", "pcl", "tcl", "tcl q", "dcl",
            "kcl", "gcl", "t w", "g w", "k w", "d w", "p w", "b w",
        }),
        "approximant": frozenset({"el", "l", "r", "y", "w"}),
        "nasal": frozenset({"en", "n", "nx", "em", "m", "eng", "ng"}),
        "fricative": frozenset({"th", "dh", "f", "v", "hh", "hv"}),
        "sibilant": frozenset({"s", "z", "sh", "zh", "ch", "jh"}),
        # "sil" is the paper's own already-normalized label; "h#" is FA-Bench's
        # own TIMIT gold ingest's native silence marker (confirmed empirically
        # against real staged data) — both must categorize as silence, or every
        # TIMIT silence boundary falls to "unknown" and gets dropped by the
        # filter for a reason that has nothing to do with the real mechanism.
        "silence": frozenset({"sil", "h#"}),
    },
    "buckeye": {
        "vowel": frozenset({
            "aa", "aan", "ao", "aon", "ae", "aen", "ah", "ahn", "aw", "awn", "ay", "ayn",
            "eh", "ehn", "er", "ern", "ey", "eyn", "ih", "ihn", "iy", "iyn", "ow", "own",
            "oy", "oyn", "uw", "uwn", "uh", "uhn", "ih r", "iy r",
        }),
        "stop": frozenset({"b", "p", "t", "d", "k", "g", "dx", "tq"}),
        "approximant": frozenset({"el", "l", "r", "y", "w"}),
        "nasal": frozenset({"en", "n", "nx", "em", "m", "eng", "ng"}),
        "fricative": frozenset({"th", "dh", "f", "v", "hh"}),
        "sibilant": frozenset({"s", "z", "sh", "zh", "ch", "jh"}),
        # "SIL" is FA-Bench's own Buckeye gold ingest's native silence marker
        # (confirmed empirically) — see the TIMIT "h#" comment above. "!sil"
        # is the kaldi swbd word form the ingest emits now; both are kept so
        # previously staged data still scores.
        "silence": frozenset({"sil", "SIL", "!sil"}),
    },
}

UNKNOWN = "unknown"

# Placeholder for a boundary reconstructed at the very start of an utterance
# (fabench/score/mfa_paper/cell.py::extract_boundary_errors, include_utterance_edges)
# — there is no real "previous phone" there, so treat it as silence, exactly
# matching fabench's old dual-edge convention ("utterance edge behaves like
# silence", fabench/score/boundary.py::manner_at). Kept as a distinct sentinel
# (not literal "sil") so it's unambiguous in diagnostics that this wasn't a real
# matched silence phone.
UTTERANCE_EDGE = "<utterance_edge>"

# data_prep.R lines 215-217: a targeted override, not a symmetric class merge.
# Trimmed to the ARPABET subset actually reachable by FA-Bench's aligners (the
# full R list also has MAUS's SAMPA rhotics "3:"/"3`"/"3:r"/"r\\", irrelevant
# here since FA-Bench doesn't run MAUS). Only fires for timit/buckeye, matching
# the R script's own corpus guard.
_RHOTIC_TEST_OVERRIDE = frozenset({"ER0", "ER1", "ER2", "R"})
_RHOTIC_REF_OVERRIDE = frozenset({"axr", "r", "er"})
_RHOTIC_CORPORA = frozenset({"timit", "buckeye"})


def categorize(label: str, table: CategoryTable) -> str:
    """Look up ``label``'s manner category in ``table``; ``"unknown"`` if absent."""
    for category, labels in table.items():
        if label in labels:
            return category
    return UNKNOWN


def categorize_ref(label: str, corpus: str) -> str:
    if label == UTTERANCE_EDGE:
        return "silence"
    return categorize(label, REFERENCE_PHONE_CATEGORIES[corpus])


def categorize_test(test_label: str, ref_label: str, aligner_key: str, corpus: str) -> str:
    """Test-side category, including the rhotic override.

    When the test label is an ARPABET rhotic (``R``/``ER0-2``) aligned against a
    reference ``axr``/``r``/``er``, the test category is force-overwritten to
    whatever the *reference* label's own category is (data_prep.R lines 215-217) —
    rescuing what would otherwise be an ``approximant`` (test) vs. ``vowel``
    (reference) mismatch for a very common TIMIT/Buckeye pattern. This mirrors the
    reference label's category directly rather than hardcoding "vowel", so it
    degrades correctly for the ``r``-vs-``R`` case (already ``approximant`` on
    both sides — the override is then a no-op).
    """
    if test_label == UTTERANCE_EDGE:
        return "silence"
    if (
        corpus in _RHOTIC_CORPORA
        and test_label in _RHOTIC_TEST_OVERRIDE
        and ref_label in _RHOTIC_REF_OVERRIDE
    ):
        return categorize_ref(ref_label, corpus)
    return categorize(test_label, TEST_PHONE_CATEGORIES[aligner_key])
