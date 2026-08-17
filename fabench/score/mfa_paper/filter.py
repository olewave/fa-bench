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

"""Port of ``data_prep.R``'s ``filtered_boundary_data`` predicate (line 253):

    filtered_boundary_data = boundary_data %>% subset(
      previous_reference_category == previous_test_category &
      following_reference_category == following_test_category &
      following_test_category != 'unknown' & following_reference_category != 'unknown' &
      previous_test_category != "unknown" & previous_reference_category != "unknown"
    )

This is the *second*, separate filtering stage the MFA-2026 paper's benchmark repo
applies on top of ``kalpy.evaluation.align_phones``'s raw ``boundary_errors`` before
producing Table 5's numbers. It is bespoke paper/benchmark-repo analysis code, not
part of MFA's shipped user guide/product — unlike the ``align_phones`` bridge, this
part is genuinely authored here, ported from the R source rather than called
directly.

Silence is treated as an ordinary manner category (kept when both sides agree),
not specially excluded — matching the R script exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

from fabench.score.mfa_paper.manner_categories import UNKNOWN, categorize_ref, categorize_test


def filter_boundaries(
    records: Sequence[dict],
    *,
    aligner_key: str,
    corpus: str,
) -> list[dict]:
    """Keep only records whose previous/following manner categories agree between
    reference and test on *both* sides, per data_prep.R's ``filtered_boundary_data``.

    Each record must carry the four raw label fields kalpy's ``align_phones``
    already returns: ``previous_reference_phone``, ``previous_test_phone``,
    ``following_reference_phone``, ``following_test_phone``. Records are passed
    through unmodified (not copied/mutated) — only membership in the output list
    changes.
    """
    out = []
    for r in records:
        prev_ref = categorize_ref(r["previous_reference_phone"], corpus)
        foll_ref = categorize_ref(r["following_reference_phone"], corpus)
        prev_test = categorize_test(
            r["previous_test_phone"], r["previous_reference_phone"], aligner_key, corpus
        )
        foll_test = categorize_test(
            r["following_test_phone"], r["following_reference_phone"], aligner_key, corpus
        )
        if UNKNOWN in (prev_ref, foll_ref, prev_test, foll_test):
            continue
        if prev_ref != prev_test or foll_ref != foll_test:
            continue
        out.append(r)
    return out
