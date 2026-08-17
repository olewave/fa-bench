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

"""score_cell() wiring tests (mfa_paper protocol) — an injected fake bridge_fn so
these run with no micromamba/kalpy present."""

from pathlib import Path

from fabench.config import Config
from fabench.schema import Interval, Utterance
from fabench.score.aggregate import aggregate
from fabench.score.core import score_pair
from fabench.score.mfa_paper.cell import make_onset_only, score_cell

_FAKE_BOUNDARY_ERRORS = [
    {
        "following_reference_phone": "ah", "following_test_phone": "AH0",
        "previous_reference_phone": "dh", "previous_test_phone": "DH",
        "boundary_error": -0.02, "reference_boundary": 0.28, "test_boundary": 0.3,
    },
    {
        "following_reference_phone": "sil", "following_test_phone": "sil",
        "previous_reference_phone": "ah", "previous_test_phone": "AH0",
        "boundary_error": -0.02, "reference_boundary": 0.35, "test_boundary": 0.37,
    },
]


def _fake_bridge_fn(utterances, *, silence_phones, custom_mapping):
    return {utt_id: {"boundary_errors": _FAKE_BOUNDARY_ERRORS} for utt_id, _, _ in utterances}


def _cfg(aligner_key=None) -> Config:
    return Config(
        raw={
            "scoring": {
                "protocol": "mfa_paper",
                "mfa_paper": {
                    "aligner_key": aligner_key if aligner_key is not None else {"mfa": "arpa"},
                    "silence_phones": ["sil"],
                    "apply_manner_filter": True,
                },
            }
        },
        path=Path("dummy.yaml"),
    )


def _gold_utterance() -> Utterance:
    return Utterance(
        utt_id="u1", source_corpus="timit", register="read", speaker_id="spk1",
        audio_path="x.wav", sample_rate=16000, duration_s=0.60,
        phones=[
            Interval("sil", 0.00, 0.20), Interval("dh", 0.20, 0.28),
            Interval("ah", 0.28, 0.35), Interval("sil", 0.35, 0.60),
        ],
    )


def _hyp_rec() -> dict:
    return {
        "utt_id": "u1", "condition": "clean", "aligner": "mfa", "mode": "A",
        "source": "mfa", "rtf": None,
        "phones": [
            {"label": "sil", "start": 0.00, "end": 0.16, "conf": None},
            {"label": "SP", "start": 0.16, "end": 0.24, "conf": None},
            {"label": "DH", "start": 0.24, "end": 0.30, "conf": None},
            {"label": "AH0", "start": 0.30, "end": 0.37, "conf": None},
            {"label": "sil", "start": 0.37, "end": 0.60, "conf": None},
        ],
    }


def test_score_cell_returns_none_when_aligner_has_no_mapping_family():
    cfg = _cfg(aligner_key={})  # "mfa" not configured with a family at all
    out = score_cell(cfg, "timit", "mfa", {"u1": _gold_utterance()}, [_hyp_rec()],
                      bridge_fn=_fake_bridge_fn)
    assert out is None


def test_score_cell_returns_none_when_mapping_file_missing():
    cfg = _cfg(aligner_key={"mfa": "arpa"})
    # no such corpus in the vendored mapping set -> file doesn't exist
    out = score_cell(cfg, "seoul_corpus", "mfa", {"u1": _gold_utterance()}, [_hyp_rec()],
                      bridge_fn=_fake_bridge_fn)
    assert out is None


def test_score_cell_wiring_with_fake_bridge():
    cfg = _cfg()
    out = score_cell(cfg, "timit", "mfa", {"u1": _gold_utterance()}, [_hyp_rec()],
                      bridge_fn=_fake_bridge_fn)
    assert out is not None and len(out) == 1
    us = out[0]
    assert us.protocol == "mfa_paper"
    assert us.utt_id == "u1"
    assert us.corpus == "timit"
    assert us.aligner == "mfa"
    assert us.condition == "clean"
    assert len(us.boundary_errors) == 2
    assert all(e.edge == "boundary" for e in us.boundary_errors)
    assert us.matched_gold_phone_idx == []  # v1 scope: opts out of common-matched guard


