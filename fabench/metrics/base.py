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

"""Boundary-metric contract + registry.

A **metric** maps a pool of :class:`~fabench.score.boundary.BoundaryError` to a
single scalar that becomes one leaderboard column. Each metric lives in its own
module (``mae.py``, ``threshold_accuracy.py``, …) and registers an *instance*
here; importing :mod:`fabench.metrics` imports those modules so the registry is
populated as a side effect.

This is deliberately the *same* registry+contract pattern as
:mod:`fabench.aligners`: to add a metric, drop a file and register an instance —
no edits to the scoring engine.

Scope note: metrics here consume a boundary-error pool. Count-based measures
(ARR / InsertRate in :mod:`fabench.score.recall`) take matched/gold/hyp *counts*,
a different input contract, so they are a separate family — not in this registry.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from fabench.score.boundary import BoundaryError


@runtime_checkable
class BoundaryMetric(Protocol):
    #: leaderboard column name, e.g. ``"mae_ms"``
    key: str
    #: reporting unit, e.g. ``"ms"`` or ``"%"``
    unit: str
    #: True if larger is better, False if smaller is better, None if it is a bias
    #: whose ideal is 0 (e.g. signed error).
    higher_is_better: bool | None

    def compute(self, errs: Sequence[BoundaryError]) -> float:
        ...


_REGISTRY: dict[str, BoundaryMetric] = {}


def register(metric: BoundaryMetric) -> BoundaryMetric:
    """Register a metric instance under its ``key`` (returns it, for convenience)."""
    if metric.key in _REGISTRY:
        raise KeyError(f"duplicate metric key {metric.key!r}")
    _REGISTRY[metric.key] = metric
    return metric


def all_metrics() -> dict[str, BoundaryMetric]:
    """All registered metrics, in registration order (deterministic)."""
    return dict(_REGISTRY)


def get_metric(key: str) -> BoundaryMetric:
    return _REGISTRY[key]


def compute_all(errs: Sequence[BoundaryError]) -> dict[str, float]:
    """Every registered metric evaluated on one error pool -> {key: value}."""
    return {key: m.compute(errs) for key, m in _REGISTRY.items()}
