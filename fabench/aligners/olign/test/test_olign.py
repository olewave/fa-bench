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

"""olign adapter — registry, request building, and JSON->Interval conversion.

Parsing is tested against ``test/fixtures/olign_response.json``, which is a real
(trimmed) response captured from the live v0.9.0 server rather than a
hand-written mock, so the shape cannot drift from reality silently.

A live smoke test hits the deployed server (skipped if unreachable). It asserts
the alignment is well-formed, not that it is good — boundary quality is measured
by the matched-set eval (summary/olign_probe_*) and the standalone acceptance
kit, not by unit tests that depend on a live server. The REST timing defect that
once made olign unscoreable (fixed 30 ms nominal durations) was fixed server-side
2026-07-20; ``test_fixture_has_varied_real_timings`` guards against a regression
to it. See the fabench/aligners/olign/adapter.py docstring and summary/.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
import pytest

from fabench.aligners import get_adapter
from fabench.aligners.base import AlignerError, ModeUnsupported
from fabench.aligners.olign import build_config, build_query, parse_olign_result
from fabench.config import AlignerSpec

FIXTURE = Path(__file__).parent / "fixtures" / "olign_response.json"
REAL_RESPONSE = json.loads(FIXTURE.read_text())

# olign's known-good fixture clip; the live smoke test self-skips without it.
SHORT1_WAV = Path(os.environ.get("OLIGN_TEST_WAV", "data/olign/short1.wav"))
SHORT1_TEXT = "what is better a fruit or hamburger"
# A live-server test needs a live server, and its address belongs to whoever
# runs the suite, not to the repo. Set OLIGN_TEST_HOST / OLIGN_TEST_PORT to
# point at one; without them these tests skip -- which is what they already
# did on every machine but the author's.
HOST = os.environ.get("OLIGN_TEST_HOST", "127.0.0.1")
PORT = int(os.environ.get("OLIGN_TEST_PORT", "8848"))


def _spec(**params):
    return AlignerSpec(
        name="olign", adapter="olign", enabled=True, modes=["A"],
        granularity=["word", "phone"], emits_confidence=True,
        params=params,
    )


def test_olign_registered():
    a = get_adapter(_spec())
    assert a.name == "olign"
    assert a.source == "arpabet"
    assert a.batch is True  # network aligner -> concurrent align_corpus path
    assert a.supports("A", "phone")


def test_build_query_is_urlencoded_with_required_params():
    q = parse_qs(build_query("what is", core_type="en.phone.align"))
    assert q["ref_text"] == ["what is"]
    assert q["core_type"] == ["en.phone.align"]
    assert q["show_phone_details"] == ["1"]
    assert q["rank"] == ["100"]


def test_build_config_uses_snake_case_proto_field_names():
    # services.proto's RequestDetails declares core_type/ref_text; camelCase
    # silently degrades to server-side defaults, so this is load-bearing.
    cfg = build_config("what is", core_type="en.other.core", vad_enable=1)
    assert cfg["request"]["core_type"] == "en.other.core"
    assert cfg["request"]["ref_text"] == "what is"
    assert cfg["vad"]["vad_enable"] == 1
    assert cfg["audio"]["sample_rate"] == 16000


def test_parse_real_response_word_and_phone_shape():
    words, phones = parse_olign_result(REAL_RESPONSE)
    assert [w.label for w in words] == ["what", "is", "better"]
    # times are milliseconds, NOT the "10ms units" the doc claims (see adapter
    # docstring: settled against TIMIT gold onsets).
    assert words[0].start == pytest.approx(0.640)
    assert words[0].end == pytest.approx(0.900)
    assert words[2].start == pytest.approx(1.080)
    assert [p.label for p in phones] == ["w", "ah", "t", "ih", "z", "b", "eh", "t", "er"]
    assert phones[0].end == pytest.approx(0.670)
    assert all(p.conf is not None for p in phones)


def test_parse_result_is_monotonic_and_positive_length():
    _, phones = parse_olign_result(REAL_RESPONSE)
    for p in phones:
        assert p.end > p.start
    assert phones == sorted(phones, key=lambda iv: (iv.start, iv.end))


def test_parse_drops_zero_length_and_resetting_phones():
    """The live server emits both (2.4% of a TIMIT sample). They must not reach
    the scorer as degenerate intervals."""
    payload = {
        "result": {
            "details": [
                {
                    "char": "or", "begin": 480, "end": 510, "score": 0,
                    "phone": [
                        {"char": "ao", "begin": 480, "end": 510, "score": 0},
                        {"char": "r", "begin": 0, "end": 0, "score": 0},  # zero-length
                    ],
                }
            ]
        }
    }
    words, phones = parse_olign_result(payload)
    assert [w.label for w in words] == ["or"]
    assert [p.label for p in phones] == ["ao"]


def test_parse_olign_result_empty_details():
    words, phones = parse_olign_result({"result": {"details": []}})
    assert words == [] and phones == []


def test_fixture_has_varied_real_timings():
    """The fixture is a real capture from the fixed server. Guards against a
    regression to the old fixed-30ms REST defect (see summary/ olign
    section): real alignments have varied phone durations."""
    _, phones = parse_olign_result(REAL_RESPONSE)
    durs = [round((p.end - p.start) * 1000) for p in phones]
    flat = sum(1 for d in durs if d == 30) / len(durs)
    assert flat < 0.5, f"fixture looks like the old flat-30ms defect ({flat:.0%} flat)"


def _silent_wav(tmp_path) -> str:
    from fabench.audio import write_audio

    path = tmp_path / "x.wav"
    write_audio(str(path), np.zeros(8000, dtype=np.float64), 16000)
    return str(path)


def test_olign_errid_raises_alignererror(tmp_path, monkeypatch):
    a = get_adapter(_spec())
    monkeypatch.setattr(
        a, "_align_rest",
        lambda *_: {"errId": 41009, "error": "The sampling rate must be 16000 Hz!"},
    )
    with pytest.raises(AlignerError, match="41009"):
        a.align(_silent_wav(tmp_path), "hello", mode="A")


def test_olign_success_via_stubbed_transport(tmp_path, monkeypatch):
    a = get_adapter(_spec())
    monkeypatch.setattr(a, "_align_rest", lambda *_: REAL_RESPONSE)
    out = a.align(_silent_wav(tmp_path), "what is better", mode="A")
    assert [w.label for w in out.words] == ["what", "is", "better"]
    assert len(out.phones) == 9


def test_olign_align_corpus_concurrent(tmp_path, monkeypatch):
    """The batch path fans align() across a thread pool and returns every item
    keyed by item_id."""
    from fabench.aligners.base import BatchItem

    a = get_adapter(_spec(concurrency=4))
    monkeypatch.setattr(a, "_align_rest", lambda audio, transcript: REAL_RESPONSE)
    wav = _silent_wav(tmp_path)
    items = [
        BatchItem(item_id=f"i{i}", audio_path=wav, transcript="what is better", mode="A")
        for i in range(6)
    ]
    out = a.align_corpus(items)
    assert set(out) == {f"i{i}" for i in range(6)}
    assert all(len(o.phones) == 9 for o in out.values())


def test_olign_align_corpus_omits_failures(tmp_path, monkeypatch):
    """A per-item failure is dropped from the dict, not raised — one bad item
    must never abort a 20k-utterance batch."""
    from fabench.aligners.base import AlignerError, BatchItem

    a = get_adapter(_spec(concurrency=2))
    wav = _silent_wav(tmp_path)

    def fake(audio, transcript):
        if transcript == "boom":
            raise AlignerError("boom")
        return REAL_RESPONSE

    monkeypatch.setattr(a, "_align_rest", fake)
    items = [
        BatchItem(item_id="ok", audio_path=wav, transcript="what is better", mode="A"),
        BatchItem(item_id="bad", audio_path=wav, transcript="boom", mode="A"),
    ]
    out = a.align_corpus(items)
    assert set(out) == {"ok"}


def test_olign_unknown_transport_raises(tmp_path):
    a = get_adapter(_spec(transport="carrier-pigeon"))
    with pytest.raises(AlignerError, match="transport"):
        a.align(_silent_wav(tmp_path), "hello", mode="A")


def test_olign_mode_b_unsupported(tmp_path):
    a = get_adapter(_spec())
    with pytest.raises(ModeUnsupported):
        a.align(_silent_wav(tmp_path), "what is", mode="B")


@pytest.mark.skipif(not SHORT1_WAV.exists(), reason="olign test fixture not staged")
def test_olign_real_server_smoke():
    """Live smoke test against the deployed v0.9.0 REST door (skipped if
    unreachable). Asserts a well-formed alignment, not a good one."""
    try:
        with socket.create_connection((HOST, PORT), timeout=2):
            pass
    except OSError:
        pytest.skip(f"{HOST}:{PORT} unreachable")

    # Point the adapter at the SAME server the guard just probed. Without this
    # the guard checks HOST:PORT while the adapter falls back to its public
    # default, so the test reaches a different machine than the one it verified
    # was up -- and fails instead of skipping.
    a = get_adapter(_spec(base_url=f"http://{HOST}:{PORT}/v1/assess"))
    out = a.align(str(SHORT1_WAV), SHORT1_TEXT, mode="A")
    assert len(out.words) >= 1
    assert len(out.phones) >= 1
    for iv in out.words + out.phones:
        assert 0.0 <= iv.start <= iv.end
