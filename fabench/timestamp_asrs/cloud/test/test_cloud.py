# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""The commercial ASR adapters, with the network stubbed.

These tests exist because the real endpoints cost money and need keys, so the
first time anyone runs the real thing it will be a paid sweep over 45k
utterances. Everything that can be wrong without a network -- a response shape
misread, milliseconds taken for seconds, a non-word entry kept, a cache key
that ignores the model -- is wrong here first, for free.

The payloads below are the documented response SHAPES, not recordings of any
account's traffic.
"""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import pytest

from fabench.aligners.base import AlignerError, BatchItem
from fabench.timestamp_asrs.cloud import adapter as A
from fabench.timestamp_asrs.cloud import providers as P


def _wav(path, seconds=1.0, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\0\0" * int(rate * seconds))
    return str(path)


@pytest.fixture
def audio(tmp_path):
    return _wav(tmp_path / "a.wav")


def _make(cls, tmp_path, monkeypatch, **params):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_STT_API_KEY", "k")
    p = {"cache_dir": str(tmp_path / "cache"), "concurrency": 2, **params}
    a = cls(cls.provider, p)
    a.load()
    return a


# --------------------------------------------------------------- providers
def test_deepgram_parses_words(audio, tmp_path, monkeypatch):
    seen = {}

    def fake(url, **kw):
        seen["url"] = url; seen["headers"] = kw.get("headers")
        return {"results": {"channels": [{"alternatives": [{"words": [
            {"word": "hello", "start": 0.1, "end": 0.4, "confidence": 0.99},
            {"word": "World.", "start": 0.5, "end": 0.9, "confidence": 0.8},
        ]}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    out = _make(A.Deepgram, tmp_path, monkeypatch).align(audio)
    assert [(w.label, w.start, w.end) for w in out.words] == [
        ("hello", 0.1, 0.4), ("world", 0.5, 0.9)]
    assert out.words[0].conf == pytest.approx(0.99)
    # Raw words requested, not display text.
    assert "punctuate=false" in seen["url"] and "numerals=false" in seen["url"]
    assert seen["headers"]["Authorization"] == "Token k"


def test_assemblyai_milliseconds_become_seconds(audio, tmp_path, monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        if url.endswith("/upload"):
            return {"upload_url": "https://cdn/x"}
        if url.endswith("/transcript"):
            return {"id": "t1"}
        return {"status": "completed", "words": [
            {"text": "hello", "start": 100, "end": 400, "confidence": 0.9}]}

    monkeypatch.setattr(P, "request_json", fake)
    monkeypatch.setattr(P, "post_json",
                        lambda u, p, h, **kw: fake(u, **kw))
    out = _make(A.AssemblyAI, tmp_path, monkeypatch).align(audio)
    assert [(w.label, w.start, w.end) for w in out.words] == [("hello", 0.1, 0.4)]
    assert any(u.endswith("/upload") for u in calls)


def test_assemblyai_error_status_raises(audio, tmp_path, monkeypatch):
    def fake(url, **kw):
        if url.endswith("/upload"):
            return {"upload_url": "https://cdn/x"}
        if url.endswith("/transcript"):
            return {"id": "t1"}
        return {"status": "error", "error": "bad audio"}

    monkeypatch.setattr(P, "request_json", fake)
    monkeypatch.setattr(P, "post_json", lambda u, p, h, **kw: fake(u, **kw))
    with pytest.raises(Exception, match="bad audio"):
        _make(A.AssemblyAI, tmp_path, monkeypatch).align(audio)


def test_elevenlabs_drops_non_word_entries(audio, tmp_path, monkeypatch):
    import math

    monkeypatch.setattr(P, "request_json", lambda url, **kw: {"words": [
        {"text": "hello", "start": 0.1, "end": 0.4, "type": "word",
         "logprob": math.log(0.5)},
        {"text": " ", "start": 0.4, "end": 0.5, "type": "spacing"},
        {"text": "(laughter)", "start": 0.5, "end": 0.7, "type": "audio_event"},
        {"text": "world", "start": 0.7, "end": 1.0, "type": "word"},
    ]})
    out = _make(A.ElevenLabs, tmp_path, monkeypatch).align(audio)
    assert [w.label for w in out.words] == ["hello", "world"]
    assert out.words[0].conf == pytest.approx(0.5)
    assert out.words[1].conf is None          # no logprob reported


def test_google_v1_sends_pcm_not_riff(audio, tmp_path, monkeypatch):
    body = {}

    def fake(url, payload, headers, **kw):
        body.update(payload); body["url"] = url
        return {"results": [{"alternatives": [{"words": [
            {"word": "hello", "startTime": "0.100s", "endTime": "0.400s",
             "confidence": 0.9},
            {"word": "world", "startTime": {"seconds": "1", "nanos": 500000000},
             "endTime": {"seconds": "2"}},
        ]}]}]}

    monkeypatch.setattr(P, "post_json", fake)
    out = _make(A.GoogleSTT, tmp_path, monkeypatch).align(audio)
    assert [(w.label, w.start, w.end) for w in out.words] == [
        ("hello", 0.1, 0.4), ("world", 1.5, 2.0)]
    import base64
    sent = base64.b64decode(body["audio"]["content"])
    assert not sent.startswith(b"RIFF"), "the RIFF header would decode as samples"
    assert body["config"]["sampleRateHertz"] == 16000     # read from the file
    assert body["config"]["enableWordTimeOffsets"] is True
    assert "key=k" in body["url"]


def test_google_v2_refuses_an_api_key(audio, tmp_path, monkeypatch):
    """With only an API key available, v2 must refuse BEFORE spending a call."""
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    a = A.GoogleSTT("google_stt_chirp2", {"cache_dir": str(tmp_path / "c"),
                                          "project_id": "p",
                                          "location": "us-central1"})
    with pytest.raises(AlignerError) as e:
        a.load()
    # It asks for the bearer variable only. Naming the key variable here would
    # send someone to set the credential this endpoint cannot use.
    assert "GOOGLE_STT_ACCESS_TOKEN" in str(e.value)
    assert "GOOGLE_STT_API_KEY" not in str(e.value)


# ------------------------------------------------------------------- cache
def test_cache_prevents_a_second_call(audio, tmp_path, monkeypatch):
    n = {"calls": 0}

    def fake(url, **kw):
        n["calls"] += 1
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    first = a.align(audio)
    second = a.align(audio)
    assert n["calls"] == 1
    assert first.meta["cached"] is False and second.meta["cached"] is True
    assert [w.label for w in second.words] == ["hi"]

    # A different model must NOT be served the cached answer.
    b = _make(A.Deepgram, tmp_path, monkeypatch, model="nova-2")
    b.align(audio)
    assert n["calls"] == 2
    # Nor a different request option.
    c = _make(A.Deepgram, tmp_path, monkeypatch, numerals=True)
    c.align(audio)
    assert n["calls"] == 3


def test_max_calls_caps_spend(audio, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "results": {"channels": [{"alternatives": [{"words": []}]}]}})
    a = _make(A.Deepgram, tmp_path, monkeypatch, max_calls=1, cache=False,
              cache_dir=None)
    a.align(audio)
    with pytest.raises(AlignerError, match="max_calls"):
        a.align(_wav(tmp_path / "b.wav", seconds=2.0))


def test_missing_key_names_the_variable(tmp_path, monkeypatch):
    for v in ("DEEPGRAM_API_KEY",):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(AlignerError, match="DEEPGRAM_API_KEY"):
        A.Deepgram("deepgram", {"cache_dir": str(tmp_path)}).load()


# ------------------------------------------------------------------- batch
def test_align_corpus_omits_failures_and_keeps_going(audio, tmp_path, monkeypatch):
    def fake(url, **kw):
        if "boom" in json.dumps(kw.get("headers", {})):
            raise RuntimeError("no")
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    items = [BatchItem("ok", audio, "hi"),
             BatchItem("missing", str(tmp_path / "nope.wav"), "hi")]
    out = a.align_corpus(items)
    assert set(out) == {"ok"}          # the unreadable item is omitted, not fatal


def test_transcript_is_ignored(audio, tmp_path, monkeypatch):
    """Track 2: the reference transcript must not reach the vendor."""
    seen = {}

    def fake(url, **kw):
        seen["data"] = kw.get("data")
        return {"results": {"channels": [{"alternatives": [{"words": []}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    a.align(audio, "the reference words")
    assert b"reference" not in (seen["data"] or b"")
    assert A.Deepgram.ignores_transcript is True


# -------------------------------------------------------------------- http
def test_retries_then_succeeds(monkeypatch):
    from fabench.timestamp_asrs.cloud import http as H
    import urllib.error

    n = {"i": 0}

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        n["i"] += 1
        if n["i"] < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down",
                                         {"Retry-After": "0"}, io.BytesIO(b""))
        return R(b'{"ok":true}')

    monkeypatch.setattr(H.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    assert H.request_json("https://x", retries=5) == {"ok": True}
    assert n["i"] == 3


def test_a_retry_is_signed_again(monkeypatch):
    """Callable headers are re-evaluated per attempt, so a retry carries a
    FRESH signature.

    THE BUG THIS EXISTS FOR. SigV4 stamps the minute it was signed into the
    request; Transcribe refuses a signature over five minutes old and S3 one
    skewed by over fifteen. The AWS path used to sign once and hand the same
    headers to every attempt, so once the backoff pushed an attempt past those
    limits the retry could not succeed however healthy the service was. The
    first Transcribe sweep lost four items to it, reported as
    InvalidSignatureException and RequestTimeTooSkewed.
    """
    from fabench.timestamp_asrs.cloud import http as H
    import urllib.error

    n = {"i": 0}
    sent = []

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        n["i"] += 1
        sent.append(req.headers.get("X-signed-at"))
        if n["i"] < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down",
                                         {"Retry-After": "0"}, io.BytesIO(b""))
        return R(b'{"ok":true}')

    stamp = {"t": 0}

    def sign_now():
        stamp["t"] += 1
        return {"X-signed-at": str(stamp["t"])}

    monkeypatch.setattr(H.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    assert H.request_json("https://x", headers=sign_now, retries=5) == {"ok": True}
    assert sent == ["1", "2", "3"], sent          # a new signature each attempt


def test_a_dict_of_headers_still_works(monkeypatch):
    """The callable is an option, not a requirement: every other provider
    passes a plain dict and must keep working."""
    from fabench.timestamp_asrs.cloud import http as H

    sent = []

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        sent.append(req.headers.get("X-key"))
        return R(b'{"ok":true}')

    monkeypatch.setattr(H.urllib.request, "urlopen", fake_urlopen)
    assert H.request_json("https://x", headers={"X-key": "v"}) == {"ok": True}
    assert sent == ["v"]


def test_does_not_retry_a_bad_key(monkeypatch):
    from fabench.timestamp_asrs.cloud import http as H
    import urllib.error

    n = {"i": 0}

    def fake_urlopen(req, timeout=None):
        n["i"] += 1
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {},
                                     io.BytesIO(b"bad key"))

    monkeypatch.setattr(H.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    with pytest.raises(H.CloudASRError, match="401"):
        H.request("https://x", retries=5)
    assert n["i"] == 1, "a 401 is not worth five paid retries"


def test_multipart_round_trip():
    from fabench.timestamp_asrs.cloud.http import multipart
    ctype, body = multipart({"model_id": "scribe_v1"},
                            {"file": ("a.wav", "audio/wav", b"\x00\x01")})
    assert ctype.startswith("multipart/form-data; boundary=")
    assert b'name="model_id"' in body and b"scribe_v1" in body
    assert b'filename="a.wav"' in body and b"\x00\x01" in body


def test_behaviour_options_reach_the_call_but_not_the_cache_key(audio, tmp_path,
                                                                monkeypatch):
    """poll_interval_s is read by the provider and must not invalidate a cache.

    It was in neither set once: the recipe declared it, the provider defaulted
    it, and nothing connected the two.
    """
    seen = {}

    def fake(url, **kw):
        if url.endswith("/upload"):
            return {"upload_url": "https://cdn/x"}
        if url.endswith("/transcript"):
            return {"id": "t1"}
        return {"status": "completed", "words": []}

    monkeypatch.setattr(P, "request_json", fake)
    monkeypatch.setattr(P, "post_json", lambda u, p, h, **kw: fake(u, **kw))

    a = _make(A.AssemblyAI, tmp_path, monkeypatch, poll_interval_s=7.5)
    assert a._call_opts["poll_interval_s"] == 7.5      # reaches the provider
    assert "poll_interval_s" not in a.opts             # not in the cache key

    b = _make(A.AssemblyAI, tmp_path, monkeypatch, poll_interval_s=1.0)
    assert a._cache_path(b"x") == b._cache_path(b"x"), \
        "changing a poll interval must not orphan a corpus of cached responses"


def test_a_model_that_ignores_word_offsets_fails_loudly(audio, tmp_path, monkeypatch):
    """A transcript with no word times must stop a sweep, not produce empty rows.

    Google's original Chirp ignored enableWordTimeOffsets, and model support
    still varies by model and region. Unguarded, that is a perfect transcript,
    zero boundaries and a full invoice.
    """
    monkeypatch.setattr(P, "post_json", lambda u, p, h, **kw: {
        "results": [{"alternatives": [{"transcript": "hello world"}]}]})
    with pytest.raises(Exception, match="no word timings"):
        _make(A.GoogleSTT, tmp_path, monkeypatch).align(audio)


def test_genuine_silence_is_not_an_error(audio, tmp_path, monkeypatch):
    """No transcript and no words is a silent utterance, which is legitimate."""
    monkeypatch.setattr(P, "post_json", lambda u, p, h, **kw: {"results": []})
    out = _make(A.GoogleSTT, tmp_path, monkeypatch).align(audio)
    assert out.words == []


def test_v2_skips_an_api_key_and_uses_the_token_command(audio, tmp_path, monkeypatch):
    """An API key in the environment must not shadow the bearer token for v2.

    Having both set is the normal state once someone has tried v1 first, and
    preferring the key told them to set a variable they had already set.
    """
    monkeypatch.setenv("GOOGLE_STT_API_KEY", "AIzaFAKE")
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    a = A.GoogleSTT("google_stt_chirp2", {
        "cache_dir": str(tmp_path / "c"), "project_id": "p",
        "location": "us-central1",
        "access_token_cmd": "printf tok-from-gcloud"})
    a.load()
    assert a.key == "Bearer tok-from-gcloud"


def test_v1_still_takes_the_api_key(audio, tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_STT_API_KEY", "AIzaFAKE")
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    a = A.GoogleSTT("google_stt", {"cache_dir": str(tmp_path / "c")})
    a.load()
    assert a.key == "AIzaFAKE"


def test_v2_without_any_bearer_says_which_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_STT_API_KEY", "AIzaFAKE")
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    a = A.GoogleSTT("google_stt_chirp2", {"cache_dir": str(tmp_path / "c"),
                                          "project_id": "p"})
    with pytest.raises(AlignerError) as e:
        a.load()
    msg = str(e.value)
    assert "GOOGLE_STT_ACCESS_TOKEN" in msg
    assert "GOOGLE_STT_API_KEY" in msg and "bearer token" in msg
    assert "AIzaFAKE" not in msg, "never echo a credential into an error"


def test_cache_stores_the_vendor_response_not_our_reading(audio, tmp_path, monkeypatch):
    """A parser fix must be free. Only the raw body may be cached."""
    import json as _json

    raw = {"results": {"channels": [{"alternatives": [
        {"words": [{"word": "hi", "start": 0.0, "end": 0.2, "confidence": 0.9}]}]}]}}
    monkeypatch.setattr(P, "request_json", lambda url, **kw: raw)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    a.align(audio)

    entry = next((tmp_path / "cache").rglob("*.json"))
    rec = _json.loads(entry.read_text())
    assert rec["raw"] == raw, "the vendor's own response must be what is stored"
    assert "words" not in rec, "our parse must not be what is stored"
    assert rec["provider"] == "deepgram" and rec["model"] == "nova-3"
    assert "fetched_at" in rec


def test_a_parser_fix_reaches_cached_calls(audio, tmp_path, monkeypatch):
    """The point of caching raw: change the parse, re-read, pay nothing."""
    n = {"calls": 0}

    def fake(url, **kw):
        n["calls"] += 1
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    assert [w.label for w in a.align(audio).words] == ["hi"]

    # A "corrected" parser that also uppercases. No new call may happen.
    def parse2(r, model, opts):
        w, m = P.deepgram_parse(r, model, opts)
        return [["re-" + x[0], x[1], x[2], x[3]] for x in w], m

    b = _make(A.Deepgram, tmp_path, monkeypatch)
    b._parse = parse2
    out = b.align(audio)
    assert [w.label for w in out.words] == ["re-hi"]
    assert out.meta["cached"] is True
    assert n["calls"] == 1, "re-parsing must not re-bill"


def test_cache_sits_beside_a_nested_recipe(monkeypatch):
    """google_stt_chirp2 lives under google_stt/exps/chirp2, not at top level.

    The old default built the path from the tool NAME and was relative, so a
    nested recipe's cache went to a stray folder whose location depended on the
    working directory the sweep was launched from.
    """
    monkeypatch.setenv("GOOGLE_STT_ACCESS_TOKEN", "t")
    a = A.GoogleSTT("google_stt_chirp2", {"project_id": "p"})
    a.load()
    assert a.cache_dir.is_absolute()
    assert a.cache_dir.parent.name == "chirp2"
    assert a.cache_dir.parent.parent.name == "exps"


# ----------------------------------------------------------------- latency
def test_latency_is_recorded_on_a_real_call(audio, tmp_path, monkeypatch):
    import time as _t

    def slow(url, **kw):
        _t.sleep(0.05)
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}

    monkeypatch.setattr(P, "request_json", slow)
    out = _make(A.Deepgram, tmp_path, monkeypatch).align(audio)
    assert out.meta["latency_s"] >= 0.05
    assert out.meta["audio_s"] == pytest.approx(1.0, abs=0.01)


def test_a_cache_hit_never_reports_the_disk_read(audio, tmp_path, monkeypatch):
    """The disk read must not enter the percentiles as a very fast request.

    The first version of this dropped latency on a hit entirely, which lost the
    measurement instead of protecting it. The timing of the ORIGINAL call is
    replayed; the read itself is never timed.
    """
    import time as _t

    monkeypatch.setattr(P, "request_json", lambda url, **kw: (_t.sleep(0.05) or {
        "results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}))
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    live = a.align(audio).meta["latency_s"]
    hit = a.align(audio).meta["latency_s"]
    assert hit == pytest.approx(live)
    assert hit >= 0.05, "a disk read would be orders of magnitude faster"


def test_retries_and_backoff_are_attributed_to_us(audio, tmp_path, monkeypatch):
    """A slow call must be separable into vendor time and our own backoff."""
    from fabench.timestamp_asrs.cloud import http as H
    import io
    import urllib.error

    n = {"i": 0}

    def flaky(req, timeout=None):
        n["i"] += 1
        if n["i"] < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down",
                                         {"Retry-After": "0"}, io.BytesIO(b""))

        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R(b'{"results":{"channels":[{"alternatives":[{"words":[]}]}]}}')

    monkeypatch.setattr(H.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    out = _make(A.Deepgram, tmp_path, monkeypatch).align(audio)
    assert out.meta["retries"] == 2
    assert "latency_s" in out.meta


def test_repairs_are_counted_because_they_are_not_recoverable(audio, tmp_path,
                                                              monkeypatch):
    """max(end,start) and the sort destroy evidence, so record it at the source.

    Everything else about a cloud row is re-derivable from the cached raw body.
    These two are not, which is why they cannot wait for a later rescore.
    """
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "results": {"channels": [{"alternatives": [{"words": [
            {"word": "b", "start": 0.50, "end": 0.70},
            {"word": "a", "start": 0.10, "end": 0.30},   # out of order
            {"word": "c", "start": 0.90, "end": 0.80},   # reversed
            {"word": "d", "start": 1.00, "end": 1.00},   # zero length
        ]}]}]}})
    out = _make(A.Deepgram, tmp_path, monkeypatch).align(audio)
    assert out.meta["n_disordered"] == 1
    assert out.meta["n_reversed"] == 1
    assert out.meta["n_zero_len"] == 1
    assert [w.label for w in out.words] == ["a", "b", "c", "d"]   # still sorted
    assert out.words[2].end >= out.words[2].start                 # still repaired


def test_a_clean_response_records_no_repair_counts(audio, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "results": {"channels": [{"alternatives": [{"words": [
            {"word": "a", "start": 0.1, "end": 0.3},
            {"word": "b", "start": 0.3, "end": 0.5},
        ]}]}]}})
    meta = _make(A.Deepgram, tmp_path, monkeypatch).align(audio).meta
    assert not any(k.startswith("n_") for k in meta), meta


def test_a_cache_hit_replays_the_original_timing(audio, tmp_path, monkeypatch):
    """Re-running a cached cell must not erase the latency it measured.

    It did: the second run rewrote hyp.jsonl with records carrying no timing,
    so a cell measured over 400 requests came back reporting one.
    """
    import time as _t

    def slow(url, **kw):
        _t.sleep(0.05)
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}}

    monkeypatch.setattr(P, "request_json", slow)
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    first = a.align(audio).meta
    second = _make(A.Deepgram, tmp_path, monkeypatch).align(audio).meta

    assert second["cached"] is True
    assert second["latency_s"] == pytest.approx(first["latency_s"])
    assert second["fetched_at"], "a replayed timing must say when it was taken"
    # The disk read itself is never what gets reported.
    assert second["latency_s"] >= 0.05


def test_an_expiring_token_is_reminted_mid_sweep(audio, tmp_path, monkeypatch):
    """gcloud tokens last an hour; load() is idempotent. Without a refresh a
    long sweep runs past expiry, and a 401 is not retried by design.
    """
    import time as _t

    minted = {"n": 0}

    def fake_run(cmd, **kw):
        minted["n"] += 1
        class R:
            stdout = f"tok{minted['n']}"
        return R()

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_STT_API_KEY", raising=False)
    monkeypatch.setattr(P, "post_json", lambda u, p, h, **kw: {"results": []})

    a = A.GoogleSTT("google_stt_chirp2", {
        "cache_dir": str(tmp_path / "c"), "project_id": "p",
        "location": "us-central1", "access_token_cmd": "gcloud auth print-access-token",
        "token_ttl_s": 1000})
    a.load()
    assert a.key == "Bearer tok1"
    a.align(audio)
    assert minted["n"] == 1, "not yet old enough"

    a._key_at = _t.monotonic() - 2000          # now past the ttl
    a.align(_wav(tmp_path / "b.wav", seconds=1.5))
    assert a.key == "Bearer tok2"
    assert minted["n"] == 2


def test_a_static_api_key_is_never_reminted(audio, tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    assert a._key_refreshable is False
    a._key_at = 0
    assert a._fresh_key() == "k"


def test_deepgram_records_the_version_it_actually_served(audio, tmp_path, monkeypatch):
    """The requested alias cannot detect an endpoint swapped underneath."""
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "metadata": {"request_id": "abc-123",
                     "model_info": {"uuid": {"name": "general-nova-3",
                                             "version": "2025-07-31.0",
                                             "arch": "nova-3"}}},
        "results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}})
    meta = _make(A.Deepgram, tmp_path, monkeypatch).align(audio).meta
    assert meta["served_model"] == "general-nova-3"
    assert meta["served_version"] == "2025-07-31.0"
    assert meta["request_id"] == "abc-123"


def test_a_response_without_version_info_is_not_an_error(audio, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "results": {"channels": [{"alternatives": [
            {"words": [{"word": "hi", "start": 0.0, "end": 0.2}]}]}]}})
    meta = _make(A.Deepgram, tmp_path, monkeypatch).align(audio).meta
    assert "served_version" not in meta and meta["api_model"] == "nova-3"


def test_a_refused_token_is_reminted_and_retried_once(audio, tmp_path, monkeypatch):
    """Age-based refresh is not enough and assuming it was cost 3,619 items.

    Each cell is its own process, so the age clock restarts every ~20 minutes
    and a 2400 s TTL never fires -- while gcloud hands back a CACHED token that
    may already be nearly expired. Only the 401 itself is a reliable signal.
    """
    from fabench.timestamp_asrs.cloud.http import CloudASRError

    minted = {"n": 0}

    def fake_run(cmd, **kw):
        minted["n"] += 1
        class R: stdout = f"tok{minted['n']}"
        return R()

    calls = {"n": 0}

    def flaky(url, payload, headers, **kw):
        calls["n"] += 1
        if headers.get("Authorization") == "Bearer tok1":
            raise CloudASRError('HTTP 401: b\'{"error":{"status":"UNAUTHENTICATED"}}\'')
        return {"results": [{"alternatives": [{"words": [
            {"word": "hi", "startOffset": "0.100s", "endOffset": "0.200s"}]}]}]}

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    monkeypatch.setattr(P, "post_json", flaky)
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_STT_API_KEY", raising=False)

    a = A.GoogleSTT("google_stt_chirp2", {
        "cache_dir": str(tmp_path / "c"), "project_id": "p", "location": "us-central1",
        "access_token_cmd": "gcloud auth print-access-token"})
    a.load()
    a._key_at -= 10                       # past the 5 s just-refreshed guard
    out = a.align(audio)
    assert [w.label for w in out.words] == ["hi"]
    assert minted["n"] == 2, "the token must be re-minted, not reused"
    assert calls["n"] == 2, "exactly one retry"


def test_a_genuinely_bad_key_still_fails_fast(audio, tmp_path, monkeypatch):
    """One retry, not a loop: a wrong key must not burn attempts."""
    from fabench.timestamp_asrs.cloud.http import CloudASRError

    n = {"mint": 0, "call": 0}

    def fake_run(cmd, **kw):
        n["mint"] += 1
        class R: stdout = "always-bad"
        return R()

    def always401(url, payload, headers, **kw):
        n["call"] += 1
        raise CloudASRError("HTTP 401: unauthorized")

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    monkeypatch.setattr(P, "post_json", always401)
    monkeypatch.delenv("GOOGLE_STT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_STT_API_KEY", raising=False)
    a = A.GoogleSTT("g", {"cache_dir": str(tmp_path / "c"), "project_id": "p",
                          "access_token_cmd": "x"})
    a.load()
    a._key_at -= 10
    with pytest.raises(CloudASRError):
        a.align(audio)
    assert n["call"] == 2, "one retry only"


def test_max_rpm_bounds_the_request_rate(audio, tmp_path, monkeypatch):
    """Concurrency does not bound the rate when the cache is warm.

    A hit returns at memory speed, so a mostly-cached re-run cycles the pool
    far faster than a cold one -- which is how Chirp 2 lost 2,020 of 4,513
    items to a per-minute quota on a cell it had already completed cold.
    """
    import time as _t

    clock = {"t": 1000.0}
    slept = {"s": 0.0}
    monkeypatch.setattr(A.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(A.time, "sleep", lambda s: (slept.__setitem__("s", slept["s"] + s),
                                                    clock.__setitem__("t", clock["t"] + s)))
    monkeypatch.setattr(P, "request_json", lambda url, **kw: {
        "results": {"channels": [{"alternatives": [{"words": []}]}]}})

    a = _make(A.Deepgram, tmp_path, monkeypatch, max_rpm=3, cache=False, cache_dir=None)
    for _ in range(3):
        a._throttle()
    assert slept["s"] == 0.0, "the first three fit inside the window"
    a._throttle()
    assert slept["s"] > 0, "the fourth must wait for the window to roll"


def test_no_max_rpm_means_no_throttle(audio, tmp_path, monkeypatch):
    a = _make(A.Deepgram, tmp_path, monkeypatch)
    assert a.max_rpm is None
    for _ in range(50):
        a._throttle()          # returns immediately, no bookkeeping


# ------------------------------------------------------------------- IBM
def test_ibm_parses_bare_timestamp_triples(audio, tmp_path, monkeypatch):
    """Watson sends [word, start, end] triples, not objects like everyone else."""
    seen = {}

    def fake(url, **kw):
        seen["url"] = url; seen["headers"] = kw.get("headers")
        return {"results": [{"final": True, "alternatives": [{
            "transcript": "when i was ",
            "confidence": 0.98,
            "timestamps": [["when", 0.04, 0.16], ["i", 0.16, 0.32],
                           ["was", 0.32, 0.44]],
            "word_confidence": [["when", 0.99], ["i", 0.95], ["was", 0.9]],
        }]}]}

    monkeypatch.setattr(P, "request_json", fake)
    monkeypatch.setenv("IBM_STT_API_KEY", "k")
    a = A.IBMWatson("ibm", {"cache_dir": str(tmp_path / "c"),
                            "service_url": "https://api.us-south.speech-to-text"
                                           ".watson.cloud.ibm.com/instances/xyz"})
    a.load()
    out = a.align(audio)
    assert [(w.label, w.start, w.end) for w in out.words] == [
        ("when", 0.04, 0.16), ("i", 0.16, 0.32), ("was", 0.32, 0.44)]
    assert out.words[0].conf == pytest.approx(0.99)
    # word times are OPT-IN on Watson; without this it returns text only
    assert "timestamps=true" in seen["url"]
    assert "word_confidence=true" in seen["url"]
    assert "smart_formatting=false" in seen["url"]
    assert seen["headers"]["Authorization"].startswith("Basic ")


def test_ibm_without_a_service_url_says_so(audio, tmp_path, monkeypatch):
    """The instance URL cannot be guessed, so the error has to name it."""
    monkeypatch.setenv("IBM_STT_API_KEY", "k")
    a = A.IBMWatson("ibm", {"cache_dir": str(tmp_path / "c")})
    a.load()
    with pytest.raises(Exception, match="service_url"):
        a.align(audio)


def test_every_recipe_param_reaches_something(monkeypatch):
    """A parameter a recipe sets and nothing reads is a silent lie.

    It has happened three times: poll_interval_s, which the AssemblyAI recipe
    declared and the provider defaulted past; and service_url and
    profanity_filter on IBM, one of which made the adapter refuse every call.
    A recipe is the record of what was run, so a key that reaches nothing makes
    that record wrong.
    """
    import glob

    import yaml

    from fabench.timestamp_asrs.cloud.adapter import _BEHAVIOUR_KEYS, _OPT_KEYS

    adapter_level = {
        "model", "concurrency", "timeout_s", "retries", "cache", "cache_dir",
        "max_calls", "max_rpm", "key_env", "access_token_cmd", "token_ttl_s",
        "venv", "worker", "device", "env",
    }
    known = set(_OPT_KEYS) | set(_BEHAVIOUR_KEYS) | adapter_level
    cloud = {"deepgram", "assemblyai", "elevenlabs", "google_stt",
             "speechmatics", "ibm"}
    orphans = []
    for f in (glob.glob("evals/timestamp_asrs/*/config.yaml")
              + glob.glob("evals/timestamp_asrs/*/exps/*/config.yaml")):
        d = yaml.safe_load(Path(f).read_text()) or {}
        if d.get("adapter") not in cloud:
            continue
        for k in (d.get("params") or {}):
            if k not in known:
                orphans.append(f"{d['name']}.{k}")
    assert not orphans, f"recipe params that reach nothing: {orphans}"


# ------------------------------------------------------------------ AWS
# The signer is the part with no second chance: a wrong signature reads as a
# bad secret key, so it is checked against AWS's own published test vector
# rather than against itself.
def test_sigv4_matches_the_published_vector():
    import datetime

    from fabench.timestamp_asrs.cloud.awssig import sign_headers
    got = sign_headers(
        method="GET", url="https://example.amazonaws.com/",
        region="us-east-1", service="service",
        access_key="AKIDEXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        now=datetime.datetime(2015, 8, 30, 12, 36, 0,
                              tzinfo=datetime.timezone.utc))
    assert got["Authorization"] == (
        "AWS4-HMAC-SHA256 "
        "Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request, "
        "SignedHeaders=host;x-amz-date, "
        "Signature=5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31")


def test_sigv4_signs_s3_paths_once_and_others_twice():
    """The single place SigV4 treats S3 differently from everything else."""
    from fabench.timestamp_asrs.cloud.awssig import canonical_uri
    assert canonical_uri("/a b/c", service="s3") == "/a%20b/c"
    assert canonical_uri("/a b/c", service="transcribe") == "/a%2520b/c"


def test_aws_parse_drops_punctuation_items(tmp_path):
    """Punctuation shares the item list with the words and carries no times."""
    words, meta = P.aws_parse({
        "jobName": "j",
        "results": {"transcripts": [{"transcript": "hi there."}], "items": [
            {"type": "pronunciation", "start_time": "0.04", "end_time": "0.52",
             "alternatives": [{"content": "hi", "confidence": "0.99"}]},
            {"type": "punctuation",
             "alternatives": [{"content": ".", "confidence": None}]},
            {"type": "pronunciation", "start_time": "0.60", "end_time": "0.90",
             "alternatives": [{"content": "there", "confidence": "0.98"}]},
        ]}}, "en-US", {})
    assert [w[0] for w in words] == ["hi", "there"]
    assert words[0][1] == pytest.approx(0.04)
    assert words[1][2] == pytest.approx(0.90)


def test_aws_parse_raises_when_a_transcript_has_no_times():
    """The spend guard. A transcript with no word times means an empty row."""
    with pytest.raises(P.CloudASRError, match="no word timings"):
        P.aws_parse({"results": {"transcripts": [{"transcript": "hello"}],
                                 "items": []}}, "en-US", {})


def test_aws_needs_both_halves_of_the_credential(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    with pytest.raises(P.CloudASRError, match="AWS_ACCESS_KEY_ID"):
        P._aws_creds({}, "secret")


def test_aws_names_the_bucket_it_is_missing(monkeypatch):
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
    with pytest.raises(P.CloudASRError, match="S3"):
        P._aws_bucket({})


def test_aws_staging_options_stay_out_of_the_cache_key(audio, tmp_path,
                                                       monkeypatch):
    """Which bucket the audio passed through cannot change what AWS heard.

    If it could, moving a bucket would re-bill a whole corpus.
    """
    from fabench.timestamp_asrs.cloud.adapter import _OPT_KEYS
    for k in ("s3_bucket", "s3_prefix", "keep_s3_object", "access_key_id"):
        assert k not in _OPT_KEYS
    # region is the exception, because Amazon rolls models out by region.
    assert "region" in _OPT_KEYS


def test_aws_runs_the_whole_four_call_sequence(audio, tmp_path, monkeypatch):
    """PUT the object, start the job, poll it, fetch the transcript, clean up.

    The signing is NOT mocked here. Only the socket is, so a signature that
    cannot be built still fails this test.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("AWS_S3_BUCKET", "a-bucket")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    seen = []

    def fake_request(url, *, method="GET", headers=None, data=None, **kw):
        headers = headers() if callable(headers) else (headers or {})
        target = headers.get("X-Amz-Target", "")
        seen.append((method, url.split("?")[0], target))
        # Everything that is not the presigned transcript GET must be signed.
        if "amazonaws.com" in url and "presigned" not in url:
            assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")
        if target.endswith("StartTranscriptionJob"):
            return b'{"TranscriptionJob":{"TranscriptionJobStatus":"IN_PROGRESS"}}'
        if target.endswith("GetTranscriptionJob"):
            return (b'{"TranscriptionJob":{"TranscriptionJobStatus":"COMPLETED",'
                    b'"Transcript":{"TranscriptFileUri":"https://presigned/x.json"}}}')
        if url.startswith("https://presigned/"):
            return json.dumps({"jobName": "j", "results": {
                "transcripts": [{"transcript": "hi"}],
                "items": [{"type": "pronunciation", "start_time": "0.1",
                           "end_time": "0.4",
                           "alternatives": [{"content": "hi",
                                             "confidence": "0.9"}]}]}}).encode()
        return b""                      # the S3 PUT and DELETE

    monkeypatch.setattr(P, "request", fake_request)
    a = A.AWSTranscribe("aws", {"cache_dir": str(tmp_path / "c"),
                                "poll_interval_s": 0})
    a.load()
    out = a.align(audio)
    assert [w.label for w in out.words] == ["hi"]
    assert out.words[0].start == pytest.approx(0.1)

    methods = [(m, t.split(".")[-1] or u.split("/")[2]) for m, u, t in seen]
    assert methods[0][0] == "PUT"                       # audio to S3
    assert methods[1][1] == "StartTranscriptionJob"
    assert methods[2][1] == "GetTranscriptionJob"
    assert seen[3][1] == "https://presigned/x.json"     # unsigned, presigned
    assert seen[4][0] == "DELETE"                       # staged object removed


