# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""fabench.score.latency -- percentiles and the fixed/marginal split."""
from __future__ import annotations

import math

import numpy as np
import pytest

from fabench.score.latency import latency_metrics


def test_recovers_a_planted_fixed_cost_and_rate():
    """The point of the fit: separate per-request cost from per-second cost."""
    rng = np.random.default_rng(0)
    dur = rng.uniform(0.5, 20.0, 500)
    lat = 0.80 + 0.15 * dur + rng.normal(0, 0.02, 500)
    m = latency_metrics(list(lat), list(dur))
    assert m["lat_fixed_s"] == pytest.approx(0.80, abs=0.02)
    assert m["lat_per_audio_s"] == pytest.approx(0.15, abs=0.01)
    assert m["lat_r2"] > 0.99
    assert m["n_lat"] == 500


def test_rtf_would_hide_what_the_fit_shows():
    """Same API, two utterance lengths: RTF differs 10x, the fit does not.

    This is why the module exists rather than reusing rtf_mean.
    """
    short = [0.8 + 0.15 * 2.5] * 50
    long_ = [0.8 + 0.15 * 60.0] * 50
    rtf_short = np.mean([t / 2.5 for t in short])
    rtf_long = np.mean([t / 60.0 for t in long_])
    # RTF reads nearly 3x worse on the short utterances. Same API, same
    # overhead, same rate -- only the denominator changed.
    assert rtf_short / rtf_long > 2.5

    m = latency_metrics(short + long_, [2.5] * 50 + [60.0] * 50)
    assert m["lat_fixed_s"] == pytest.approx(0.80, abs=1e-6)
    assert m["lat_per_audio_s"] == pytest.approx(0.15, abs=1e-6)


def test_percentiles_follow_the_tail_not_the_mean():
    lat = [1.0] * 99 + [100.0]
    m = latency_metrics(lat)
    assert m["lat_p50_s"] == pytest.approx(1.0)
    assert m["lat_max_s"] == pytest.approx(100.0)
    assert m["lat_p99_s"] > 1.0


def test_absent_measurements_are_nan_not_zero():
    """Every local tool reports no latency. It must not read as instant."""
    m = latency_metrics([None, None, None])
    assert m["n_lat"] == 0
    assert math.isnan(m["lat_p50_s"])
    assert math.isnan(m["lat_fixed_s"])


def test_none_entries_drop_in_step_with_their_durations():
    m = latency_metrics([None, 1.0, None, 2.0, 3.0],
                        [99.0, 1.0, 99.0, 2.0, 3.0])
    assert m["n_lat"] == 3
    # Misaligned dropping would pair 1.0 s with a 99 s duration and flatten the
    # slope towards zero. In step, the planted rate is exactly 1.
    assert m["lat_per_audio_s"] == pytest.approx(1.0, abs=1e-6)
    assert m["lat_fixed_s"] == pytest.approx(0.0, abs=1e-6)


def test_no_fit_without_spread_in_duration():
    """A constant duration cannot identify a slope; nan beats an arbitrary split."""
    m = latency_metrics([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
    assert math.isnan(m["lat_per_audio_s"])
    assert not math.isnan(m["lat_p50_s"])       # percentiles still fine


def test_negative_and_infinite_are_discarded():
    m = latency_metrics([1.0, -1.0, float("inf"), float("nan"), 3.0])
    assert m["n_lat"] == 2


def test_the_network_floor_is_reported_and_subtracted():
    """lat_fixed_s mixes round trip with vendor overhead; only the net is portable."""
    rng = np.random.default_rng(1)
    dur = rng.uniform(0.5, 20.0, 300)
    lat = 0.90 + 0.10 * dur + rng.normal(0, 0.01, 300)   # 0.90 = 0.15 net + 0.75? no:
    m = latency_metrics(list(lat), list(dur), [0.15] * 300)
    assert m["lat_setup_s"] == pytest.approx(0.15)
    assert m["lat_fixed_s"] == pytest.approx(0.90, abs=0.01)
    # 0.75 s of the fixed cost is the service; 0.15 s is this machine's network.
    assert m["lat_fixed_net_s"] == pytest.approx(0.75, abs=0.01)


def test_no_setup_probe_leaves_the_net_figure_absent():
    """Without a probe there is no honest way to net out the network."""
    m = latency_metrics([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert math.isnan(m["lat_setup_s"])
    assert math.isnan(m["lat_fixed_net_s"])
    assert not math.isnan(m["lat_fixed_s"])


def test_a_fit_that_explains_nothing_is_not_reported():
    """Measured, duration explains ~0% of a cloud endpoint's latency.

    Splitting a mean into a fixed and a marginal part then invents precision
    the data does not have, and the real endpoints produced exactly that --
    r2 of 0.00 for Deepgram over 40,924 calls, and a NEGATIVE fixed cost for
    ElevenLabs, which is not a quantity that exists.
    """
    rng = np.random.default_rng(3)
    dur = rng.uniform(0.5, 20.0, 400)
    lat = rng.uniform(0.1, 1.0, 400)          # independent of duration
    m = latency_metrics(list(lat), list(dur))
    assert math.isnan(m["lat_fixed_s"])
    assert math.isnan(m["lat_per_audio_s"])
    assert m["lat_r2"] < 0.1                  # reported, so the absence is explained
    assert not math.isnan(m["lat_p50_s"])     # percentiles still stand


def test_a_negative_fixed_cost_is_never_reported():
    dur = [1.0, 2.0, 3.0, 4.0, 5.0]
    lat = [0.1, 0.9, 1.7, 2.5, 3.3]           # intercept -0.7
    m = latency_metrics(lat, dur)
    assert math.isnan(m["lat_fixed_s"]), "a request cannot cost negative time"


# --------------------------------------------------------------- coverage
def test_coverage_marks_a_truncated_cell():
    """A cell cut off mid-run scores as a clean row unless coverage says so."""
    from fabench.schema import Interval, Utterance
    from fabench.score.aggregate import aggregate
    from fabench.score.core import score_pair

    def utt(uid):
        return Utterance(utt_id=uid, speaker_id="s", source_corpus="timit",
                         register="read", audio_path="x.wav", sample_rate=16000,
                         duration_s=2.0,
                         words=[Interval("a", 0.0, 1.0), Interval("b", 1.0, 2.0)],
                         phones=[])
    rows = [score_pair(utt(f"u{i}"), utt(f"u{i}"), condition="origin",
                       aligner="t", mode="A", n_gold_utts=100)
            for i in range(19)]
    r = aggregate(rows, bootstrap_iters=0)[0][0]
    assert r["n_utts"] == 19 and r["n_gold_utts"] == 100
    assert r["coverage"] == pytest.approx(0.19)
    assert r["incomplete"] is True

    rows = [score_pair(utt(f"u{i}"), utt(f"u{i}"), condition="origin",
                       aligner="t", mode="A", n_gold_utts=100)
            for i in range(97)]
    r = aggregate(rows, bootstrap_iters=0)[0][0]
    assert r["coverage"] == pytest.approx(0.97)
    assert r["incomplete"] is False, "a legitimate few-percent drop is not damage"
