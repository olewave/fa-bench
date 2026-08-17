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

"""Silence-edge split: decompose boundary MAE into interior (speech<->speech) vs
silence/edge boundaries. Sharp aligners tend to win the interior but pay at the
soft silence edges — this shows where the error lives. Returns full-precision
values; callers round for presentation."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from fabench.analyze.base import Analytic, register


def _mae(xs) -> float:
    return float(np.mean(xs)) if len(xs) else float("nan")


def silence_edge_split(errs: Sequence[tuple[float, bool]]) -> dict:
    """errs: (abs_error_ms, silence_adjacent) per boundary."""
    interior = [a for a, sil in errs if not sil]
    edge = [a for a, sil in errs if sil]
    allb = [a for a, _ in errs]
    return {
        "n": len(allb), "n_interior": len(interior), "n_edge": len(edge),
        "mae_all": _mae(allb), "mae_interior": _mae(interior), "mae_edge": _mae(edge),
        "pct_edge": (100.0 * len(edge) / len(allb)) if allb else float("nan"),
    }


register(Analytic(
    "silence_edge",
    "Silence-edge MAE split",
    "Boundary MAE split into interior (speech-speech) vs silence/edge boundaries.",
    silence_edge_split,
))
