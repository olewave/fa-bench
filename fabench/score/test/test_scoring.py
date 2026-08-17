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

"""Boundary / word / recall / calibration metrics (Plan 5.2-5.7).

Every expected value below is computed by hand in the comments so the test is a
specification, not just a regression lock (Plan S5 acceptance / gate #4).
"""

import math

import pytest

from fabench.schema import Interval, Utterance
from fabench.score import boundary as B
from fabench.score import calibration, recall, word
from fabench.score.core import score_pair

TOL = 1e-9

# Manner map for the toy inventory.
_MANNER = {"sil": "silence", "s": "fricative", "iy": "vowel"}


def manner_of(canon: str) -> str:
    return _MANNER.get(canon, "vowel")


def _phones(seq):
    return [Interval(lab, s, e) for lab, s, e in seq]


# Gold: 4 tiled phones over [0, 0.5]s.
GOLD = _phones(
    [("sil", 0.00, 0.10), ("s", 0.10, 0.20), ("iy", 0.20, 0.40), ("sil", 0.40, 0.50)]
)
# Hyp (Mode B, 1:1) with deliberate offsets.
HYP = _phones(
    [("sil", 0.00, 0.12), ("s", 0.12, 0.19), ("iy", 0.19, 0.41), ("sil", 0.41, 0.50)]
)


def _matched_11(n):
    return [(i, i) for i in range(n)]


def _errs():
    return B.build_boundary_errors(_matched_11(4), GOLD, HYP, manner_of)


# --------------------------------------------------------------------------
# 5.2 MAE / median / signed
# --------------------------------------------------------------------------
def test_boundary_mae_median_signed():
    errs = _errs()
    # 8 dual-edge abs errors (s): [0, .02, .02, .01, .01, .01, .01, 0] -> sum .08
    assert len(errs) == 8
    assert B.mae(errs) == pytest.approx(0.08 / 8)          # 0.010 s = 10 ms
    assert B.median_abs(errs) == pytest.approx(0.010)       # median of the 8
    # signed (hyp-gold) sum = +.04 -> mean +.005 s = +5 ms (aligner lags)
    assert B.signed_mean(errs) == pytest.approx(0.04 / 8)


def test_threshold_accuracy():
    errs = _errs()
    # <=10ms: two 0.0 + four 0.01 = 6/8 ; the two 0.02 excluded
    assert B.threshold_accuracy(errs, 0.010) == pytest.approx(6 / 8)
    # <=20ms: all 8
    assert B.threshold_accuracy(errs, 0.020) == pytest.approx(1.0)


def test_onset_offset_components():
    errs = _errs()
    on = B.onset_only(errs)
    off = B.offset_only(errs)
    assert len(on) == 4 and len(off) == 4
    # onsets abs: [0, .02, .01, .01] -> mean .01 ; offsets: [.02, .01, .01, 0] -> mean .01
    assert B.mae(on) == pytest.approx(0.04 / 4)
    assert B.mae(off) == pytest.approx(0.04 / 4)


# --------------------------------------------------------------------------
# 5.4 per-boundary-type
# --------------------------------------------------------------------------
def test_per_type_buckets():
    errs = _errs()
    pt = B.per_type(errs, ta20_s=0.020, min_n=1)
    # (silence,silence): phone0 onset(0.0) + phone3 offset(0.0) -> n=2, mae=0
    assert pt[("silence", "silence")]["n"] == 2
    assert pt[("silence", "silence")]["mae_s"] == pytest.approx(0.0)
    # (silence,fricative): phone0 offset(.02)+phone1 onset(.02) -> mae .02
    assert pt[("silence", "fricative")]["mae_s"] == pytest.approx(0.020)
    # (fricative,vowel): phone1 offset(.01)+phone2 onset(.01) -> mae .01
    assert pt[("fricative", "vowel")]["mae_s"] == pytest.approx(0.010)


# --------------------------------------------------------------------------
# 5.6 recall / insertion
# --------------------------------------------------------------------------
def test_recall_insertion():
    assert recall.arr(2, 3) == pytest.approx(2 / 3)
    assert recall.insertion_rate(2, 3) == pytest.approx(1 / 3)
    # Mode B 1:1 => ARR == 1.0
    assert recall.arr(4, 4) == 1.0
    assert recall.insertion_rate(4, 4) == 0.0


