# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""olign adapter — registry, request building, and JSON->Interval conversion.

Parsing is tested against ``test/fixtures/olign_response.json``, which is a real
(trimmed) response of the hosted 0.9 service rather than a hand-written mock,
so the shape cannot drift from reality silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
import pytest

from fabench.aligners import get_adapter
from fabench.aligners.base import AlignerError, ModeUnsupported
from fabench.aligners.olign import build_query, parse_olign_result
from fabench.config import AlignerSpec

FIXTURE = Path(__file__).parent / "fixtures" / "olign_response.json"
REAL_RESPONSE = json.loads(FIXTURE.read_text())


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


def test_build_query_uses_snake_case_keys():
    # The service reads its parameters by their snake_case names.
    q = parse_qs(build_query("what is", core_type="en.other.core"))
    assert q["core_type"] == ["en.other.core"] and q["ref_text"] == ["what is"]
    assert "coreType" not in q and "refText" not in q


def test_parse_real_response_word_and_phone_shape():
    words, phones = parse_olign_result(REAL_RESPONSE)
    assert [w.label for w in words] == ["what", "is", "better"]
    # times are milliseconds
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
    """Zero-length phones must not reach the scorer as degenerate intervals."""
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
    """The fixture is a real capture, and a real alignment has varied phone
    durations."""
    _, phones = parse_olign_result(REAL_RESPONSE)
    durs = [round((p.end - p.start) * 1000) for p in phones]
    flat = sum(1 for d in durs if d == 30) / len(durs)
    assert flat < 0.5, f"fixture phones look flat, {flat:.0%} at 30 ms"


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


def test_olign_keeps_the_versions_object_as_given(tmp_path, monkeypatch):
    """A body's ``versions`` object reaches hyp.jsonl through meta untouched,
    and a body without one adds nothing."""
    a = get_adapter(_spec())
    wav = _silent_wav(tmp_path)
    versions = {"x": "v0.0.1"}
    monkeypatch.setattr(a, "_align_rest", lambda *_: {**REAL_RESPONSE, "versions": versions})
    assert a.align(wav, "what is better", mode="A").meta == {"versions": versions}
    monkeypatch.setattr(a, "_align_rest", lambda *_: REAL_RESPONSE)
    assert a.align(wav, "what is better", mode="A").meta == {}


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


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self):
        return self._body


def _capture_rest_request(tmp_path, monkeypatch):
    """Run the REST transport against a fake urlopen; return the Request it built."""
    import fabench.aligners.olign.adapter as adapter_mod
    seen = []
    def fake_urlopen(req, timeout=None):
        seen.append(req)
        return _FakeResponse(REAL_RESPONSE)
    monkeypatch.setattr(adapter_mod.urllib.request, "urlopen", fake_urlopen)
    get_adapter(_spec())._align_rest(_silent_wav(tmp_path), "what is better")
    return seen[0]


def test_rest_sends_the_service_token_headers_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CF_ACCESS_CLIENT_ID", "abc.access")
    monkeypatch.setenv("CF_ACCESS_CLIENT_SECRET", "s3cret")
    req = _capture_rest_request(tmp_path, monkeypatch)
    assert req.get_header("Cf-access-client-id") == "abc.access"
    assert req.get_header("Cf-access-client-secret") == "s3cret"


def test_rest_without_a_token_sends_no_auth_but_still_names_itself(tmp_path, monkeypatch):
    monkeypatch.delenv("CF_ACCESS_CLIENT_ID", raising=False)
    monkeypatch.delenv("CF_ACCESS_CLIENT_SECRET", raising=False)
    req = _capture_rest_request(tmp_path, monkeypatch)
    assert req.get_header("Cf-access-client-id") is None
    # The endpoint 403s Python-urllib's default User-Agent.
    assert req.get_header("User-agent", "").startswith("fa-bench-olign/")
