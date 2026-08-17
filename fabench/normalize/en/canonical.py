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

"""Canonical phone inventory + manner classes (Plan S2).

We use the standard **TIMIT-39** reduced set (Lee & Hon 1989 folding, as in the
Kaldi/HTK TIMIT recipes): 39 symbols including ``sil`` and the flap ``dx``. Every
aligner's and corpus's inventory maps into this set so phones are comparable
(fabench.normalize.maps). The choice is documented here so the benchmark's
scoring granularity is unambiguous.
"""

from __future__ import annotations

# The 39 canonical symbols.
CANONICAL_39: tuple[str, ...] = (
    "sil",
    # stops (+ flap dx)
    "b", "d", "g", "p", "t", "k", "dx",
    # affricates
    "ch", "jh",
    # fricatives (incl. /h/)
    "s", "sh", "z", "f", "th", "v", "dh", "hh",
    # nasals
    "m", "n", "ng",
    # liquids / glides
    "l", "r", "w", "y",
    # vowels (monophthongs, diphthongs, rhotic)
    "aa", "ae", "ah", "aw", "ay", "eh", "er", "ey",
    "ih", "iy", "ow", "oy", "uh", "uw",
)

assert len(CANONICAL_39) == 39, len(CANONICAL_39)
CANONICAL_SET = frozenset(CANONICAL_39)

# Coarse manner class per canonical phone (Plan 5.4 buckets).
_MANNER = {
    "sil": "silence",
    **{p: "stop" for p in ("b", "d", "g", "p", "t", "k", "dx")},
    **{p: "fricative" for p in ("ch", "jh", "s", "sh", "z", "f", "th", "v", "dh", "hh")},
    **{p: "nasal" for p in ("m", "n", "ng")},
    **{p: "liquid" for p in ("l", "r", "w", "y")},
    **{
        p: "vowel"
        for p in (
            "aa", "ae", "ah", "aw", "ay", "eh", "er", "ey",
            "ih", "iy", "ow", "oy", "uh", "uw",
        )
    },
}
assert set(_MANNER) == CANONICAL_SET


def manner_of(canonical_label: str) -> str:
    """Coarse manner class of a canonical phone; 'silence' for unknown/edge."""
    return _MANNER.get(canonical_label, "silence")


# Finer manner taxonomy used by the MFA-2026 paper (arXiv:2606.18466) purely for
# its boundary-exclusion rule: "boundaries where the manner categories of the
# reference and hypothesis phones differed were excluded from evaluation." Its
# classes are vowel / stop / approximant / nasal / fricative / sibilant-affricate,
# with "flaps treated as stops" and "rhotics collapsed with rhotic vowels". Kept
# separate from ``manner_of`` (the coarse 6-class *display* taxonomy) so the
# per-type report is unaffected; this map is consulted only when
# ``scoring.manner_match`` is enabled.
_MANNER_PAPER = {
    "sil": "silence",
    **{p: "stop" for p in ("b", "d", "g", "p", "t", "k", "dx")},   # dx flap -> stop
    **{p: "sibilant_affricate" for p in ("s", "sh", "z", "ch", "jh")},
    **{p: "fricative" for p in ("f", "th", "v", "dh", "hh")},
    **{p: "nasal" for p in ("m", "n", "ng")},
    **{p: "approximant" for p in ("l", "w", "y")},
    **{p: "rhotic" for p in ("r", "er")},         # rhotic collapsed with rhotic vowel
    **{
        p: "vowel"
        for p in (
            "aa", "ae", "ah", "aw", "ay", "eh", "ey",
            "ih", "iy", "ow", "oy", "uh", "uw",
        )
    },
}
assert set(_MANNER_PAPER) == CANONICAL_SET, set(_MANNER_PAPER) ^ CANONICAL_SET


def manner_class_paper(canonical_label: str) -> str:
    """Manner class under the paper's exclusion taxonomy (8 classes incl.
    silence/rhotic). Unknown/edge -> 'silence'."""
    return _MANNER_PAPER.get(canonical_label, "silence")