# --------------------------------------------------------------------------
# 5.5 WBE
# --------------------------------------------------------------------------
def test_wbe_pools_over_all_boundaries():
    gold1 = _phones([("she", 0.0, 0.3), ("sells", 0.3, 0.7)])
    hyp1 = _phones([("she", 0.0, 0.32), ("sells", 0.32, 0.69)])
    gold2 = _phones([("hi", 0.0, 0.2)])
    hyp2 = _phones([("hi", 0.0, 0.25)])
    e1 = word.word_abs_errors(gold1, hyp1)  # [0, .02, .02, .01]
    e2 = word.word_abs_errors(gold2, hyp2)  # [0, .05]
    assert sorted(e1) == pytest.approx([0.0, 0.01, 0.02, 0.02])
    mm = word.word_boundary_error([e1, e2])
    # One number: the mean over ALL 6 boundaries, not the mean of the two
    # per-utterance means. The short utterance therefore carries the weight its
    # 2 boundaries earn, not the half it would get from utterance-averaging --
    # which for this pair is .10/6 = 16.7 ms against (.0125+.025)/2 = 18.8 ms.
    assert mm["wbe_s"] == pytest.approx(0.10 / 6)
    assert mm["n_word_boundaries"] == 6
    assert mm["n_utts_with_words"] == 2
    assert "wbe_macro_s" not in mm


# --------------------------------------------------------------------------
# 5.7 calibration
# --------------------------------------------------------------------------
def test_spearman_perfect_and_auroc():
    # conf increases as error decreases -> Spearman(conf, -abserr) = +1
    conf = [0.9, 0.8, 0.7, 0.6]
    aerr = [0.001, 0.005, 0.02, 0.05]
    cal = calibration.calibration_metrics(conf, aerr, within_tau_s=0.010)
    assert cal["spearman"] == pytest.approx(1.0)
    # within-10ms labels: [T,T,F,F]; conf perfectly separates -> AUROC 1.0
    assert cal["auroc"] == pytest.approx(1.0)


def test_auroc_reversed_is_zero():
    conf = [0.1, 0.2, 0.8, 0.9]
    aerr = [0.001, 0.002, 0.05, 0.06]  # within20: [T,T,F,F], conf anti-correlated
    cal = calibration.calibration_metrics(conf, aerr, within_tau_s=0.020)
    assert cal["auroc"] == pytest.approx(0.0)


def test_ece_probability_and_na():
    # avg_conf .9, empirical acc 0 -> ECE .9
    conf = [0.9, 0.9]
    aerr = [0.5, 0.5]  # both far -> not within 20ms
    cal = calibration.calibration_metrics(conf, aerr, within_tau_s=0.020)
    assert cal["ece"] == pytest.approx(0.9)
    # log-likelihood-style conf outside [0,1] -> ECE N/A (nan)
    cal2 = calibration.calibration_metrics([-3.2, -1.1], [0.5, 0.001])
    assert math.isnan(cal2["ece"])


# --------------------------------------------------------------------------
# score_pair end-to-end (gate #5: Mode B 1:1 => ARR 1.0)
# --------------------------------------------------------------------------
def test_score_pair_mode_b():
    gold = Utterance("u1", "toy", "read", "spk1", "x.wav", 16000, 0.5, words=[], phones=GOLD)
    hyp = Utterance("u1", "toy", "read", "spk1", "x.wav", 16000, 0.5, words=[], phones=HYP)
    us = score_pair(
        gold, hyp, condition="clean", aligner="toy", mode="B",
        manner_of_canonical=manner_of,
    )
    assert (us.n_matched_phone, us.n_gold_phone, us.n_hyp_phone) == (4, 4, 4)
    assert B.mae(us.boundary_errors) == pytest.approx(0.010)
    assert us.matched_gold_phone_idx == [0, 1, 2, 3]


def test_score_pair_manner_match_keeps_consistent_substitutions():
    """Paper protocol (arXiv:2606.18466): boundary error is scored on aligned
    pairs incl. substitutions, dropping only manner-mismatched ones. Here
    s~sh (both sibilant/affricate) is kept, z~d (sibilant vs stop) is dropped,
    iy~iy is an exact match. ARR still counts only the exact-label match."""
    gp = _phones([("s", 0.0, 0.1), ("z", 0.1, 0.2), ("iy", 0.2, 0.4)])
    hp = _phones([("sh", 0.0, 0.11), ("d", 0.1, 0.19), ("iy", 0.19, 0.41)])
    gold = Utterance("u", "toy", "read", "spk", "x.wav", 16000, 0.4, words=[], phones=gp)
    hyp = Utterance("u", "toy", "read", "spk", "x.wav", 16000, 0.4, words=[], phones=hp)

    # exact-label matching (default): only iy matches -> 1 pair -> 2 dual-edge errs
    us_exact = score_pair(gold, hyp, condition="clean", aligner="t", mode="A")
    assert us_exact.n_matched_phone == 1
    assert len(us_exact.boundary_errors) == 2
    assert us_exact.matched_gold_phone_idx == [2]

    # manner-match: s~sh + iy~iy kept (2 pairs -> 4 errs), z~d excluded
    us_mm = score_pair(gold, hyp, condition="clean", aligner="t", mode="A", manner_match=True)
    assert us_mm.n_matched_phone == 1               # ARR unchanged (exact only)
    assert len(us_mm.boundary_errors) == 4
    assert us_mm.matched_gold_phone_idx == [0, 2]   # z (idx 1) dropped by manner


