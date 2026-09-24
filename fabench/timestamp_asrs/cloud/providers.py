# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""One CALL and one PARSE function per commercial ASR API.

They are separate on purpose. A call costs money and a parse does not, so the
cache stores the vendor's RAW response and the parse runs on every read. When a
reading of the response turns out to be wrong -- and these parsers were written
against documentation, so at least one of them is -- fixing it is free and
re-running is free. Cache the parsed output instead and every parser fix is a
second invoice for the same audio.

Each returns ``(words, meta)`` where a word is ``[label, start_s, end_s, conf]``
and conf is None where the vendor reports none. Times are seconds, always, so
the millisecond and nanosecond forms are converted here rather than downstream.

A NOTE ON FORMATTING, which matters more than it looks. Every one of these APIs
will, by default, hand back text meant for a human to read: "21" for "twenty
one", capitals, and punctuation. Against a gold transcript that spells its
numbers out, that is not a recognition error but it scores as one, and it
inflates WER for the vendor that formats hardest rather than the one that hears
worst. So every provider below asks for RAW words and the option is exposed in
the recipe rather than buried here. ElevenLabs has no such switch, which is
recorded in its recipe and is a real caveat on its WER.

The parallel caveat for TIMESTAMPS: these are the vendors' own word times,
which is the whole point of Track 2 one-step. Nothing here re-aligns them.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import time
import uuid
import wave
from urllib.parse import urlsplit as _urlsplit

from fabench.timestamp_asrs.cloud.awssig import sign_headers
from fabench.timestamp_asrs.cloud.http import (
    CloudASRError,
    _bump,
    _note,
    multipart,
    post_json,
    request,
    request_json,
)

Word = list           # [label, start_s, end_s, conf|None]

_CTYPE = {"wav": "audio/wav", "flac": "audio/flac", "mp3": "audio/mpeg",
          "ogg": "audio/ogg", "m4a": "audio/mp4", "webm": "audio/webm"}


