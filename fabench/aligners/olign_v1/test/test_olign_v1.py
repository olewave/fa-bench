# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Olign 1.0 on its job API, with the network stubbed."""
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from fabench.aligners.base import AlignerError
from fabench.aligners.olign_v1 import OlignV1
from fabench.timestamp_asrs.cloud import OlignV1ASR
from fabench.timestamp_asrs.cloud import providers as P

DONE = {
    "state": "done", "transcript_source": "client",
    "result": {"words": [
        {"word": "In", "begin": 0.14, "end": 0.31, "score": 98.0,
         "phones": [{"ph": "ih", "begin": 0.14, "end": 0.203, "score": 96},
                    {"ph": "n", "begin": 0.203, "end": 0.31, "score": 100}]},
        {"word": "wage,", "begin": 0.31, "end": 0.75, "score": 90.0,
         "phones": [{"ph": "w", "begin": 0.31, "end": 0.403, "score": 80}]},
    ]},
}


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000)
    return str(path)


@pytest.fixture
def server(monkeypatch):
    """Records every request. The job is done on its first poll."""
    calls: list = []
    state = {"final": DONE}

    def fake(url, **kw):
        calls.append({"url": url, **kw})
        if kw.get("method") == "POST":
            return {"job_id": "j1"}
        return state["final"]
    monkeypatch.setattr(P, "request_json", fake)
    monkeypatch.setattr(P.time, "sleep", lambda s: None)
    return calls, state


def _make(cls, tmp_path, monkeypatch, **params):
    monkeypatch.setenv("OLIGN_API_KEY", "k")
    a = cls(cls.provider, {"cache_dir": str(tmp_path / "cache"), "concurrency": 2, **params})
    a.load()
    return a


def test_track1_sends_the_transcript_and_reads_words_and_phones(audio, tmp_path, monkeypatch, server):
    calls, _ = server
    out = _make(OlignV1, tmp_path, monkeypatch).align(audio, "in wage")
    post, poll = calls[0], calls[1]
    assert post["url"] == "https://api.olewave.com/olign/v1" and post["method"] == "POST"
    assert post["headers"]["X-API-Key"] == "k"
    assert post["headers"]["User-Agent"] == "fa-bench-olign/1"
    assert b'name="transcript"' in post["data"] and b"in wage" in post["data"]
    assert b'name="audio"' in post["data"]
    assert poll["url"] == "https://api.olewave.com/olign/v1/j1"
    assert [(w.label, w.start, w.end) for w in out.words] == [("in", 0.14, 0.31), ("wage", 0.31, 0.75)]
    assert out.words[0].conf == pytest.approx(0.98)
    assert [(p.label, p.start, p.end) for p in out.phones] == [
        ("ih", 0.14, 0.203), ("n", 0.203, 0.31), ("w", 0.31, 0.403)]
    assert out.meta["transcript_source"] == "client"


def test_track1_refuses_to_run_without_a_transcript(audio, tmp_path, monkeypatch, server):
    calls, _ = server
    with pytest.raises(AlignerError, match="needs the reference transcript"):
        _make(OlignV1, tmp_path, monkeypatch).align(audio, "")
    assert calls == []


def test_track2_sends_audio_alone(audio, tmp_path, monkeypatch, server):
    calls, state = server
    state["final"] = {**DONE, "transcript_source": "asr"}
    out = _make(OlignV1ASR, tmp_path, monkeypatch).align(audio, "the reference is never sent")
    assert b'name="transcript"' not in calls[0]["data"]
    assert b"the reference is never sent" not in calls[0]["data"]
    assert out.meta["transcript_source"] == "asr"
    assert [w.label for w in out.words] == ["in", "wage"]


def test_no_speech_is_an_empty_answer_and_is_cached(audio, tmp_path, monkeypatch, server):
    calls, state = server
    state["final"] = {"state": "failed",
                      "log_tail": "no transcript given and no speech recognized in the audio"}
    a = _make(OlignV1ASR, tmp_path, monkeypatch)
    out = a.align(audio, "")
    assert out.words == [] and out.phones == [] and out.meta["no_speech"] is True
    n = len(calls)
    assert a.align(audio, "").meta["cached"] is True and len(calls) == n


def test_any_other_failure_raises(audio, tmp_path, monkeypatch, server):
    _, state = server
    state["final"] = {"state": "failed", "log_tail": "pipeline crashed"}
    with pytest.raises(Exception, match="pipeline crashed"):
        _make(OlignV1ASR, tmp_path, monkeypatch).align(audio, "")


def test_polls_until_done(audio, tmp_path, monkeypatch):
    seq = iter([{"job_id": "j1"}, {"state": "queued"}, {"state": "running"}, DONE])
    seen = []
    monkeypatch.setattr(P, "request_json", lambda url, **kw: seen.append(url) or next(seq))
    monkeypatch.setattr(P.time, "sleep", lambda s: None)
    out = _make(OlignV1, tmp_path, monkeypatch).align(audio, "in wage")
    assert len(out.words) == 2 and seen.count("https://api.olewave.com/olign/v1/j1") == 3


def test_track1_and_track2_never_share_a_cache_entry(audio, tmp_path, monkeypatch, server):
    blob = Path(audio).read_bytes()
    t1 = _make(OlignV1, tmp_path, monkeypatch)._cache_path(blob, "in wage")
    t2 = _make(OlignV1ASR, tmp_path, monkeypatch)._cache_path(blob)
    assert t1 != t2