def test_score_cell_empty_hyp_recs_returns_empty_list_not_none():
    cfg = _cfg()
    out = score_cell(cfg, "timit", "mfa", {"u1": _gold_utterance()}, [],
                      bridge_fn=_fake_bridge_fn)
    assert out == []


def test_aggregate_keeps_fabench_and_mfa_paper_rows_separate():
    """Regression test for the aggregate.py::_group_key change: running both
    protocols over the same (corpus, aligner, mode, condition) must not merge
    two different MAE definitions into one leaderboard row."""
    gold = _gold_utterance()
    hyp = Utterance(
        utt_id="u1", source_corpus="hyp", register="", speaker_id="", audio_path="",
        sample_rate=16000, duration_s=0.0,
        phones=[
            Interval("sil", 0.00, 0.16), Interval("dh", 0.16, 0.24),
            Interval("ah", 0.24, 0.31), Interval("sil", 0.31, 0.60),
        ],
    )
    us_fabench = score_pair(gold, hyp, condition="clean", aligner="mfa", mode="A")
    assert us_fabench.protocol == "fabench"

    cfg = _cfg()
    us_mfa_paper_list = score_cell(
        cfg, "timit", "mfa", {"u1": gold}, [_hyp_rec()], bridge_fn=_fake_bridge_fn
    )
    assert len(us_mfa_paper_list) == 1

    leaderboard, _ = aggregate([us_fabench, *us_mfa_paper_list])
    assert len(leaderboard) == 2
    protocols = {row["scoring_protocol"] for row in leaderboard}
    assert protocols == {"fabench", "mfa_paper"}
    for row in leaderboard:
        assert row["corpus"] == "timit" and row["aligner"] == "mfa"
        assert row["mode"] == "A" and row["condition"] == "clean"


def test_make_onset_only_drops_gap_marker_and_stretches_ends():
    """Paper footnote: BFA's inter-phone gaps are a CTC artifact, not meaningful
    boundaries — use only the onset. Verified on staged data: BFA emits a literal
    "-" placeholder on some gaps, plus plain timing gaps on ~78% of consecutive
    phone pairs even without one."""
    ivs = [
        Interval("sh", 0.195, 0.211),
        Interval("iy", 0.260, 0.293),   # real timing gap before this one (no "-")
        Interval("-", 0.731, 0.748),    # explicit gap-marker placeholder
        Interval("d", 0.764, 0.780),
    ]
    out = make_onset_only(ivs)
    assert [iv.label for iv in out] == ["sh", "iy", "d"]  # "-" removed
    assert out[0].end == out[1].start == 0.260  # sh stretched to iy's onset
    assert out[1].end == out[2].start == 0.764  # iy stretched across the dropped "-"
    assert out[2].end == 0.780  # last interval keeps its own end


def test_score_cell_applies_onset_only_for_bfa_by_default():
    cfg = _cfg(aligner_key={"bfa": "bournemouth"})
    gold = _gold_utterance()
    rec = _hyp_rec()
    rec["aligner"] = "bfa"
    rec["phones"] = [
        {"label": "sil", "start": 0.00, "end": 0.16, "conf": None},
        {"label": "-", "start": 0.16, "end": 0.20, "conf": None},
        {"label": "dh", "start": 0.24, "end": 0.30, "conf": None},
        {"label": "ah", "start": 0.34, "end": 0.37, "conf": None},
        {"label": "sil", "start": 0.40, "end": 0.60, "conf": None},
    ]

    captured = {}

    def _capturing_bridge(utterances, *, silence_phones, custom_mapping):
        captured["hyp_ivs"] = utterances[0][2]
        return {utt_id: {"boundary_errors": []} for utt_id, _, _ in utterances}

    score_cell(cfg, "timit", "bfa", {"u1": gold}, [rec], bridge_fn=_capturing_bridge)
    hyp_ivs = captured["hyp_ivs"]
    assert [iv.label for iv in hyp_ivs] == ["sil", "dh", "ah", "sil"]  # "-" dropped
    assert hyp_ivs[0].end == hyp_ivs[1].start == 0.24  # stretched across the gap