def content_type(path: str) -> str:
    return _CTYPE.get(path.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def wav_info(blob: bytes) -> tuple[int, int, bytes] | None:
    """`(sample_rate, channels, raw PCM frames)` for a PCM WAV, else None.

    Google v1 wants the encoding and rate declared, and declaring them from the
    file rather than from a config constant is the difference between a row
    that is right and a row that is right until someone stages 8 kHz audio.
    """
    try:
        with wave.open(io.BytesIO(blob)) as w:
            if w.getsampwidth() != 2:
                return None
            return w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    except Exception:
        return None


def duration_s(blob: bytes) -> float | None:
    """Audio seconds, for the billing line. None when the header is unreadable."""
    try:
        with wave.open(io.BytesIO(blob)) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return None


# --------------------------------------------------------------------------
# Deepgram -- one POST, raw bytes in, words out. The simplest of the four.
# --------------------------------------------------------------------------
def deepgram_call(blob: bytes, path: str, model: str, opts: dict, key: str,
                  timeout_s: float, retries: int) -> dict:
    q = {
        "model": model,
        "language": opts.get("language", "en"),
        # Raw words, not display text. See the module docstring.
        "punctuate": _b(opts.get("punctuate", False)),
        "smart_format": _b(opts.get("smart_format", False)),
        "numerals": _b(opts.get("numerals", False)),
        "filler_words": _b(opts.get("filler_words", True)),
    }
    if opts.get("version"):
        q["version"] = str(opts["version"])
    url = "https://api.deepgram.com/v1/listen?" + _qs(q)
    _note("endpoint", url.split("?")[0])
    _note("api_version", "v1")
    return request_json(
        url, method="POST", data=blob,
        headers={"Authorization": f"Token {key}", "Content-Type": content_type(path)},
        timeout_s=timeout_s, retries=retries)


def deepgram_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    try:
        alts = r["results"]["channels"][0]["alternatives"]
    except (KeyError, IndexError, TypeError) as e:
        raise CloudASRError(f"deepgram: unexpected response {json.dumps(r)[:200]}") from e
    words: list[Word] = []
    if alts:
        for w in alts[0].get("words") or []:
            words.append([str(w.get("word") or ""), float(w["start"]), float(w["end"]),
                          _conf(w.get("confidence"))])
    meta = {"api_model": model}
    # Deepgram is the only one of the four that names the model version it
    # actually served -- "general-nova-3", "2025-07-31.0". Everyone else echoes
    # back the alias that was requested, which cannot detect the endpoint being
    # swapped underneath. Surfaced onto the record rather than left buried in
    # the cached body, because it is the strongest reproducibility evidence any
    # of these rows can carry.
    md = raw_meta = r.get("metadata") or {}
    for info in (md.get("model_info") or {}).values():
        if isinstance(info, dict) and info.get("version"):
            meta["served_model"] = str(info.get("name") or model)
            meta["served_version"] = str(info["version"])
            break
    if raw_meta.get("request_id"):
        meta["request_id"] = str(raw_meta["request_id"])
    return words, meta


# --------------------------------------------------------------------------
# AssemblyAI -- upload, submit, poll. Three calls, and the only async one.
# --------------------------------------------------------------------------
def assemblyai_call(blob: bytes, path: str, model: str, opts: dict, key: str,
                    timeout_s: float, retries: int) -> dict:
    base = "https://api.assemblyai.com/v2"
    _note("endpoint", f"{base}/transcript")
    _note("api_version", "v2")
    auth = {"authorization": key}
    up = request_json(f"{base}/upload", method="POST", data=blob,
                      headers={**auth, "Content-Type": "application/octet-stream"},
                      timeout_s=timeout_s, retries=retries)
    audio_url = up.get("upload_url")
    if not audio_url:
        raise CloudASRError(f"assemblyai: no upload_url in {json.dumps(up)[:200]}")

    body = {
        "audio_url": audio_url,
        "language_code": opts.get("language", "en_us"),
        "punctuate": bool(opts.get("punctuate", False)),
        "format_text": bool(opts.get("format_text", False)),
        "disfluencies": bool(opts.get("disfluencies", True)),
    }
    if model:
        # speech_modelS, a LIST. The singular form was deprecated and now hard
        # errors: "The speech_model parameter is deprecated. Use speech_models:
        # [universal-3-5-pro, universal-2]". Written as a list of one so a
        # recipe names exactly the model its row reports, rather than handing
        # the service a choice.
        body["speech_models"] = [model]
    job = post_json(f"{base}/transcript", body, auth,
                    timeout_s=timeout_s, retries=retries)
    tid = job.get("id")
    if not tid:
        raise CloudASRError(f"assemblyai: no transcript id in {json.dumps(job)[:200]}")

    # Poll. The deadline is the same timeout the other providers get for their
    # single blocking call, so a wedged job cannot hold a worker thread forever.
    interval = float(opts.get("poll_interval_s", 2.0))
    deadline = time.monotonic() + timeout_s
    # This provider is the only asynchronous one, and its wall time is partly
    # OUR poll interval rather than the vendor's speed. Recording the polling
    # separately keeps that out of the latency percentile by subtraction.
    _bump("upload_submit_s", time.monotonic() - (deadline - timeout_s))
    n_poll = 0
    while True:
        r = request_json(f"{base}/transcript/{tid}", headers=auth,
                         timeout_s=min(60.0, timeout_s), retries=retries)
        status = r.get("status")
        if status == "completed":
            break
        if status == "error":
            raise CloudASRError(f"assemblyai: {r.get('error')}")
        if time.monotonic() > deadline:
            raise CloudASRError(f"assemblyai: still {status} after {timeout_s:.0f}s")
        n_poll += 1
        _bump("poll_sleep_s", interval)
        _bump("n_polls")
        time.sleep(interval)

    return r


def assemblyai_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    words: list[Word] = []
    for w in r.get("words") or []:
        # start/end are MILLISECONDS here, unlike every other provider.
        words.append([str(w.get("text") or ""), float(w["start"]) / 1000.0,
                      float(w["end"]) / 1000.0, _conf(w.get("confidence"))])
    return words, {"api_model": r.get("speech_model") or model,
                   "transcript_id": r.get("id")}


# --------------------------------------------------------------------------
# ElevenLabs Scribe -- multipart, and the response interleaves non-words.
# --------------------------------------------------------------------------
def elevenlabs_call(blob: bytes, path: str, model: str, opts: dict, key: str,
                    timeout_s: float, retries: int) -> dict:
    fields = {
        "model_id": model,
        "timestamps_granularity": opts.get("timestamps_granularity", "word"),
        "diarize": "true" if opts.get("diarize") else "false",
        "tag_audio_events": "true" if opts.get("tag_audio_events") else "false",
    }
    if opts.get("language"):
        fields["language_code"] = str(opts["language"])
    ctype, body = multipart(fields, {"file": (path.rsplit("/", 1)[-1],
                                              content_type(path), blob)})
    _note("endpoint", "https://api.elevenlabs.io/v1/speech-to-text")
    _note("api_version", "v1")
    return request_json("https://api.elevenlabs.io/v1/speech-to-text",
                        method="POST", data=body,
                        headers={"xi-api-key": key, "Content-Type": ctype},
                        timeout_s=timeout_s, retries=retries)


def elevenlabs_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    words: list[Word] = []
    for w in r.get("words") or []:
        # The list carries "spacing" and "audio_event" entries beside the words.
        # Keeping them would invent boundaries at every space in the utterance.
        if (w.get("type") or "word") != "word":
            continue
        lp = w.get("logprob")
        conf = None
        if isinstance(lp, (int, float)):
            try:
                conf = float(math.exp(float(lp)))
            except (OverflowError, ValueError):
                conf = None
        words.append([str(w.get("text") or ""), float(w["start"]), float(w["end"]),
                      _conf(conf)])
    return words, {"api_model": model}


# --------------------------------------------------------------------------
# Google Cloud Speech-to-Text -- v1 (API key works) or v2 (bearer + project).
# --------------------------------------------------------------------------
def google_stt_call(blob: bytes, path: str, model: str, opts: dict, key: str,
                    timeout_s: float, retries: int) -> dict:
    project = str(opts.get("project_id") or "")
    if project:
        return _google_v2(blob, path, model, opts, key, timeout_s, retries, project)
    return _google_v1(blob, path, model, opts, key, timeout_s, retries)


def google_stt_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    """v1 and v2 name the offsets differently, so read whichever is present.

    The version is not stored in the response, and re-deriving it from opts
    would tie a cached body to the options it was fetched with. The field names
    are unambiguous on their own, so the body tells us.
    """
    ver = "v2" if opts.get("project_id") else "v1"
    s_key, e_key = ("startOffset", "endOffset") if ver == "v2" else ("startTime", "endTime")
    words: list[Word] = []
    for res in r.get("results") or []:
        for alt in (res.get("alternatives") or [])[:1]:
            for w in alt.get("words") or []:
                # Tolerate either spelling regardless of which endpoint was
                # asked, so a cached body always reads back.
                st = w.get(s_key, w.get("startTime", w.get("startOffset")))
                en = w.get(e_key, w.get("endTime", w.get("endOffset")))
                words.append([str(w.get("word") or ""), _gtime(st), _gtime(en),
                              _conf(w.get("confidence"))])
    _no_timings(words, r, f"google {ver} model={model or 'default'}")
    billed = (r.get("metadata") or {}).get("totalBilledDuration")
    meta = {"api_model": model or "default", "api_version": ver}
    if billed:
        meta["billed"] = billed
    return words, meta


def _google_v1(blob, path, model, opts, key, timeout_s, retries):
    cfg = {
        "languageCode": opts.get("language", "en-US"),
        "enableWordTimeOffsets": True,
        "enableWordConfidence": True,
        "enableAutomaticPunctuation": bool(opts.get("punctuate", False)),
    }
    if model:
        cfg["model"] = model
    info = wav_info(blob)
    if info:
        rate, channels, pcm = info
        # Send the PCM, not the RIFF container: with a header in the payload and
        # LINEAR16 declared, the header bytes are decoded as samples and the
        # first ~20 ms of every utterance is a click.
        cfg |= {"encoding": "LINEAR16", "sampleRateHertz": rate,
                "audioChannelCount": channels}
        payload_audio = pcm
    else:
        payload_audio = blob          # let Google sniff a container it knows
    body = {"config": cfg,
            "audio": {"content": base64.b64encode(payload_audio).decode()}}
    url = "https://speech.googleapis.com/v1/speech:recognize"
    _note("endpoint", url)
    _note("api_version", "v1")
    headers = {}
    if key.startswith("Bearer "):
        headers["Authorization"] = key
    else:
        url += "?key=" + key
    return post_json(url, body, headers, timeout_s=timeout_s, retries=retries)


def _google_v2(blob, path, model, opts, key, timeout_s, retries, project):
    loc = str(opts.get("location", "global"))
    host = "speech.googleapis.com" if loc == "global" else f"{loc}-speech.googleapis.com"
    recognizer = opts.get("recognizer", "_")
    url = (f"https://{host}/v2/projects/{project}/locations/{loc}"
           f"/recognizers/{recognizer}:recognize")
    _note("endpoint", url)
    _note("api_version", "v2")
    cfg = {
        "autoDecodingConfig": {},
        "languageCodes": [opts.get("language", "en-US")],
        "features": {"enableWordTimeOffsets": True, "enableWordConfidence": True,
                     "enableAutomaticPunctuation": bool(opts.get("punctuate", False))},
    }
    if model:
        cfg["model"] = model
    body = {"config": cfg, "content": base64.b64encode(blob).decode()}
    if not key.startswith("Bearer "):
        raise CloudASRError(
            "google v2 needs an OAuth bearer token, not an API key. Set "
            "GOOGLE_STT_ACCESS_TOKEN, or leave params.project_id unset to use v1.")
    return post_json(url, body, {"Authorization": key},
                     timeout_s=timeout_s, retries=retries)


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Speechmatics -- asynchronous like AssemblyAI, but the job is created with a
# multipart body carrying a JSON config beside the audio, and the transcript is
# a THIRD request rather than a field on the status response.
# --------------------------------------------------------------------------
def speechmatics_call(blob: bytes, path: str, model: str, opts: dict, key: str,
                      timeout_s: float, retries: int) -> dict:
    base = "https://asr.api.speechmatics.com/v2"
    auth = {"Authorization": f"Bearer {key}"}
    _note("endpoint", f"{base}/jobs")
    _note("api_version", "v2")

    cfg = {
        "type": "transcription",
        "transcription_config": {
            "language": str(opts.get("language", "en")),
            # standard | enhanced. Their own docs call enhanced the accurate
            # one; it is the default here for the same reason every other
            # recipe asks for the vendor's best rather than its cheapest.
            "operating_point": str(model or "enhanced"),
            # Raw words, as with every other provider. See the module docstring.
            "enable_entities": bool(opts.get("enable_entities", False)),
        },
    }
    ctype, body = multipart({"config": json.dumps(cfg)},
                            {"data_file": (path.rsplit("/", 1)[-1],
                                           content_type(path), blob)})
    created = request_json(f"{base}/jobs", method="POST", data=body,
                           headers={**auth, "Content-Type": ctype},
                           timeout_s=timeout_s, retries=retries)
    jid = created.get("id")
    if not jid:
        raise CloudASRError(f"speechmatics: no job id in {json.dumps(created)[:200]}")

    interval = float(opts.get("poll_interval_s", 1.0))
    deadline = time.monotonic() + timeout_s
    while True:
        st = request_json(f"{base}/jobs/{jid}", headers=auth,
                          timeout_s=min(60.0, timeout_s), retries=retries)
        status = ((st.get("job") or {}).get("status") or "").lower()
        if status == "done":
            break
        if status in ("rejected", "expired", "deleted"):
            raise CloudASRError(f"speechmatics: job {status} -- "
                                f"{json.dumps(st)[:200]}")
        if time.monotonic() > deadline:
            raise CloudASRError(f"speechmatics: still {status!r} after {timeout_s:.0f}s")
        _bump("poll_sleep_s", interval)
        _bump("n_polls")
        time.sleep(interval)

    # The transcript is its own request. json-v2 is the only format carrying
    # per-word times; the plain text format drops them entirely.
    return request_json(f"{base}/jobs/{jid}/transcript?format=json-v2",
                        headers=auth, timeout_s=min(120.0, timeout_s),
                        retries=retries)


def speechmatics_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    words: list[Word] = []
    for item in r.get("results") or []:
        # The stream interleaves punctuation with words, as ElevenLabs
        # interleaves spacing. Keeping it would invent a boundary per comma.
        if (item.get("type") or "word") != "word":
            continue
        alts = item.get("alternatives") or []
        if not alts:
            continue
        words.append([str(alts[0].get("content") or ""),
                      float(item.get("start_time") or 0.0),
                      float(item.get("end_time") or 0.0),
                      _conf(alts[0].get("confidence"))])
    meta = {"api_model": model or "enhanced"}
    md = r.get("metadata") or {}
    # Speechmatics echoes the config that ran, which most vendors do not.
    tc = md.get("transcription_config") or {}
    if tc.get("operating_point"):
        meta["served_model"] = str(tc["operating_point"])
    # AND IT NAMES ITS BUILD, which only Deepgram was thought to do. The field
    # is orchestrator_version and it carries a date, a commit and a semantic
    # version: 2026.09.07+1f5eba77f2+16.0.0, identical across 3,000 sampled
    # responses of the sweep, so the service did not change underneath it.
    # That is the second strongest provenance any row here has and it was
    # sitting unread in the cached responses.
    if md.get("orchestrator_version"):
        meta["served_version"] = str(md["orchestrator_version"])
    if md.get("type"):
        meta["job_type"] = str(md["type"])
    return words, meta



# --------------------------------------------------------------------------
# IBM Watson Speech to Text -- synchronous, but unlike the others the word
# times must be ASKED FOR (timestamps=true) and come back as bare triples
# rather than objects.
# --------------------------------------------------------------------------
def ibm_call(blob: bytes, path: str, model: str, opts: dict, key: str,
             timeout_s: float, retries: int) -> dict:
    # Recipe first, then the environment. The instance URL names an account's
    # own service, so like a key it belongs in .fabench.env rather than in a
    # tracked recipe that anyone can read.
    base = str(opts.get("service_url") or os.environ.get("IBM_STT_URL", "")).rstrip("/")
    if not base:
        raise CloudASRError(
            "ibm: params.service_url is required and is region-specific, e.g. "
            "https://api.us-south.speech-to-text.watson.cloud.ibm.com . An IAM "
            "key authenticates against the regional endpoint directly; the "
            "older .../instances/<guid> form names a specific instance. Set "
            "IBM_STT_URL in .fabench.env, or params.service_url in the recipe.")
    q = {
        "model": model or "en-US_Multimedia",
        # Without this Watson returns a transcript and NO times at all, which
        # is the one provider here where the timestamps are opt-in.
        "timestamps": "true",
        "word_confidence": "true",
        # Raw words, as everywhere else. See the module docstring.
        "smart_formatting": _b(opts.get("smart_format", False)),
        "profanity_filter": _b(opts.get("profanity_filter", False)),
    }
    url = f"{base}/v1/recognize?" + _qs(q)
    _note("endpoint", f"{base}/v1/recognize")
    _note("api_version", "v1")
    # IAM key as HTTP Basic, username literally "apikey". Simpler than the
    # token exchange and it does not expire mid-sweep, which is the failure
    # that cost Google 3,619 utterances.
    auth = base64.b64encode(f"apikey:{key}".encode()).decode()
    return request_json(url, method="POST", data=blob,
                        headers={"Authorization": f"Basic {auth}",
                                 "Content-Type": content_type(path)},
                        timeout_s=timeout_s, retries=retries)


def ibm_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    words: list[Word] = []
    for res in r.get("results") or []:
        for alt in (res.get("alternatives") or [])[:1]:
            # [[word, start, end], ...] -- a bare triple, not an object.
            stamps = alt.get("timestamps") or []
            # [[word, confidence], ...], same order when present.
            confs = {i: c for i, (_w, c) in enumerate(alt.get("word_confidence") or [])}
            for i, t in enumerate(stamps):
                if not isinstance(t, (list, tuple)) or len(t) < 3:
                    continue
                words.append([str(t[0] or ""), float(t[1]), float(t[2]),
                              _conf(confs.get(i))])
    _no_timings(words, r, f"ibm model={model or 'en-US_Multimedia'}")
    return words, {"api_model": model or "en-US_Multimedia"}


# --------------------------------------------------------------------------
# Amazon Transcribe -- the only provider here that will not take the audio.
#
# Every other endpoint accepts the bytes in the request. Transcribe batch reads
# from S3 and nothing else, so one utterance is four signed calls: PUT the
# object, start the job, poll it, then GET the transcript from the presigned
# URL the job hands back. The object is deleted afterwards unless the recipe
# says otherwise.
#
# WHY BATCH AND NOT STREAMING. Transcribe streaming takes the bytes directly
# and would avoid S3 entirely, but it speaks HTTP/2 or WebSocket framed in
# Amazon's own event-stream encoding, and the standard library has neither a
# HTTP/2 client nor a WebSocket one. Batch is plain signed HTTPS and JSON.
#
# WHAT THIS COSTS IN LATENCY. A batch job carries tens of seconds of fixed
# scheduling overhead regardless of how short the clip is, so this row's
# latency figures measure AWS's job queue and not its recognizer. That is a
# real property of using the service this way and it is reported as measured,
# but it is not comparable to the synchronous endpoints.
# --------------------------------------------------------------------------
def _aws_creds(opts: dict, secret: str) -> tuple[str, str, str | None, str]:
    """`(access_key_id, secret_access_key, session_token, region)`.

    The registry resolves only the secret, because that is the shape the other
    providers have. The rest comes from the environment under the names the
    AWS tooling already uses, so a machine that can run the CLI can run this.
    """
    access = (opts.get("access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID") or "")
    token = (os.environ.get("AWS_SESSION_TOKEN") or None)
    region = (opts.get("region") or os.environ.get("AWS_REGION")
              or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
    if not access:
        raise CloudASRError(
            "aws: AWS_ACCESS_KEY_ID is not set. The secret alone does not "
            "sign a request, so set both it and AWS_SECRET_ACCESS_KEY.")
    return access, secret, token, str(region)


def _aws_bucket(opts: dict) -> str:
    b = opts.get("s3_bucket") or os.environ.get("AWS_S3_BUCKET") or ""
    if not b:
        raise CloudASRError(
            "aws: no S3 bucket. Transcribe batch reads the audio from S3 and "
            "will not take it in the request, so set AWS_S3_BUCKET or put "
            "s3_bucket in the recipe. The bucket must be in the same region "
            "as the Transcribe endpoint.")
    return str(b)


#: AWS says "slow down" with a 400 and an exception name, so the status alone
#: cannot distinguish a rate limit from a bad request. These are the names, and
#: they are the only 400s worth a retry. Anything else 400 is our bug and
#: retrying it would just bill four more times for the same mistake.
AWS_RETRY_BODY = ("ThrottlingException", "ThrottledException",
                  "TooManyRequestsException", "LimitExceededException",
                  "RequestLimitExceeded", "SlowDown", "RequestTimeout",
                  "ProvisionedThroughputExceededException")


def _aws_signed(method, url, *, region, service, creds, payload=b"",
                headers=None, timeout_s=300.0, retries=5) -> bytes:
    access, secret, token, _ = creds

    # SIGNED PER ATTEMPT, NOT ONCE. The signature carries the minute it was
    # made; Transcribe rejects one over five minutes old and S3 one over
    # fifteen. A retry therefore has to be signed again or it cannot succeed,
    # and with eight retries behind a 900 s timeout the backoff alone reaches
    # those limits. The first sweep lost four items to exactly this, reported
    # as InvalidSignatureException and RequestTimeTooSkewed, which read like
    # clock trouble on this machine and were nothing of the kind.
    def _sign() -> dict:
        return sign_headers(method=method, url=url, region=region,
                            service=service, access_key=access,
                            secret_key=secret, session_token=token,
                            payload=payload, headers=headers)

    try:
        return request(url, method=method, data=payload or None, headers=_sign,
                       timeout_s=timeout_s, retries=retries,
                       retry_body=AWS_RETRY_BODY)
    except CloudASRError as e:
        # THE COMMONEST SETUP MISTAKE, and S3 reports it as a redirect rather
        # than as a region error. Say what it actually means, once, here.
        # AWS blames the KEY for what is an account problem. The wording is
        # "The AWS Access Key Id needs a subscription for the service", which
        # reads as a bad or unprivileged key and sends you to IAM. It is
        # neither. The signature was accepted and the account is simply not
        # activated for this service yet, which is the normal state of a fresh
        # account until billing verification finishes. S3 and STS answer
        # throughout, so the credential looks fine everywhere else.
        if "SubscriptionRequiredException" in str(e):
            raise CloudASRError(
                f"aws: this account is not subscribed to Amazon {service}. "
                f"The signature was accepted, so the key is correct. A new "
                f"account stays in this state until signup is fully activated, "
                f"usually payment method and phone verification. Check the "
                f"billing page, not IAM. Original: {e}") from e
        if service == "s3" and ("PermanentRedirect" in str(e)
                                or "HTTP 301" in str(e)):
            raise CloudASRError(
                f"aws: the S3 bucket is not in {region}. Transcribe and its "
                f"staging bucket must be in the SAME region. Either make a "
                f"bucket in {region} or set region to the bucket's. "
                f"Original: {e}") from e
        raise


def _aws_target(target: str, body: dict, *, region, creds, timeout_s, retries) -> dict:
    """One Transcribe API call. AWS JSON 1.1, the operation in a header."""
    url = f"https://transcribe.{region}.amazonaws.com/"
    raw = _aws_signed("POST", url, region=region, service="transcribe",
                      creds=creds, payload=json.dumps(body).encode(),
                      headers={"Content-Type": "application/x-amz-json-1.1",
                               "X-Amz-Target": f"Transcribe.{target}"},
                      timeout_s=timeout_s, retries=retries)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise CloudASRError(f"aws {target}: non-JSON response: {raw[:200]!r}") from e


_AWS_FORMAT = {"wav": "wav", "flac": "flac", "mp3": "mp3", "mp4": "mp4",
               "m4a": "m4a", "ogg": "ogg", "webm": "webm", "amr": "amr"}


def aws_call(blob: bytes, path: str, model: str, opts: dict, key: str,
             timeout_s: float, retries: int) -> dict:
    creds = _aws_creds(opts, key)
    region = creds[3]
    bucket = _aws_bucket(opts)
    ext = path.rsplit(".", 1)[-1].lower()
    fmt = _AWS_FORMAT.get(ext)
    if not fmt:
        raise CloudASRError(f"aws: Transcribe does not read .{ext} files")

    # The object key is the audio's own digest, so a retry after a failed job
    # re-uses the upload rather than paying for a second one, and two identical
    # utterances in a corpus share one object.
    digest = hashlib.sha256(blob).hexdigest()
    prefix = str(opts.get("s3_prefix") or "fabench").strip("/")
    s3_key = f"{prefix}/{digest}.{ext}"
    s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    _note("endpoint", f"https://transcribe.{region}.amazonaws.com/")
    _note("api_version", "2017-10-26")
    _note("s3_uri", f"s3://{bucket}/{s3_key}")

    t_up = time.monotonic()
    _aws_signed("PUT", s3_url, region=region, service="s3", creds=creds,
                payload=blob, headers={"Content-Type": content_type(path)},
                timeout_s=timeout_s, retries=retries)
    _bump("upload_submit_s", time.monotonic() - t_up)

    # EVERYTHING BELOW RUNS UNDER A finally THAT DELETES THE OBJECT. The
    # cleanup used to sit on the success path, so any failure between the
    # upload and the transcript left the audio in the bucket forever. A sweep
    # retries, and a bad day would have leaked thousands of objects that
    # nothing afterwards knew to look for. Observed for real: one failed smoke
    # test against an unsubscribed account left its object behind.
    try:
        return _aws_job(opts, creds, region, bucket, s3_key, digest, fmt,
                        timeout_s, retries)
    finally:
        if opts.get("keep_s3_object") is not True:
            try:
                _aws_signed("DELETE", s3_url, region=region, service="s3",
                            creds=creds, timeout_s=60.0, retries=1)
            except Exception:
                # The transcript, if there is one, is already in hand and paid
                # for. A failed cleanup is a storage bill, not a lost
                # utterance, so it must never replace the real exception.
                _bump("s3_delete_failed")


def _aws_job(opts, creds, region, bucket, s3_key, digest, fmt,
             timeout_s, retries) -> dict:
    """Start the job, poll it, fetch the transcript. The caller owns the S3
    object's lifetime, so nothing here cleans up and every path may raise."""
    job = f"fabench-{digest[:16]}-{uuid.uuid4().hex[:12]}"
    body = {
        "TranscriptionJobName": job,
        "LanguageCode": opts.get("language", "en-US"),
        "Media": {"MediaFileUri": f"s3://{bucket}/{s3_key}"},
        "MediaFormat": fmt,
    }
    # Stated rather than defaulted. Both are already off, but a row that says
    # what it asked for is worth more than one that relies on a default the
    # vendor can change.
    settings: dict = {"ShowSpeakerLabels": False, "ShowAlternatives": False}
    if opts.get("vocabulary_name"):
        settings["VocabularyName"] = str(opts["vocabulary_name"])
    if opts.get("language_model_name"):
        body["ModelSettings"] = {"LanguageModelName": str(opts["language_model_name"])}
    # NO MediaSampleRateHertz. Transcribe detects the rate itself, and a
    # declared rate that disagrees with the file fails the job outright. There
    # is nothing to gain by declaring it and a whole cell to lose.
    body["Settings"] = settings
    _aws_target("StartTranscriptionJob", body, region=region, creds=creds,
                timeout_s=timeout_s, retries=retries)

    interval = float(opts.get("poll_interval_s", 2.0))
    deadline = time.monotonic() + timeout_s
    uri = ""
    while True:
        got = _aws_target("GetTranscriptionJob", {"TranscriptionJobName": job},
                          region=region, creds=creds,
                          timeout_s=min(60.0, timeout_s), retries=retries)
        tj = got.get("TranscriptionJob") or {}
        status = tj.get("TranscriptionJobStatus")
        if status == "COMPLETED":
            uri = str((tj.get("Transcript") or {}).get("TranscriptFileUri") or "")
            break
        if status == "FAILED":
            raise CloudASRError(f"aws: job failed, {tj.get('FailureReason')}")
        if time.monotonic() > deadline:
            raise CloudASRError(f"aws: still {status} after {timeout_s:.0f}s")
        _bump("poll_sleep_s", interval)
        _bump("n_polls")
        time.sleep(interval)

    if not uri:
        raise CloudASRError("aws: job completed with no TranscriptFileUri")
    # The service-managed output bucket hands back a PRESIGNED url, so this one
    # GET carries its own credentials in the query string and must not be
    # signed again. Signing it would invalidate the presigned signature.
    raw = request(uri, timeout_s=min(120.0, timeout_s), retries=retries)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise CloudASRError(f"aws: non-JSON transcript: {raw[:200]!r}") from e


def aws_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    words: list[Word] = []
    res = r.get("results") or {}
    for it in res.get("items") or []:
        # PUNCTUATION ITEMS CARRY NO TIMES. They sit in the same list as the
        # words and have no start_time at all, so keeping them would either
        # crash on the missing key or invent a zero-length boundary after every
        # clause. Same trap as the ElevenLabs spacing entries.
        if (it.get("type") or "pronunciation") != "pronunciation":
            continue
        alts = it.get("alternatives") or []
        if not alts:
            continue
        try:
            start = float(it["start_time"])
            end = float(it["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        words.append([str(alts[0].get("content") or ""), start, end,
                      _conf(alts[0].get("confidence"))])
    if not words:
        text = ""
        for t in res.get("transcripts") or []:
            text += str(t.get("transcript") or "")
        if text.strip():
            raise CloudASRError(
                f"aws: got a transcript but no word timings. Transcript was: "
                f"{text.strip()[:80]!r}")
    return words, {"api_model": model or "en-US", "job_name": r.get("jobName")}


# --------------------------------------------------------------------------
# Azure AI Speech, FAST TRANSCRIPTION. One synchronous multipart POST, audio in
# the request, word times in the response by default.
#
# WHY THIS API AND NOT THE OTHER TWO. Azure sells three ways to get a
# transcript. Batch transcription reads from Blob Storage and would repeat the
# AWS staging problem. The Speech SDK is a dependency tree this repo cannot
# take. Fast transcription is plain multipart HTTPS, takes the bytes directly,
# and is the only one of the three that behaves like every other row here.
#
# THE PUNCTUATION CAVEAT, and it is different in kind from the others. Deepgram
# and AssemblyAI have a switch for raw words. AWS and ElevenLabs return
# punctuation as its own entry, which the parser drops. Azure does neither: it
# glues the mark onto the word, so the last word of a clause arrives as
# "afternoon." and the scorer, which lowercases but does not strip, would count
# every one of them as a substitution. So the mark is stripped here. That is a
# parser decision rather than a request option because Azure offers no option,
# and it is safe to make here precisely because the cache holds the RAW
# response, so revisiting it costs nothing.
# --------------------------------------------------------------------------

#: Stripped from the ends of a word. Internal marks stay, so "don't" and
#: "well-known" survive while "afternoon." and "(laughs)" lose their edges.
_AZURE_EDGE = ".,!?;:\"'`()[]{}<>‘’“”–—…"


def _azure_host(opts: dict) -> str:
    """The resource host. Azure issues one per Speech resource."""
    ep = (opts.get("endpoint") or os.environ.get("AZURE_SPEECH_ENDPOINT") or "").strip()
    if ep:
        # WHATEVER SHAPE THE PORTAL GAVE THEM. Azure shows this value several
        # ways and people paste it whole: with a trailing slash, with no
        # scheme, and sometimes with a service path still attached such as
        # /sts/v1.0/issuetoken. Only the scheme and host are ours to keep, and
        # reducing to them here turns three confusing 404s into none.
        if "://" not in ep:
            ep = "https://" + ep
        parts = _urlsplit(ep)
        if not parts.netloc:
            raise CloudASRError(f"azure: cannot read a host out of {ep!r}")
        return f"{parts.scheme or 'https'}://{parts.netloc}"
    region = (opts.get("region") or os.environ.get("AZURE_SPEECH_REGION") or "").strip()
    if region:
        # The regional gateway answers for a resource in that region and is the
        # documented alternative to the per-resource host.
        return f"https://{region}.api.cognitive.microsoft.com"
    raise CloudASRError(
        "azure: no endpoint. Set AZURE_SPEECH_ENDPOINT to the resource host "
        "from the portal, for example "
        "https://<resource>.cognitiveservices.azure.com, or set "
        "AZURE_SPEECH_REGION to its region.")


#: Azure's short-audio endpoint lives on a different host from everything else
#: in the Speech resource, and the portal's "Endpoint" is the other one.
def _azure_stt_host(opts: dict) -> str:
    region = (opts.get("region") or os.environ.get("AZURE_SPEECH_REGION") or "").strip()
    if not region:
        # Recover it from the resource host when only that was given:
        # https://westus.api.cognitive.microsoft.com -> westus.
        host = _azure_host(opts)
        first = host.split("//", 1)[-1].split(".", 1)[0]
        if first and "cognitiveservices" not in first:
            region = first
    if not region:
        raise CloudASRError(
            "azure: the short-audio endpoint is per REGION, and the region "
            "could not be read from AZURE_SPEECH_REGION or the endpoint host. "
            "Set AZURE_SPEECH_REGION, or use api: fast.")
    return f"https://{region}.stt.speech.microsoft.com"


def azure_call(blob: bytes, path: str, model: str, opts: dict, key: str,
               timeout_s: float, retries: int) -> dict:
    if (opts.get("api") or "short_audio") == "short_audio":
        return _azure_short_audio(blob, path, model, opts, key, timeout_s, retries)
    return _azure_fast(blob, path, model, opts, key, timeout_s, retries)


def _azure_short_audio(blob: bytes, path: str, model: str, opts: dict, key: str,
                       timeout_s: float, retries: int) -> dict:
    """The v1 recognition endpoint, detailed, with word timestamps asked for.

    WHY THIS AND NOT FAST TRANSCRIPTION, which was wired first. This one
    returns the LEXICAL form, and the benchmark's reference spells its numbers
    out and carries no punctuation. Measured on the same audio:

        gold                and then i've been married ... for twenty one years
        short-audio Words   and then i've been married ... for twenty one years
        fast transcription  And then I've been married ... for twenty-one years

    Fast transcription applies inverse text normalisation with no switch, so
    it returns 5 and 7.30 where the reference says five and seven thirty, and
    it hyphenates twenty-one into ONE token where the reference has two. The
    second costs more than the word error: one token is one fewer boundary, so
    it moves recall as well. Azure offers no way to turn that off, and this
    endpoint simply does not do it.

    The price is a 60 s cap, and the longest utterance in this benchmark is
    23.6 s.
    """
    host = _azure_stt_host(opts)
    lang = opts.get("language") or model or "en-US"
    q = {
        "language": lang,
        # Detailed, or the response carries no NBest and so no words at all.
        "format": "detailed",
        "wordLevelTimestamps": "true",
        "profanity": str(opts.get("profanity") or "raw").lower(),
    }
    url = f"{host}/speech/recognition/conversation/cognitiveservices/v1?" + _qs(q)
    info = wav_info(blob)
    rate = info[0] if info else 16000
    _note("endpoint", url.split("?")[0])
    _note("api_version", "v1 short-audio")
    return request_json(
        url, method="POST", data=blob,
        headers={"Ocp-Apim-Subscription-Key": key, "Accept": "application/json",
                 "Content-Type": f"audio/wav; codecs=audio/pcm; samplerate={rate}"},
        timeout_s=timeout_s, retries=retries,
        # A throttle here is 401 with an empty body; a bad key is 401 with a
        # JSON message. Only the first is worth another try.
        retry_empty=(401,),
        # "Invalid HTTP request" is a 400, and a 400 usually means we asked
        # wrongly. Not this one. Four utterances of the 4,513 in Buckeye test
        # drew it, clustered in one session and one stretch of the run, and
        # all four returned 200 on a plain retry with the same bytes and the
        # same headers. It is a transient fault at the service, so it is
        # retried and the four are no longer lost.
        retry_body=("Invalid HTTP request",))


def _azure_fast(blob: bytes, path: str, model: str, opts: dict, key: str,
                timeout_s: float, retries: int) -> dict:
    host = _azure_host(opts)
    # PINNED, never floating. Azure dates its api-version and the response
    # shape has changed across them, so the recipe names one and the row
    # records which answered.
    ver = str(opts.get("api_version") or "2024-11-15")
    url = f"{host}/speechtotext/transcriptions:transcribe?api-version={ver}"

    definition = {
        "locales": [opts.get("language") or model or "en-US"],
        # Raw words as far as Azure allows. There is no punctuation switch on
        # this API, only this one.
        "profanityFilterMode": opts.get("profanity_filter_mode") or "None",
    }
    if opts.get("diarize"):
        definition["diarization"] = {"enabled": True,
                                     "maxSpeakers": int(opts.get("max_speakers", 2))}
    ctype, body = multipart(
        {"definition": json.dumps(definition)},
        {"audio": (path.rsplit("/", 1)[-1], content_type(path), blob)})
    _note("endpoint", url.split("?")[0])
    _note("api_version", ver)
    return request_json(url, method="POST", data=body,
                        headers={"Ocp-Apim-Subscription-Key": key,
                                 "Content-Type": ctype},
                        timeout_s=timeout_s, retries=retries)


def azure_parse(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    # Two response shapes behind one provider. The short-audio endpoint
    # answers with RecognitionStatus and NBest; fast transcription with
    # phrases. Keyed on what came back rather than on the recipe, so a cached
    # response parses correctly whichever setting is current.
    if "NBest" in r or "RecognitionStatus" in r:
        return _azure_parse_short(r, model, opts)
    words: list[Word] = []
    for ph in r.get("phrases") or []:
        conf = ph.get("confidence")
        for w in ph.get("words") or []:
            try:
                off = float(w["offsetMilliseconds"]) / 1000.0
                dur = float(w.get("durationMilliseconds") or 0) / 1000.0
            except (KeyError, TypeError, ValueError):
                continue
            label = str(w.get("text") or "").strip(_AZURE_EDGE)
            if not label:
                continue          # a bare punctuation token, nothing to time
            # Azure reports offset and DURATION, not offset and end. Every
            # other provider here reports an end, so the conversion happens
            # once, at the edge.
            words.append([label, off, off + dur, _conf(conf)])
    if not words:
        text = " ".join(str(c.get("text") or "")
                        for c in (r.get("combinedPhrases") or []))
        if text.strip():
            raise CloudASRError(
                f"azure: got a transcript but no word timings. Transcript was: "
                f"{text.strip()[:80]!r}")
    meta = {"api_model": model or "en-US"}
    if r.get("durationMilliseconds"):
        meta["reported_duration_ms"] = r["durationMilliseconds"]
    return words, meta



#: 100-nanosecond ticks to seconds. Azure's short-audio endpoint is the only
#: one here that uses them.
_AZURE_TICK = 1e-7


def _azure_parse_short(r: dict, model: str, opts: dict) -> tuple[list[Word], dict]:
    status = str(r.get("RecognitionStatus") or "")
    nbest = r.get("NBest") or []
    if not nbest:
        # Silence and no-match are real answers, not failures: an utterance the
        # service heard nothing in has no words, exactly as an empty transcript
        # from any other provider. Only a status that means we asked wrongly
        # should raise.
        if status in ("NoMatch", "InitialSilenceTimeout", "BabbleTimeout",
                      "EndOfDictation", ""):
            return [], {"api_model": model or "en-US", "status": status}
        raise CloudASRError(f"azure short-audio: status {status!r}")
    alt = nbest[0]
    # Utterance-level confidence. The per-word Confidence field on this
    # endpoint reads 0.0 for every word, so carrying it would put a false
    # zero on the calibration columns; the utterance score is the honest one.
    conf = _conf(alt.get("Confidence"))
    words: list[Word] = []
    for w in alt.get("Words") or []:
        try:
            off = float(w["Offset"]) * _AZURE_TICK
            dur = float(w.get("Duration") or 0) * _AZURE_TICK
        except (KeyError, TypeError, ValueError):
            continue
        # Already lexical: lower case, no punctuation, numbers spelled out.
        # Stripped anyway, because a lexical form is a promise rather than a
        # guarantee and a stray mark would score as a substitution.
        label = str(w.get("Word") or "").strip(_AZURE_EDGE)
        if not label:
            continue
        words.append([label, off, off + dur, conf])
    if not words and str(alt.get("Lexical") or "").strip():
        raise CloudASRError(
            f"azure short-audio: got a transcript but no word timings, so "
            f"wordLevelTimestamps did not take. Transcript was: "
            f"{str(alt['Lexical']).strip()[:80]!r}")
    return words, {"api_model": model or "en-US", "status": status,
                   "lexical": str(alt.get("Lexical") or "")[:400]}

def _no_timings(words, resp, who: str) -> None:
    """Raise when a response carries a transcript but no word times.

    THIS IS A SPEND GUARD, not a parser check. A model that recognises fine and
    silently ignores enableWordTimeOffsets -- Google's original Chirp did
    exactly that, and model support for the flag still varies by model and
    region -- returns a flawless transcript and no boundaries. Scored, that is
    an empty row; unguarded, it is an empty row 47,000 paid requests later. An
    utterance that is genuinely silent has no transcript either, so the two
    cases are distinguishable and only the expensive one raises.
    """
    if words:
        return
    text = ""
    for res in resp.get("results") or []:
        for alt in (res.get("alternatives") or [])[:1]:
            text += str(alt.get("transcript") or "")
    if text.strip():
        raise CloudASRError(
            f"{who}: got a transcript but no word timings -- this model is "
            f"ignoring enableWordTimeOffsets, so every row would be empty. "
            f"Pick a model that supports word offsets (v1 latest_long does) "
            f"before running a sweep. Transcript was: {text.strip()[:80]!r}")


def _gtime(v) -> float:
    """Google's several time spellings -> seconds. "1.100s", or {seconds,nanos}."""
    if v is None:
        return 0.0
    if isinstance(v, dict):
        return float(v.get("seconds") or 0) + float(v.get("nanos") or 0) / 1e9
    s = str(v)
    return float(s[:-1]) if s.endswith("s") else float(s)


def _conf(v) -> float | None:
    """A confidence the calibration metrics can use, or None.

    Zero is returned as None on purpose: several of these APIs send 0.0 to mean
    "not scored", and a column of zeros would read as a confident wrong answer.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0.0 else None


def _b(v) -> str:
    return "true" if v else "false"


def _qs(d: dict) -> str:
    from urllib.parse import urlencode
    return urlencode({k: v for k, v in d.items() if v not in (None, "")})


def host_for(provider: str, opts: dict) -> str:
    """The host a provider's calls go to, for the connection-baseline probe.

    Google's is regional and depends on the recipe, which is exactly why this
    is derived rather than tabulated.
    """
    if provider == "ibm":
        # Instance-specific, so it is derived from the recipe rather than fixed.
        u = str(opts.get("service_url") or "")
        return u.split("://")[-1].split("/")[0] if u else ""
    if provider == "google_stt":
        loc = str(opts.get("location") or "")
        if opts.get("project_id") and loc and loc != "global":
            return f"{loc}-speech.googleapis.com"
        return "speech.googleapis.com"
    return {"deepgram": "api.deepgram.com",
            "assemblyai": "api.assemblyai.com",
            "elevenlabs": "api.elevenlabs.io",
            "speechmatics": "asr.api.speechmatics.com"}.get(provider, "")


#: provider -> (call, parse, default model, env var names in priority order).
#: call costs money and parse does not, which is why they are separate: the
#: cache holds what call returned and parse runs on every read.
PROVIDERS = {
    # <VENDOR>_STT_API_KEY is the preferred spelling throughout: several of
    # these vendors issue one key across speech-to-text, text-to-speech and
    # more, so a name that says which product it was minted for is worth
    # preferring over the generic one. The generic names still work.
    "deepgram":   (deepgram_call,   deepgram_parse,   "nova-3",
                   ("DEEPGRAM_STT_API_KEY", "DEEPGRAM_API_KEY")),
    "assemblyai": (assemblyai_call, assemblyai_parse, "universal-3-5-pro",
                   ("ASSEMBLYAI_STT_API_KEY", "ASSEMBLYAI_API_KEY")),
    # ELEVENLABS_STT_API_KEY first: ElevenLabs issues one key for speech-to-text
    # and text-to-speech alike, and a name that says which product it was minted
    # for is the one worth preferring. XI_API_KEY is their own header spelling.
    "elevenlabs": (elevenlabs_call, elevenlabs_parse, "scribe_v2",
                   ("ELEVENLABS_STT_API_KEY", "ELEVENLABS_API_KEY", "XI_API_KEY")),
    "google_stt": (google_stt_call, google_stt_parse, "latest_long",
                   ("GOOGLE_STT_ACCESS_TOKEN", "GOOGLE_STT_API_KEY")),
    "speechmatics": (speechmatics_call, speechmatics_parse, "enhanced",
                     ("SPEECHMATICS_STT_API_KEY", "SPEECHMATICS_API_KEY")),
    "ibm": (ibm_call, ibm_parse, "en-US_Multimedia",
            ("IBM_STT_API_KEY", "IBM_API_KEY")),
    # AWS is the odd one out: the resolved "key" is the SECRET access key, and
    # the access key id, the session token and the region are read from the
    # standard AWS environment names inside the call. One env var cannot carry
    # a two-part credential.
    "aws": (aws_call, aws_parse, "en-US",
            ("AWS_SECRET_ACCESS_KEY", "AWS_STT_SECRET_ACCESS_KEY")),
    # Azure issues TWO interchangeable keys per resource, labelled KEY 1 and
    # KEY 2 in the portal so one can be rotated while the other serves. Both
    # spellings are accepted and the first one set wins, which matches how the
    # second ElevenLabs key was carried. <VENDOR>_STT_API_KEY is this repo's
    # own convention and comes first.
    "azure": (azure_call, azure_parse, "en-US",
              ("AZURE_STT_API_KEY", "AZURE_STT_API_KEY1", "AZURE_STT_API_KEY2",
               "AZURE_SPEECH_STT_API_KEY", "AZURE_SPEECH_API_KEY",
               "AZURE_SPEECH_KEY")),
}
