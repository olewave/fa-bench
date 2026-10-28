# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Corpus aggregation (Plan 5.9) — hand-checked rollups."""

import pytest

from fabench.schema import Interval, Utterance
from fabench.score.aggregate import aggregate
from fabench.score.core import score_pair

_MANNER = {"sil": "silence", "s": "fricative", "iy": "vowel"}


def manner_of(c):
    return _MANNER.get(c, "vowel")


def _utt(uid, spk, phones):
    return Utterance(uid, "toy", "read", spk, "x.wav", 16000, 0.5, phones=phones)


def _p(seq):
    return [Interval(l, s, e) for l, s, e in seq]


GOLD = _p([("sil", 0.0, 0.1), ("s", 0.1, 0.2), ("iy", 0.2, 0.4), ("sil", 0.4, 0.5)])


def test_aggregate_rollup_values():
    # Two utts, identical hyp offsets. 4 contiguous phones give 5 boundaries
    # per utterance, so MAE is 8 ms.
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
    lb = aggregate(scores)
    assert len(lb) == 1
    row = lb[0]
    assert (row["n_utts"], row["n_absent"], row["n_empty"]) == (2, 0, 0)
    assert row["n_boundaries"] == 10
    assert row["mae_ms"] == pytest.approx(8.0)
    assert row["per"] == pytest.approx(0.0)          # Mode B
    # no word tier: every word column reads NaN, and so does the phone F1,
    # which classes phone boundaries by the words around them
    assert row["n_word_boundaries"] == 0
    for c in ("wbe_ms", "wbnd_f1_all_20ms", "wts_f1", "wer", "bnd_f1_all_20ms"):
        assert row[c] != row[c], c


def test_extras_see_every_row_and_its_group():
    """The extension point: a callable gets each finished row with the scores
    it came from, and what it writes stays in the row."""
    s = score_pair(_utt("u1", "spkA", GOLD), _utt("u1", "spkA", GOLD),
                   condition="clean", aligner="toy", mode="B",
                   extras=[lambda us, ctx: us.extra.update(n=len(ctx.phone.matched))])
    assert s.extra == {"n": 4}

    def add(row, group):
        row["n_seen"] = sum(g.extra["n"] for g in group)

    (row,) = aggregate([s], extras=[add])
    assert row["n_seen"] == 4 and row["mae_ms"] == 0.0
