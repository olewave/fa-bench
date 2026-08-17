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

"""Corpus aggregation + bootstrap (Plan 5.9) — hand-checked rollups."""

import numpy as np
import pytest

from fabench.schema import Interval, Utterance
from fabench.score.aggregate import aggregate, bootstrap_mean_ci
from fabench.score.core import score_pair

_MANNER = {"sil": "silence", "s": "fricative", "iy": "vowel"}


def manner_of(c):
    return _MANNER.get(c, "vowel")


def _utt(uid, spk, phones):
    return Utterance(uid, "toy", "read", spk, "x.wav", 16000, 0.5, phones=phones)


def _p(seq):
    return [Interval(l, s, e) for l, s, e in seq]


GOLD = _p([("sil", 0.0, 0.1), ("s", 0.1, 0.2), ("iy", 0.2, 0.4), ("sil", 0.4, 0.5)])


def test_bootstrap_brackets_point_estimate_and_deterministic():
    # three utterances, per-utt (sum, count) of abs errors
    sums = np.array([0.08, 0.04, 0.12])
    cnts = np.array([8.0, 8.0, 8.0])
    point = sums.sum() / cnts.sum()
    lo, hi = bootstrap_mean_ci(sums, cnts, n_iters=500, ci=0.95, seed=1)
    assert lo <= point <= hi
    # determinism: same seed -> identical CI (gate #6)
    lo2, hi2 = bootstrap_mean_ci(sums, cnts, n_iters=500, ci=0.95, seed=1)
    assert (lo, hi) == (lo2, hi2)


def test_aggregate_rollup_values():
    # Two utts, identical hyp offsets => known MAE 10 ms.
    hyp_phones = _p(
        [("sil", 0.0, 0.12), ("s", 0.12, 0.19), ("iy", 0.19, 0.41), ("sil", 0.41, 0.5)]
    )
    scores = []
    for uid, spk in [("u1", "spkA"), ("u2", "spkB")]:
        g = _utt(uid, spk, GOLD)
        h = _utt(uid, spk, hyp_phones)
        scores.append(
            score_pair(g, h, condition="clean", aligner="toy", mode="B",
                       manner_of_canonical=manner_of)
        )
    lb, pt = aggregate(scores, bootstrap_iters=200, min_matched_per_cell=100)
    assert len(lb) == 1
    row = lb[0]
    assert row["n_utts"] == 2
    assert row["n_speakers"] == 2
    assert row["mae_ms"] == pytest.approx(10.0)
    assert row["arr"] == pytest.approx(1.0)          # Mode B
    assert row["insert_rate"] == pytest.approx(0.0)
    assert row["ta_20ms"] == pytest.approx(1.0)
    assert row["ta_10ms"] == pytest.approx(0.75)
    # underpowered: 8 matched-phones (n_matched=8) < 100
    assert row["underpowered"] is True
    # CI brackets the point estimate
    assert row["mae_ci_lo_ms"] <= row["mae_ms"] <= row["mae_ci_hi_ms"]
    # per-type long table present
    assert any(r["left_manner"] == "silence" for r in pt)


def test_common_matched_survivor_bias():
    # Aligner "good" matches all 4 gold phones; "lazy" drops the hard iy (idx 2).
    good_hyp = _p(
        [("sil", 0.0, 0.11), ("s", 0.11, 0.21), ("iy", 0.19, 0.39), ("sil", 0.39, 0.5)]
    )
    # lazy omits iy entirely (deletion) but nails the easy ones exactly.
    lazy_hyp = _p([("sil", 0.0, 0.1), ("s", 0.1, 0.2), ("sil", 0.4, 0.5)])
    _utt("u1", "spkA", GOLD)
    s_good = score_pair(_utt("u1", "spkA", GOLD), _utt("u1", "spkA", good_hyp),
                        condition="clean", aligner="good", mode="A",
                        manner_of_canonical=manner_of)
    s_lazy = score_pair(_utt("u1", "spkA", GOLD), _utt("u1", "spkA", lazy_hyp),
                        condition="clean", aligner="lazy", mode="A",
                        manner_of_canonical=manner_of)
    # lazy has higher ARR-cost: dropped a phone
    assert s_lazy.n_matched_phone == 3
    assert s_good.n_matched_phone == 4
    lb, _ = aggregate([s_good, s_lazy], bootstrap_iters=50)
    by = {r["aligner"]: r for r in lb}
    # common-matched set = phones matched by BOTH = {0,1,3} (iy excluded)
    # lazy nails those exactly -> common MAE 0; per-system MAE also 0 for lazy.
    assert by["lazy"]["mae_common_ms"] == pytest.approx(0.0)
    # good's common MAE only over {0,1,3}; excludes the fuzzy iy it placed.
    assert by["good"]["arr"] == pytest.approx(1.0)
    assert by["lazy"]["arr"] == pytest.approx(0.75)
