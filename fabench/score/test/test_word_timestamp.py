# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Word timestamps: each reference word owns a start and an end."""

import pytest

from fabench.schema import Interval, Utterance
from fabench.score.aggregate import aggregate
from fabench.score.core import score_pair


def _w(label, start, end):
    return Interval(label=label, start=start, end=end)


JOINT = [_w("big", 0.0, 0.3), _w("the", 0.3, 0.5), _w("cat", 0.5, 0.9)]
PAUSE = [_w("big", 0.0, 0.3), _w("the", 0.3, 0.5), _w("cat", 0.8, 1.2)]


def _misread(words):
    return [words[0], _w("a", words[1].start, words[1].end), words[2]]


def _row(gold_words, hyp_words):
    def utt(words):
        return Utterance("u", "toy", "read", "spk", "x.wav", 16000, 1.2,
                         words=words, phones=[])
    us = score_pair(utt(gold_words), utt(hyp_words), condition="clean",
                    aligner="toy", mode="A", score_phones=False)
    return aggregate([us])[0]


@pytest.mark.parametrize("gold", [JOINT, PAUSE])
def test_misread_word_costs_only_its_own_timestamps(gold):
    """A pause beside the misread word changes nothing. The boundary metrics
    drop the start of "cat" at a joint and keep it at a pause."""
    assert _row(gold, gold)["wts_f1"] == pytest.approx(1.0)
    r = _row(gold, _misread(gold))
    assert (r["n_wts_gold"], r["n_wts_hyp"], r["n_wts_matched"]) == (6, 6, 4)
    assert r["wts_recall"] == pytest.approx(4 / 6)
    assert r["wts_precision"] == pytest.approx(4 / 6)
    assert r["wts_mae_ms"] == pytest.approx(0.0)


def test_inserted_word_is_two_false_alarms_and_moves_its_neighbours():
    hyp = [_w("big", 0.0, 0.3), _w("the", 0.3, 0.45), _w("uh", 0.45, 0.55),
           _w("cat", 0.55, 0.9)]
    r = _row(JOINT, hyp)
    assert (r["n_wts_gold"], r["n_wts_hyp"]) == (6, 8)
    # the end and the cat start are each 50 ms off, the other four exact
    assert r["wts_start_mae_ms"] == pytest.approx(50 / 3)
    assert r["wts_end_mae_ms"] == pytest.approx(50 / 3)
    assert r["wts_recall"] == pytest.approx(4 / 6)
    assert r["wts_precision"] == pytest.approx(4 / 8)


def test_exactly_the_width_is_a_hit():
    """0.31 - 0.29 is 0.020000000000000018 in floats."""
    gold = [_w("a", 0.29, 0.5)]
    r = _row(gold, [_w("a", 0.31, 0.5)])
    assert r["wts_recall"] == pytest.approx(1.0)


def test_empty_hypothesis_charges_recall():
    r = _row(JOINT, [])
    assert (r["n_wts_gold"], r["n_wts_hyp"], r["n_wts_matched"]) == (6, 0, 0)
    assert r["wts_recall"] == pytest.approx(0.0)