def test_score_pair_exclude_silence_boundaries():
    """Paper scores speech-to-speech boundaries only (no silence manner class);
    silence/edge-adjacent boundaries are dropped when the flag is set."""
    gold = Utterance("u1", "toy", "read", "spk1", "x.wav", 16000, 0.5, words=[], phones=GOLD)
    hyp = Utterance("u1", "toy", "read", "spk1", "x.wav", 16000, 0.5, words=[], phones=HYP)
    kw = {"condition": "clean", "aligner": "toy", "mode": "B", "manner_of_canonical": manner_of}
    us_all = score_pair(gold, hyp, **kw)
    us_sp = score_pair(gold, hyp, exclude_silence_boundaries=True, **kw)
    # GOLD = sil,s,iy,sil -> only the internal s<->iy boundary is speech-to-speech
    # (dual-edge: s.offset + iy.onset); everything else touches silence/edge.
    assert len(us_all.boundary_errors) == 8
    assert len(us_sp.boundary_errors) == 2
    for e in us_sp.boundary_errors:
        assert e.left_manner != "silence" and e.right_manner != "silence"


def test_boundary_unit_word_scores_word_boundaries():
    """boundary_unit='word' scores dual-edge WORD boundaries (with hand-computed
    errors) instead of phones, and reuses the count fields for word ARR."""
    gold = Utterance(
        utt_id="u", source_corpus="timit", register="read", speaker_id="s",
        audio_path="", sample_rate=16000, duration_s=1.0,
        words=[Interval("she", 0.10, 0.30), Interval("had", 0.30, 0.60)],
        phones=[Interval("sh", 0.10, 0.20), Interval("iy", 0.20, 0.30),
                Interval("hh", 0.30, 0.40), Interval("ae", 0.40, 0.50), Interval("d", 0.50, 0.60)],
    )
    hyp = Utterance(
        utt_id="u", source_corpus="hyp", register="", speaker_id="", audio_path="",
        sample_rate=16000, duration_s=1.0,
        words=[Interval("she", 0.12, 0.30), Interval("had", 0.30, 0.57)],
        phones=[Interval("sh", 0.12, 0.22), Interval("iy", 0.22, 0.30),
                Interval("hh", 0.30, 0.42), Interval("ae", 0.42, 0.52), Interval("d", 0.52, 0.57)],
    )
    us_w = score_pair(gold, hyp, condition="c", aligner="a", mode="A", boundary_unit="word")
    # 2 words x 2 edges; errors: she.start .02, she.end 0, had.start 0, had.end .03
    assert len(us_w.boundary_errors) == 4
    assert sorted(round(b.abs, 4) for b in us_w.boundary_errors) == [0.0, 0.0, 0.02, 0.03]
    assert us_w.n_matched_phone == 2 and us_w.n_gold_phone == 2  # word counts -> word ARR
    # phone mode still uses phones (5 phones x 2 edges = 10)
    us_p = score_pair(gold, hyp, condition="c", aligner="a", mode="A", boundary_unit="phone")
    assert len(us_p.boundary_errors) == 10


def test_boundary_unit_word_drops_silence_pseudowords():
    """Silence pseudo-words on the hyp word tier (charsiu '[sil]', maps 'sil')
    are dropped, so they never count as a real word boundary."""
    gold = Utterance("u", "timit", "read", "s", "", 16000, 1.0,
                     words=[Interval("she", 0.1, 0.3)], phones=[Interval("sh", 0.1, 0.3)])
    hyp = Utterance("u", "hyp", "", "", "", 16000, 1.0,
                    words=[Interval("[sil]", 0.0, 0.1), Interval("she", 0.1, 0.3)],
                    phones=[Interval("sh", 0.1, 0.3)])
    us = score_pair(gold, hyp, condition="c", aligner="a", mode="A", boundary_unit="word")
    assert len(us.boundary_errors) == 2  # only "she", both edges ~0 error
    assert us.n_gold_phone == 1 and us.n_hyp_phone == 1  # [sil] not counted