def test_aws_keeps_the_s3_object_when_asked(audio, tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("AWS_S3_BUCKET", "a-bucket")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    seen = []

    def fake_request(url, *, method="GET", headers=None, data=None, **kw):
        seen.append(method)
        h = headers() if callable(headers) else (headers or {})
        t = h.get("X-Amz-Target", "")
        if t.endswith("GetTranscriptionJob"):
            return (b'{"TranscriptionJob":{"TranscriptionJobStatus":"COMPLETED",'
                    b'"Transcript":{"TranscriptFileUri":"https://p/x.json"}}}')
        if url.startswith("https://p/"):
            return json.dumps({"results": {"transcripts": [], "items": [
                {"type": "pronunciation", "start_time": "0", "end_time": "1",
                 "alternatives": [{"content": "a"}]}]}}).encode()
        return b'{"TranscriptionJob":{"TranscriptionJobStatus":"IN_PROGRESS"}}'

    monkeypatch.setattr(P, "request", fake_request)
    a = A.AWSTranscribe("aws", {"cache_dir": str(tmp_path / "c"),
                                "poll_interval_s": 0, "keep_s3_object": True})
    a.load()
    a.align(audio)
    assert "DELETE" not in seen


def test_aws_throttling_is_a_400_and_must_still_be_retried(monkeypatch):
    """AWS says "slow down" with HTTP 400 and an exception name in the body.

    A 400 is correctly never retried on status alone, so without the body
    match every throttled call on a fast cell would be dropped rather than
    backed off. That is silent item loss, and it is the failure this guards.
    """
    import urllib.error

    from fabench.timestamp_asrs.cloud import http as H

    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(
                req.full_url, 400, "Bad Request", {},
                io.BytesIO(b'{"__type":"ThrottlingException",'
                           b'"message":"Rate exceeded"}'))
        class R:
            def read(self): return b"ok"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setattr(H.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    out = H.request("https://transcribe.us-west-1.amazonaws.com/",
                    retry_body=P.AWS_RETRY_BODY, backoff_s=0.0)
    assert out == b"ok"
    assert len(calls) == 3


def test_a_plain_400_is_still_not_retried(monkeypatch):
    """The other half. A malformed request must not be billed four more times."""
    import urllib.error

    from fabench.timestamp_asrs.cloud import http as H
    calls = []

    def bad(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {},
            io.BytesIO(b'{"__type":"BadRequestException"}'))

    monkeypatch.setattr(H.urllib.request, "urlopen", bad)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    with pytest.raises(H.CloudASRError):
        H.request("https://transcribe.us-west-1.amazonaws.com/",
                  retry_body=P.AWS_RETRY_BODY, backoff_s=0.0)
    assert len(calls) == 1


def test_aws_deletes_the_staged_object_even_when_the_job_fails(audio, tmp_path,
                                                               monkeypatch):
    """The cleanup must run on the failure path too.

    It used to sit after the transcript fetch, so anything that raised in
    between left the audio in the bucket with nothing afterwards aware of it.
    Seen for real: one failed smoke test against an unsubscribed account
    orphaned its object.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("AWS_S3_BUCKET", "a-bucket")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    seen = []

    def fake_request(url, *, method="GET", headers=None, data=None, **kw):
        seen.append(method)
        h = headers() if callable(headers) else (headers or {})
        if h.get("X-Amz-Target", "").endswith("StartTranscriptionJob"):
            raise P.CloudASRError("HTTP 400: SubscriptionRequiredException")
        return b""

    monkeypatch.setattr(P, "request", fake_request)
    a = A.AWSTranscribe("aws", {"cache_dir": str(tmp_path / "c"),
                                "poll_interval_s": 0})
    a.load()
    with pytest.raises(Exception):
        a.align(audio)
    assert seen[0] == "PUT", seen
    assert "DELETE" in seen, f"staged object was orphaned: {seen}"


# ---------------------------------------------------------------- Azure
def test_azure_strips_glued_punctuation_but_not_internal(tmp_path):
    """Azure is the only provider that glues the mark onto the word.

    The scorer lowercases and does not strip, so "afternoon." would count as a
    substitution against every clause-final gold word.
    """
    words, _ = P.azure_parse({"phrases": [{"confidence": 0.9, "words": [
        {"text": "good", "offsetMilliseconds": 960, "durationMilliseconds": 240},
        {"text": "afternoon.", "offsetMilliseconds": 1200,
         "durationMilliseconds": 400},
        {"text": "don't", "offsetMilliseconds": 1600,
         "durationMilliseconds": 200},
        {"text": "well-known", "offsetMilliseconds": 1800,
         "durationMilliseconds": 300},
        {"text": ".", "offsetMilliseconds": 2100, "durationMilliseconds": 0},
    ]}]}, "en-US", {})
    assert [w[0] for w in words] == ["good", "afternoon", "don't", "well-known"]


def test_azure_converts_duration_to_an_end_time(tmp_path):
    """Azure reports offset and DURATION; everything else here reports an end."""
    words, _ = P.azure_parse({"phrases": [{"words": [
        {"text": "x", "offsetMilliseconds": 500, "durationMilliseconds": 250}]}]},
        "en-US", {})
    assert words[0][1] == pytest.approx(0.5)
    assert words[0][2] == pytest.approx(0.75)


def test_azure_raises_when_a_transcript_has_no_times():
    with pytest.raises(P.CloudASRError, match="no word timings"):
        P.azure_parse({"phrases": [],
                       "combinedPhrases": [{"text": "hello there"}]}, "en-US", {})


def test_azure_names_the_endpoint_it_is_missing(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    with pytest.raises(P.CloudASRError, match="AZURE_SPEECH_ENDPOINT"):
        P._azure_host({})


def test_azure_fast_sends_audio_in_the_request_and_pins_the_api_version(
        audio, tmp_path, monkeypatch):
    """One POST, the bytes in it, and the api-version from the recipe.

    api: fast is no longer the default but stays available for audio over the
    short-audio endpoint's 60 s cap.
    """
    monkeypatch.setenv("AZURE_SPEECH_API_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://r.cognitiveservices.azure.com")
    seen = {}

    def fake(url, **kw):
        seen["url"] = url
        seen["key"] = kw["headers"]["Ocp-Apim-Subscription-Key"]
        seen["body"] = kw["data"]
        return {"phrases": [{"confidence": 0.8, "words": [
            {"text": "hi", "offsetMilliseconds": 100,
             "durationMilliseconds": 300}]}]}

    monkeypatch.setattr(P, "request_json", fake)
    a = A.AzureSpeech("azure", {"cache_dir": str(tmp_path / "c"),
                                "api": "fast", "api_version": "2024-11-15"})
    a.load()
    out = a.align(audio)
    assert [w.label for w in out.words] == ["hi"]
    assert "api-version=2024-11-15" in seen["url"]
    assert "transcriptions:transcribe" in seen["url"]
    assert seen["key"] == "k"
    # The audio itself, not a URL to it.
    assert b'name="audio"' in seen["body"] and b"RIFF" in seen["body"]
    assert b'name="definition"' in seen["body"]


@pytest.mark.parametrize("given", [
    "https://r.cognitiveservices.azure.com",
    "https://r.cognitiveservices.azure.com/",
    "r.cognitiveservices.azure.com",
    "https://r.cognitiveservices.azure.com/sts/v1.0/issuetoken",
])
def test_azure_endpoint_survives_however_it_was_pasted(given):
    """Azure shows this value several ways and people paste it whole."""
    assert P._azure_host({"endpoint": given}) == "https://r.cognitiveservices.azure.com"


def test_azure_defaults_to_the_lexical_endpoint(audio, tmp_path, monkeypatch):
    """short_audio is the default, and it is a different HOST from the rest.

    The reference spells its numbers out and carries no punctuation. Only this
    endpoint matches that: fast transcription returns "twenty-one" as one
    token where the reference has two, which costs a boundary as well as a
    word.
    """
    monkeypatch.setenv("AZURE_STT_API_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westus")
    monkeypatch.delenv("AZURE_SPEECH_ENDPOINT", raising=False)
    seen = {}

    def fake(url, **kw):
        seen["url"] = url
        seen["ctype"] = kw["headers"]["Content-Type"]
        return {"RecognitionStatus": "Success", "NBest": [{
            "Confidence": 0.9, "Lexical": "twenty one",
            "Words": [{"Word": "twenty", "Offset": 7000000, "Duration": 2400000},
                      {"Word": "one", "Offset": 9400000, "Duration": 1200000}]}]}

    monkeypatch.setattr(P, "request_json", fake)
    a = A.AzureSpeech("azure", {"cache_dir": str(tmp_path / "c")})
    a.load()
    out = a.align(audio)
    assert [w.label for w in out.words] == ["twenty", "one"]
    assert out.words[0].start == pytest.approx(0.7)
    assert "stt.speech.microsoft.com" in seen["url"]
    assert "wordLevelTimestamps=true" in seen["url"]
    assert "format=detailed" in seen["url"]
    # The sample rate is read off the file, not assumed.
    assert "samplerate=16000" in seen["ctype"]


def test_azure_silence_is_an_answer_not_a_failure():
    """An utterance the service heard nothing in has no words, like any other
    provider's empty transcript. Only a status meaning we asked wrongly raises."""
    for st in ("NoMatch", "InitialSilenceTimeout", "BabbleTimeout"):
        words, meta = P.azure_parse({"RecognitionStatus": st, "NBest": []},
                                    "en-US", {})
        assert words == [] and meta["status"] == st


def test_azure_raises_when_word_timestamps_did_not_take():
    """A transcript with no Words means the flag was dropped, which would
    publish an empty row for every utterance."""
    with pytest.raises(P.CloudASRError, match="wordLevelTimestamps"):
        P.azure_parse({"RecognitionStatus": "Success",
                       "NBest": [{"Lexical": "hello there", "Words": []}]},
                      "en-US", {})


def test_azure_parser_dispatches_on_the_response_not_the_recipe():
    """A cached response must parse correctly whichever endpoint is current."""
    fast = {"phrases": [{"confidence": 0.5, "words": [
        {"text": "a", "offsetMilliseconds": 100, "durationMilliseconds": 100}]}]}
    short = {"RecognitionStatus": "Success", "NBest": [{"Confidence": 0.5,
             "Lexical": "a", "Words": [{"Word": "a", "Offset": 1000000,
                                        "Duration": 1000000}]}]}
    assert P.azure_parse(fast, "en-US", {})[0][0][0] == "a"
    assert P.azure_parse(short, "en-US", {})[0][0][0] == "a"


def test_azure_throttle_is_an_empty_401_and_must_be_retried(monkeypatch):
    """Azure answers a throttle with 401 and an empty body.

    A 401 is otherwise never retried, and rightly. Without this the first
    real attempt lost 146 of 192 utterances to throttling.
    """
    import urllib.error

    from fabench.timestamp_asrs.cloud import http as H
    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                         io.BytesIO(b""))
        class R:
            def read(self): return b"ok"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setattr(H.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    assert H.request("https://x.stt.speech.microsoft.com/", retry_empty=(401,),
                     backoff_s=0.0) == b"ok"
    assert len(calls) == 3


def test_a_401_that_names_the_problem_is_still_not_retried(monkeypatch):
    """A bad key must not burn five paid attempts."""
    import urllib.error

    from fabench.timestamp_asrs.cloud import http as H
    calls = []

    def bad(req, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(
            req.full_url, 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"code":"401","message":"Access denied due to '
                       b'invalid subscription key"}}'))

    monkeypatch.setattr(H.urllib.request, "urlopen", bad)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    with pytest.raises(H.CloudASRError):
        H.request("https://x.stt.speech.microsoft.com/", retry_empty=(401,),
                  backoff_s=0.0)
    assert len(calls) == 1


def test_an_exhausted_quota_stops_the_cell_instead_of_bleeding(audio, tmp_path,
                                                               monkeypatch):
    """A quota wall is not a hiccup: every remaining call fails identically.

    Azure's free tier allows 5 audio hours a month. A Buckeye cell hit that
    wall and then spent seventeen minutes failing 575 more calls one at a
    time. The batch now stops at the first such answer.
    """
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    calls = []

    def fake(url, **kw):
        calls.append(1)
        raise P.CloudASRError('HTTP 400: b\'"Quota exceeded. Cid: "\'')

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch, cache=False, concurrency=1)
    items = [BatchItem(item_id=f"i{i}", audio_path=audio, transcript=None,
                       mode="A") for i in range(25)]
    out = a.align_corpus(items)
    assert out == {}
    # One real attempt, then the wall; the rest never leave the machine.
    assert len(calls) <= 2, f"kept calling after the quota wall: {len(calls)}"


def test_a_transient_failure_still_only_omits(audio, tmp_path, monkeypatch):
    """The other half: an ordinary failure must not stop the cell."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "k")
    calls = []

    def fake(url, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise P.CloudASRError("HTTP 500: b'oops'")
        return {"results": {"channels": [{"alternatives": [
            {"words": [{"word": "a", "start": 0.0, "end": 0.1,
                        "confidence": 0.9}]}]}]}}

    monkeypatch.setattr(P, "request_json", fake)
    a = _make(A.Deepgram, tmp_path, monkeypatch, cache=False, concurrency=1)
    items = [BatchItem(item_id=f"i{i}", audio_path=audio, transcript=None,
                       mode="A") for i in range(5)]
    out = a.align_corpus(items)
    # Four of five survive the one 500. The call count is lower than the item
    # count because these five items are the same audio file and the response
    # is reused, which is the cache doing its job.
    assert len(out) == 4, "a transient failure must not stop the cell"


def test_azure_invalid_http_request_is_transient_and_retried(monkeypatch):
    """A 400 usually means we asked wrongly. This one does not.

    Four utterances of Buckeye test's 4,513 drew `HTTP 400 "Invalid HTTP
    request."`, clustered in one session, and all four returned 200 on a plain
    retry with identical bytes and headers.
    """
    import urllib.error

    from fabench.timestamp_asrs.cloud import http as H
    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) < 2:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {},
                                         io.BytesIO(b'"Invalid HTTP request."'))
        class R:
            def read(self): return b"ok"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setattr(H.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    assert H.request("https://x.stt.speech.microsoft.com/",
                     retry_body=("Invalid HTTP request",), backoff_s=0.0) == b"ok"
    assert len(calls) == 2
