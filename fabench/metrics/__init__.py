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

"""FA-Bench metric registry (one metric per module).

Importing this package imports each metric module so registration side effects
fire and :func:`all_metrics` is populated:

    >>> from fabench import metrics
    >>> sorted(metrics.all_metrics())
    ['mae_ms', 'median_ms', 'signed_ms', 'ta10', 'ta25', 'ta50']
    >>> metrics.compute_all(errs)          # {key: scalar} for a boundary-error pool

See :mod:`fabench.metrics.base` for the contract, and ``CONTRIBUTING.md`` for
how to add one.
"""
# Import for registration side effects (keep after the base import).
from fabench.metrics import mae, median, signed, threshold_accuracy  # noqa: F401
from fabench.metrics.base import (
    BoundaryMetric,
    all_metrics,
    compute_all,
    get_metric,
    register,
)

__all__ = [
    "BoundaryMetric",
    "all_metrics",
    "compute_all",
    "get_metric",
    "register",
]
