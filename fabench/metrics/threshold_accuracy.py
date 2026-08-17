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

"""Threshold Accuracy TA@tau (%): fraction of matched boundaries within tau ms
of gold. Sharpness of the *typical* boundary at a fixed tolerance. The MFA-2026
paper reports tau in {10, 25, 50} ms (Table 5), registered here as ta10/25/50.

A single parameterized class registered at several tau values — the pattern for
metric families that differ only by a constant."""
from __future__ import annotations

from collections.abc import Sequence

from fabench.metrics.base import register
from fabench.score import boundary
from fabench.score.boundary import BoundaryError

TAU_MS = (10, 25, 50)


class ThresholdAccuracy:
    unit = "%"
    higher_is_better = True

    def __init__(self, tau_ms: int):
        self.tau_ms = tau_ms
        self.key = f"ta{tau_ms}"

    def compute(self, errs: Sequence[BoundaryError]) -> float:
        return boundary.threshold_accuracy(errs, self.tau_ms / 1000.0) * 100.0


for _tau in TAU_MS:
    register(ThresholdAccuracy(_tau))
