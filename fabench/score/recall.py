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

"""Alignment recall + insertion — the anti-gaming pair (Plan 5.6).

MAE/TA are computed on the matched path only; deletions/insertions are
quarantined here so a system cannot flatter its MAE by skipping hard phones
without paying in ARR.
"""

from __future__ import annotations


def arr(n_matched: int, n_gold: int) -> float:
    """Alignment Recall Rate = matched_gold / total_gold."""
    return n_matched / n_gold if n_gold else float("nan")


def insertion_rate(n_matched: int, n_hyp: int) -> float:
    """InsertRate = unmatched_hyp / total_hyp (each match consumes one hyp)."""
    return (n_hyp - n_matched) / n_hyp if n_hyp else float("nan")
