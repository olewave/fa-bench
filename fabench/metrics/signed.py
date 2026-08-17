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

"""Signed mean boundary error (ms), hyp - gold. A *bias*: positive => the
aligner systematically lags gold, negative => it leads. Ideal is 0, so it has no
'higher is better' direction."""
from __future__ import annotations

from collections.abc import Sequence

from fabench.metrics.base import register
from fabench.score import boundary
from fabench.score.boundary import BoundaryError


class SignedMean:
    key = "signed_ms"
    unit = "ms"
    higher_is_better = None  # bias metric: ideal is 0

    def compute(self, errs: Sequence[BoundaryError]) -> float:
        return boundary.signed_mean(errs) * 1000.0


register(SignedMean())
