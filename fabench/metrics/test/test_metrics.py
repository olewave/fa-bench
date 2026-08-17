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

"""Metric registry: population, known-answer values, and equivalence with the
existing boundary.summarize() engine (the registry is a faithful façade)."""
import math

from fabench import metrics
from fabench.score import boundary
from fabench.score.boundary import BoundaryError


def _toy_pool():
    # onset off by +10 ms, offset off by -20 ms.
    return [
        BoundaryError("onset", 1.0, 1.010, "vowel", "stop"),
        BoundaryError("offset", 2.0, 1.980, "stop", "vowel"),
    ]


def test_registry_is_populated():
    assert set(metrics.all_metrics()) == {"mae_ms", "median_ms", "signed_ms", "ta10", "ta25", "ta50"}


def test_metric_traits():
    m = metrics.all_metrics()
    assert m["mae_ms"].unit == "ms" and m["mae_ms"].higher_is_better is False
    assert m["ta10"].unit == "%" and m["ta10"].higher_is_better is True
    assert m["signed_ms"].higher_is_better is None  # bias, ideal 0


def test_known_answers():
    v = metrics.compute_all(_toy_pool())
    assert math.isclose(v["mae_ms"], 15.0)       # (10 + 20) / 2
    assert math.isclose(v["median_ms"], 15.0)
    assert math.isclose(v["signed_ms"], -5.0)    # (+10 - 20) / 2
    assert math.isclose(v["ta10"], 50.0)         # only the +10 ms boundary is <=10
    assert math.isclose(v["ta25"], 100.0)
    assert math.isclose(v["ta50"], 100.0)


def test_equivalent_to_summarize_engine():
    errs = _toy_pool()
    v = metrics.compute_all(errs)
    s = boundary.summarize(errs, [0.010, 0.025, 0.050])
    assert math.isclose(v["mae_ms"], s["mae_s"] * 1000)
    assert math.isclose(v["median_ms"], s["median_s"] * 1000)
    assert math.isclose(v["signed_ms"], s["signed_mean_s"] * 1000)
    assert math.isclose(v["ta10"], s["ta_10ms"] * 100)
    assert math.isclose(v["ta50"], s["ta_50ms"] * 100)


def test_empty_pool_is_nan_not_crash():
    v = metrics.compute_all([])
    assert math.isnan(v["mae_ms"]) and math.isnan(v["ta10"])
