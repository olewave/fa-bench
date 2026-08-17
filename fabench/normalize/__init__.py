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

"""Phone-set normalization API (Plan S2).

Language-agnostic machinery lives here; the per-language content — canonical
inventory, source->canonical maps, manner classes — lives in language
subpackages. Today the only language is :mod:`fabench.normalize.en` (English;
US/General American, with a ``uk`` accent hook). Add a language as a sibling
package and re-export it here.

``canonicalize(label, source)`` returns a canonical symbol, the sentinel
:data:`DELETE` (label intentionally dropped by the standard folding, e.g. glottal
stop), or :data:`UNMAPPED` (label we do not recognize — counted and logged, never
silently dropped).
"""
from __future__ import annotations

from collections.abc import Callable

from fabench.normalize import en

# --- language-agnostic sentinels (NUL-prefixed: can't collide with a label) ---
DELETE = "\x00DELETE"
UNMAPPED = "\x00UNMAPPED"

# --- English re-exports (the default/only language today) -------------------
CANONICAL_39 = en.CANONICAL_39
CANONICAL_SET = en.CANONICAL_SET
manner_of = en.manner_of
manner_class_paper = en.manner_class_paper
ARPABET_TO_39 = en.ARPABET_TO_39
BUCKEYE_TO_39 = en.BUCKEYE_TO_39
IPA_TO_39 = en.IPA_TO_39
TIMIT61_TO_39 = en.TIMIT61_TO_39
norm_arpabet = en.norm_arpabet
norm_buckeye = en.norm_buckeye
norm_ipa = en.norm_ipa
norm_timit = en.norm_timit
#: source -> (table, normalizer) for the default (US) accent — back-compat.
SOURCES = en.SOURCES

__all__ = [
    "CANONICAL_39",
    "CANONICAL_SET",
    "DELETE",
    "SOURCES",
    "UNMAPPED",
    "canonicalize",
    "make_canon",
    "manner_class_paper",
    "manner_of",
    "unmapped_rate",
]


def canonicalize(label: str, source: str, accent: str = en.DEFAULT_ACCENT) -> str:
    """Map one source label -> canonical symbol / DELETE / UNMAPPED.

    ``accent`` selects the English accent's source maps (only ``"us"`` populated).
    """
    srcs = en.sources(accent)
    if source not in srcs:
        raise KeyError(f"unknown normalization source {source!r}; known: {sorted(srcs)}")
    table, norm = srcs[source]
    key = norm(label)
    # Buckeye markers can be case-sensitive; also try lowercased ARPABET.
    if key in table:
        val = table[key]
    elif key.lower() in table:
        val = table[key.lower()]
    else:
        return UNMAPPED
    return DELETE if val is None else val


def make_canon(source: str, accent: str = en.DEFAULT_ACCENT) -> Callable[[str], str]:
    """Return a single-arg canonicalizer bound to ``source`` (for score_pair)."""
    return lambda label: canonicalize(label, source, accent)


def unmapped_rate(labels, source: str, accent: str = en.DEFAULT_ACCENT):
    """(rate, Counter of unmapped labels) over an iterable of raw labels."""
    from collections import Counter

    total = 0
    unmapped: Counter[str] = Counter()
    for lab in labels:
        total += 1
        if canonicalize(lab, source, accent) == UNMAPPED:
            unmapped[lab] += 1
    rate = (sum(unmapped.values()) / total) if total else 0.0
    return rate, unmapped
