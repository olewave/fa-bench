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

"""FA-Bench analytics registry (breakdowns / diagnostics).

An *analytic* turns an error pool into a table diagnostic (a distribution, a
per-partition split) — as opposed to a :mod:`fabench.metrics` *metric*, which is
one scalar leaderboard column. Importing this package imports the analytic
modules so registration side effects fire and :func:`all_analytics` is populated:

    >>> from fabench import analyze as analytics
    >>> sorted(analyzers.all_analytics())
    ['mae_decomposition', 'silence_edge', 'tail_percentiles']

Boundary-error extraction (gold + hyp -> tagged error lists) is in
:mod:`fabench.analyze.errors`. See ``CONTRIBUTING.md`` to add one.
"""
# Import for registration side effects (keep after the base import).
from fabench.analyze import errors, silence_edge, tail_stats  # noqa: F401
from fabench.analyze.base import (
    Analytic,
    all_analytics,
    get_analytic,
    register,
)

__all__ = [
    "Analytic",
    "all_analytics",
    "errors",
    "get_analytic",
    "register",
]
