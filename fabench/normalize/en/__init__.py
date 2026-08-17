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

"""English (``en``) normalization content: the canonical phone inventory, the
per-source label->canonical maps, and the manner classes. The language-agnostic
machinery (``canonicalize``/``make_canon``/``unmapped_rate`` + the DELETE/UNMAPPED
sentinels) stays in :mod:`fabench.normalize`.

Accent
------
The canonical set is TIMIT-39 / ARPABET, i.e. **General American (US)** — so
``us`` is the only implemented accent. **UK (RP)** genuinely differs (non-rhotic;
a larger vowel inventory — LOT/PALM, TRAP/BATH) and is a recognized but
**not-yet-populated** accent: adding it means accent-specific source maps (and a
few fold rules) here, reachable via :func:`sources`, not a new language.
"""
from __future__ import annotations

from fabench.normalize.en.canonical import (
    CANONICAL_39,
    CANONICAL_SET,
    manner_class_paper,
    manner_of,
)
from fabench.normalize.en.maps import (
    ARPABET_TO_39,
    BUCKEYE_TO_39,
    IPA_TO_39,
    TIMIT61_TO_39,
    norm_arpabet,
    norm_buckeye,
    norm_ipa,
    norm_timit,
)

#: Accents with populated mappings. GA (US) today; RP ("uk") is a planned variant.
IMPLEMENTED_ACCENTS: tuple[str, ...] = ("us",)
DEFAULT_ACCENT = "us"

# source key -> (mapping table, label normalizer). Aligner adapters declare their
# source (AlignerAdapter.source); gold corpora use the corpus name.
_SOURCES_US: dict = {
    "timit": (TIMIT61_TO_39, norm_timit),
    "buckeye": (BUCKEYE_TO_39, norm_buckeye),
    "l2arctic": (ARPABET_TO_39, norm_arpabet),
    "arpabet": (ARPABET_TO_39, norm_arpabet),
    "mfa": (ARPABET_TO_39, norm_arpabet),
    "torchaudio": (ARPABET_TO_39, norm_arpabet),
    "whisperx": (ARPABET_TO_39, norm_arpabet),
    "ipa": (IPA_TO_39, norm_ipa),
    "charsiu": (IPA_TO_39, norm_ipa),
}


def sources(accent: str = DEFAULT_ACCENT) -> dict:
    """``source -> (table, normalizer)`` for the given English accent.

    Only ``"us"`` (General American) is populated; ``"uk"`` (RP) is recognized
    but not yet populated (raises :class:`NotImplementedError`).
    """
    if accent == "us":
        return _SOURCES_US
    if accent == "uk":
        raise NotImplementedError(
            "English 'uk' (RP) source mappings are not populated yet — see "
            "fabench/normalize/en/README.md"
        )
    raise ValueError(f"unknown English accent {accent!r}; known: {IMPLEMENTED_ACCENTS}")


#: Default (US) source registry — back-compat top-level constant.
SOURCES = _SOURCES_US

__all__ = [
    "ARPABET_TO_39",
    "BUCKEYE_TO_39",
    "CANONICAL_39",
    "CANONICAL_SET",
    "DEFAULT_ACCENT",
    "IMPLEMENTED_ACCENTS",
    "IPA_TO_39",
    "SOURCES",
    "TIMIT61_TO_39",
    "manner_class_paper",
    "manner_of",
    "norm_arpabet",
    "norm_buckeye",
    "norm_ipa",
    "norm_timit",
    "sources",
]
