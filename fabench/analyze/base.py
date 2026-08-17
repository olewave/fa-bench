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

"""Analytic contract + registry.

An **analytic** maps an error pool to a *table/diagnostic* (a distribution, a
per-partition split) — many numbers — unlike a :mod:`fabench.metrics` **metric**,
which yields one scalar leaderboard column. Analytics are intentionally
heterogeneous in input (some take ``(abs_ms, edge)`` pairs, some take a plain
``abs_ms`` array), so this registry is a lightweight *catalogue* — key + human
metadata + the pure callable — rather than a rigid single-signature protocol.

Pure compute lives in the analytic modules; orchestration (which aligner runs to
read, loading gold, writing CSVs) lives in the report modules beside this
file -- see fabench/analyze/README.md.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Analytic:
    key: str
    title: str
    description: str
    fn: Callable

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


_REGISTRY: dict[str, Analytic] = {}


def register(analytic: Analytic) -> Analytic:
    if analytic.key in _REGISTRY:
        raise KeyError(f"duplicate analytic key {analytic.key!r}")
    _REGISTRY[analytic.key] = analytic
    return analytic


def all_analytics() -> dict[str, Analytic]:
    return dict(_REGISTRY)


def get_analytic(key: str) -> Analytic:
    return _REGISTRY[key]
