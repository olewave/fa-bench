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

"""Analytics registry + pure-compute known answers, and the boundary-error
extractors on a toy utterance."""
import math

from fabench import analyze as analytics
from fabench.analyze.errors import word_boundary_errors
from fabench.analyze.silence_edge import silence_edge_split
from fabench.analyze.tail_stats import BUCKETS, mae_decomposition, tail_percentiles
from fabench.schema import Interval, Utterance


def test_registry_populated():
    assert set(analytics.all_analytics()) == {"silence_edge", "tail_percentiles", "mae_decomposition"}


def test_silence_edge_split():
    r = silence_edge_split([(10.0, False), (20.0, False), (40.0, True)])
    assert (r["n"], r["n_interior"], r["n_edge"]) == (3, 2, 1)
    assert math.isclose(r["mae_interior"], 15.0)
    assert math.isclose(r["mae_edge"], 40.0)
    assert math.isclose(r["mae_all"], (10 + 20 + 40) / 3)
    assert math.isclose(r["pct_edge"], 100 / 3)


def test_tail_percentiles():
    r = tail_percentiles([10.0, 20.0, 30.0, 200.0])
    assert r["n"] == 4
    assert math.isclose(r["mae"], 65.0)
    assert math.isclose(r["median"], 25.0)
    assert math.isclose(r["max"], 200.0)
    assert math.isclose(r["ta25"], 50.0)        # 10, 20 within 25 ms -> 2/4
    assert math.isclose(r["pct_gt100"], 25.0)   # only 200


def test_mae_decomposition_contribs_sum_to_mae():
    a = [5.0, 15.0, 40.0, 300.0]  # one per bucket except 50_100
    dec = mae_decomposition(a)
    total = sum(dec[f"contrib_{name}"] for name, _, _ in BUCKETS)
    assert math.isclose(total, sum(a) / len(a))          # exact, full precision
    assert math.isclose(dec["pct_le10"], 25.0)
    assert math.isclose(dec["contrib_gt100"], 300.0 / 4)


def test_word_boundary_errors_toy():
    gold = Utterance("u", "timit", "read", "s", "a.wav", 16000, 1.2,
                     words=[Interval("cat", 0.0, 0.5), Interval("dog", 0.7, 1.2)])
    hyp = Utterance("u", "hyp", "", "", "", 16000, 0.0,
                    words=[Interval("cat", 0.02, 0.52), Interval("dog", 0.68, 1.18)])
    errs = word_boundary_errors(gold, hyp)
    assert len(errs) == 4  # 2 words x (onset + offset)
    assert all(math.isclose(a, 20.0) for a, _sil in errs)  # every edge off by 20 ms
    assert all(sil for _a, sil in errs)  # 0.2 s gap + utterance edges -> all silence-adjacent
