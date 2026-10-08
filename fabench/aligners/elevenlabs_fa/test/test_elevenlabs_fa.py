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

"""ElevenLabs forced alignment, with the network stubbed so nothing is billed."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import pytest

from fabench.aligners.base import AlignerError, BatchItem
from fabench.aligners.elevenlabs_fa import ElevenLabsFA
from fabench.timestamp_asrs.cloud import adapter as A
from fabench.timestamp_asrs.cloud import providers as P

RESPONSE = {
    "characters": [{"text": "h", "start": 0.10, "end": 0.15}],
    "words": [
        {"text": "hello", "start": 0.10, "end": 0.42, "loss": 0.8},
        {"text": " ", "start": 0.42, "end": 0.50, "loss": 0.0},
        {"text": "world.", "start": 0.50, "end": 0.91, "loss": 1.1},
    ],
    "loss": 0.95,
}


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "a.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000)
    return str(path)


def _make(tmp_path, monkeypatch, cls=ElevenLabsFA, **params):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    a = cls(cls.provider, {"cache_dir": str(tmp_path / "cache"), "concurrency": 2, **params})
    a.load()
    return a


def _recording(calls):
    def fake(url, **kw):
        calls.append({"url": url, **kw})
        return RESPONSE
    return fake


def test_sends_the_transcript_to_the_forced_alignment_endpoint(audio, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(P, "request_json", _recording(calls))
    out = _make(tmp_path, monkeypatch).align(audio, "hello world")
    (c,) = calls
    assert c["url"] == "https://api.elevenlabs.io/v1/forced-alignment"
    assert c["headers"]["xi-api-key"] == "k"
    assert b'name="text"' in c["data"] and b"hello world" in c["data"]
    assert b'name="file"' in c["data"]
    # Seconds as returned, the space between words dropped, punctuation off.
    assert [(w.label, w.start, w.end) for w in out.words] == [
        ("hello", 0.10, 0.42), ("world", 0.50, 0.91)]
    assert all(w.conf is None for w in out.words)
    assert out.meta["alignment_loss"] == pytest.approx(0.95)


def test_refuses_to_run_without_a_transcript(audio, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(P, "request_json", _recording(calls))
    with pytest.raises(AlignerError, match="needs the reference transcript"):
        _make(tmp_path, monkeypatch).align(audio, "  ")
    assert calls == []


def test_the_transcript_is_part_of_the_cache_key(audio, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(P, "request_json", _recording(calls))
    a = _make(tmp_path, monkeypatch)
    first = a.align(audio, "hello world")
    again = a.align(audio, "hello   world")       # same words, other spacing
    assert len(calls) == 1 and first.meta["cached"] is False and again.meta["cached"] is True
    a.align(audio, "hello there")                  # same audio, other words
    assert len(calls) == 2


def test_the_scribe_rows_cache_key_is_unchanged(audio, tmp_path, monkeypatch):
    """Adding the transcript to the key must not orphan Scribe's cached responses."""
    scribe = _make(tmp_path, monkeypatch, cls=A.ElevenLabs, model="scribe_v2",
                   language="eng", timestamps_granularity="word")
    blob = Path(audio).read_bytes()
    h = hashlib.sha256()
    for part in (scribe.provider, scribe.model, json.dumps(scribe.opts, sort_keys=True)):
        h.update(part.encode()); h.update(b"\0")
    h.update(blob)
    assert scribe._cache_path(blob).name == f"{h.hexdigest()}.json"


def test_max_calls_zero_bills_nothing(audio, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(P, "request_json", _recording(calls))
    with pytest.raises(AlignerError, match="max_calls"):
        _make(tmp_path, monkeypatch, max_calls=0).align(audio, "hello world")
    assert calls == []


def test_a_batch_sends_each_items_own_transcript(audio, tmp_path, monkeypatch):
    calls: list = []
    monkeypatch.setattr(P, "request_json", _recording(calls))
    items = [BatchItem("a", audio, "hello world"), BatchItem("b", audio, "good night")]
    out = _make(tmp_path, monkeypatch).align_corpus(items)
    assert set(out) == {"a", "b"}
    sent = sorted(next(t for t in (b"hello world", b"good night") if t in c["data"])
                  for c in calls)
    assert sent == [b"good night", b"hello world"]


def test_it_is_filed_under_track_1():
    from fabench.paths import tool_kind
    root = Path(__file__).resolve().parents[4]
    assert tool_kind(root, "elevenlabs_fa") == "aligners"
    assert tool_kind(root, "elevenlabs") == "timestamp_asrs"
    assert ElevenLabsFA.ignores_transcript is False
