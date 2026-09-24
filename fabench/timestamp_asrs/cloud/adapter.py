# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Commercial timestamped ASR APIs as Track 2, one-step systems.

Four vendors, one adapter. They differ only in how the bytes go out and how the
words come back (fabench.timestamp_asrs.cloud.providers); everything that makes
them usable in a sweep is the same and lives here.

WHAT IS DIFFERENT ABOUT A PAID ROW, and what this adapter does about it.

1. A call costs money and a rescore must not re-bill. Every response is cached
   under the tool's own directory, keyed by the SHA-256 of the audio bytes plus
   the model and every request option that can change the answer. Re-running a
   cell, re-running after a crash, or re-running to fix a scoring bug all hit
   the cache and cost nothing. Change the model or an option and the key
   changes, so the cache can never serve a stale configuration -- the failure
   mode a cache keyed on the file path alone would have.

2. A key is a secret and this repo is public. Keys come from the environment
   only, named in each recipe, and `.fabench.env` is gitignored. Nothing here
   reads a key out of a config file even if one is put there.

3. Rate limits are real and per-vendor. Concurrency is a recipe parameter,
   defaulting low, and 429 is retried with backoff rather than dropped
   (fabench.timestamp_asrs.cloud.http).

4. A sweep should be able to say what it spent. Each batch prints the calls
   made, the cache hits and the audio minutes actually sent.

WHAT THIS DOES NOT DO. It does not re-align, re-time or re-format anything. The
word boundaries scored are the vendor's own, which is the definition of Track 2
one-step. A cascade on one of these transcripts is a separate recipe, built the
same way as the Qwen3-ASR ones.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from itertools import pairwise
from pathlib import Path

from fabench.aligners.base import AlignerAdapter, AlignerError, AlignerOutput
from fabench.schema import Interval
from fabench.timestamp_asrs.cloud import http as H
from fabench.timestamp_asrs.cloud import providers as P
from fabench.timestamp_asrs.cloud.http import CloudASRError

#: Failures that mean the ACCOUNT is out, not that the network hiccuped. These
#: do not recover by waiting or retrying, and every remaining call in the cell
#: will fail identically, so the batch stops instead of bleeding.
#:
#: This is not hypothetical tidiness. Azure's free tier allows 5 audio hours a
#: month, and a Buckeye cell walked into that wall and then spent seventeen
#: minutes failing 575 more calls one at a time, reporting only
#: `HTTP 400: "Quota exceeded. Cid: "` at the end.
_EXHAUSTED = (
    ("quota exceeded", "the account's quota is exhausted"),
    ("quota_exceeded", "the account's quota is exhausted"),
    ("insufficient_quota", "the account's quota is exhausted"),
    ("out of credits", "the account is out of credits"),
    ("subscriptionrequiredexception", "the account is not subscribed to this service"),
)


def _exhausted(e: Exception) -> str | None:
    """A reason to stop the whole cell, or None to carry on omitting."""
    m = str(e).lower()
    for needle, why in _EXHAUSTED:
        if needle in m:
            return (f"{why}. Every remaining call would fail the same way, so "
                    f"the cell stopped rather than spending the round trips. "
                    f"Raise the tier or top up, then re-run: the responses "
                    f"already paid for are cached and will not be billed "
                    f"again. Original: {e}")
    return None


def _is_auth_error(e: Exception) -> bool:
    """A refused credential, as opposed to any other 4xx."""
    m = str(e)
    return "HTTP 401" in m or "UNAUTHENTICATED" in m or "HTTP 403" in m


#: Request options that reach the provider AND the cache key. Anything a vendor
#: reads that can change the ANSWER must be listed, or a changed option would
#: be served a stale response.
_OPT_KEYS = (
    "language", "punctuate", "smart_format", "numerals", "filler_words",
    "format_text", "disfluencies", "version", "timestamps_granularity",
    "diarize", "tag_audio_events", "project_id", "location", "recognizer",
    "enable_entities", "profanity_filter",
    # AWS. `region` sits here rather than below because Amazon rolls models out
    # by region, so the same request to two regions is not guaranteed the same
    # answer and a cached response should not be replayed across them.
    "region", "vocabulary_name", "language_model_name",
    # Azure. api_version is pinned in the recipe and Azure has changed the
    # response shape across versions, so it belongs to the answer.
    "api_version", "profanity_filter_mode", "max_speakers",
    # `api` picks which Azure endpoint answers, and the two return different
    # TEXT for the same audio -- lexical against inverse-normalised -- so it
    # belongs to the answer and to the cache key.
    "api", "profanity",
)

#: Options the provider reads that CANNOT change the answer, so they reach the
#: call but stay out of the cache key. Kept apart because putting them in
#: _OPT_KEYS would invalidate a whole corpus of cached responses the day
#: someone tuned a poll interval.
#: `service_url` routes the call without changing the answer: the same audio
#: and model return the same transcript from any instance of the service, so a
#: new instance must not invalidate a cache full of responses.
#: The AWS S3 staging options are routing too. Which bucket the audio passed
#: through on its way to Transcribe cannot change what Transcribe heard, and
#: `access_key_id` is a credential rather than a setting, so none of them may
#: touch the cache key.
#: `endpoint` is Azure's per-resource host and routes exactly as IBM's
#: service_url does. Two resources in one region return the same transcript,
#: so moving resource must not invalidate a cache; `region`, which CAN change
#: the answer because Azure rolls models out by region, is in _OPT_KEYS above.
_BEHAVIOUR_KEYS = ("poll_interval_s", "service_url", "s3_bucket", "s3_prefix",
                   "keep_s3_object", "access_key_id", "endpoint")


class CloudASR(AlignerAdapter):
    """Audio -> a vendor's own words and word times. Subclasses set `provider`."""

    source = "orthographic"
    granularity = ("word",)
    emits_confidence = True
    #: Take the runner's concurrent align_corpus path: these calls are network
    #: I/O, so threads give real concurrency while the GIL is released.
    batch = True
    #: The defining Track 2 property. align() is handed the reference transcript
    #: by the runner's signature and ignores it.
    ignores_transcript = True

    provider: str = ""
    default_model: str = ""
    #: Native timestamp resolution in seconds, where it has been MEASURED, not
    #: read off a spec sheet. For an endpoint there is no architecture to
    #: reason from, so the only honest source is the offsets it returns.
    #: fabench.timestamp_asrs.base documents why it is recorded: it caps what
    #: any tolerance below it can show.
    frame_s: float | None = None

    def requires_bearer(self) -> bool:
        """Does this configuration need an OAuth token rather than an API key?

        Asked before a credential is picked, not after. Google v2 takes only a
        bearer token, so an API key sitting in the environment is not a weaker
        credential for it, it is the wrong kind -- and preferring it, then
        failing on the call, told the user to set something they had already
        set.
        """
        return False

    # ---- lifecycle --------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        if self.provider not in P.PROVIDERS:
            raise AlignerError(f"{self.name}: unknown provider {self.provider!r}; "
                               f"known: {sorted(P.PROVIDERS)}")
        call, parse, default_model, env_names = P.PROVIDERS[self.provider]
        self._call, self._parse = call, parse
        self.model = str(self.params.get("model") or self.default_model or default_model)
        self._env_names = env_names
        self.key = self._resolve_key(env_names)
        # A gcloud access token lives about an hour. load() is idempotent, so
        # without a refresh the key is minted once and a multi-hour sweep runs
        # past its expiry -- which is exactly what happened: 142 of Buckeye
        # test's 4513 items died on HTTP 401 near the end of a 22-minute cell,
        # and a 401 is deliberately not retried so that a bad key cannot burn
        # five paid attempts. Refresh well inside the lifetime instead.
        self._key_at = time.monotonic()
        self._key_refreshable = bool(self.params.get("access_token_cmd")) and \
            self.key.startswith("Bearer ")
        self.token_ttl_s = float(self.params.get("token_ttl_s", 2400))
        self.opts = {k: self.params[k] for k in _OPT_KEYS if k in self.params}
        self._call_opts = dict(self.opts) | {
            k: self.params[k] for k in _BEHAVIOUR_KEYS if k in self.params}
        self.timeout_s = float(self.params.get("timeout_s") or 300)
        self.retries = int(self.params.get("retries", 5))
        self.concurrency = max(1, int(self.params.get("concurrency", 4)))
        self.max_calls = self.params.get("max_calls")
        self.max_calls = int(self.max_calls) if self.max_calls else None
        # Requests per minute, client side. CONCURRENCY DOES NOT BOUND THIS.
        # A cache hit returns at memory speed, so a mostly-cached re-run cycles
        # the pool far faster than a cold one and the few real calls bunch up:
        # Chirp 2 lost 2,020 of 4,513 items to "Recognize requests per minute
        # per region" on a restart where 285 of 2,493 were cached, having
        # completed the same cell cold. Backoff alone cannot fix that -- eight
        # retries buy 183 s against a limit that stays saturated -- so the rate
        # is capped here instead of apologised for afterwards.
        rpm = self.params.get("max_rpm")
        self.max_rpm = int(rpm) if rpm else None
        self._call_times: list[float] = []
        self.cache_dir = self._resolve_cache_dir()
        self._lock = threading.Lock()
        self._setup_s = None          # measured lazily, once per cell
        self._n_call = self._n_hit = 0
        self._billed_s = 0.0
        self._loaded = True

    def _resolve_cache_dir(self) -> Path | None:
        """Beside the recipe that owns it, as an ABSOLUTE path.

        Two bugs this replaces. The old default was a RELATIVE
        "evals/timestamp_asrs/<name>/cache", so where a sweep put its cache
        depended on the working directory it happened to be launched from. And
        it was built from the tool NAME, which for a nested recipe is not its
        directory: google_stt_chirp2 lives at google_stt/exps/chirp2/, so the
        cache landed in a stray top-level folder that was neither a recipe nor
        beside the cells it belongs to.

        tool_index is the same lookup find_hyp uses to locate a nested recipe's
        output, so the cache now sits where every other artefact of that cell
        already does.
        """
        cache = self.params.get("cache_dir")
        if cache:
            return Path(cache).expanduser().resolve()
        if not self.params.get("cache", True):
            return None
        # tool_dir already resolves a nested recipe by its declared name, which
        # is the same lookup the runner uses to place hyp.jsonl.
        from fabench.paths import tool_dir
        root = Path(__file__).resolve().parents[3]
        try:
            base = tool_dir(root, self.name, "timestamp_asrs")
        except Exception:
            base = root / "evals" / "timestamp_asrs" / self.name
        return (root / base).resolve() / "cache"

    def _resolve_key(self, env_names: tuple[str, ...]) -> str:
        """Environment only. A key in a tracked config is a key in the history."""
        bearer_only = self.requires_bearer()
        skipped = []
        for n in (self.params.get("key_env"), *env_names):
            if not n or not os.environ.get(n):
                continue
            # A bearer token and an API key go to different places. The
            # ACCESS_TOKEN spelling says bearer; everything else is a key.
            is_bearer = n.endswith("_ACCESS_TOKEN")
            if bearer_only and not is_bearer:
                skipped.append(n)       # wrong KIND, so keep looking
                continue
            v = os.environ[n].strip()
            return f"Bearer {v}" if is_bearer else v
        cmd = self.params.get("access_token_cmd")
        why = ""
        if cmd:
            # For Google, `gcloud auth print-access-token`. A convenience for a
            # machine that already holds a login, so a missing or unauthenticated
            # gcloud is reported as part of "no credential" rather than as its
            # own failure -- the fix in both cases is to set a variable or log in.
            try:
                out = subprocess.run(cmd, shell=True, capture_output=True,
                                     text=True, timeout=60, check=True)
                tok = out.stdout.strip()
                if tok:
                    return f"Bearer {tok}"
                why = f"; `{cmd}` printed nothing"
            except Exception as e:
                why = f"; `{cmd}` failed ({type(e).__name__})"
        if skipped:
            why += (f"; ignored {', '.join(skipped)} because this recipe sets "
                    f"project_id and that endpoint takes only a bearer token")
        wanted = ([n for n in env_names if n.endswith("_ACCESS_TOKEN")]
                  if bearer_only else list(env_names))
        raise AlignerError(
            f"{self.name}: no credential. Set one of {', '.join(wanted)} in "
            f".fabench.env (gitignored) or the environment{why}."
            + self.credential_hint())

    def credential_hint(self) -> str:
        """Extra wording for a provider whose credential is not one string."""
        return ""

    def _throttle(self) -> None:
        """Block until another request would stay inside max_rpm.

        A trailing-window counter rather than a fixed-rate sleep: a sweep that
        has been idle should not be punished for it, and a burst that fits
        inside the window should not be slowed.
        """
        if not self.max_rpm:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                self._call_times = [t for t in self._call_times if now - t < 60.0]
                if len(self._call_times) < self.max_rpm:
                    self._call_times.append(now)
                    return
                wait = 60.0 - (now - self._call_times[0]) + 0.01
            time.sleep(max(0.01, min(wait, 60.0)))

    def _fresh_key(self, force: bool = False) -> str:
        """The credential, re-minted when it is stale or has just been refused.

        Age alone is not enough, and assuming it was cost 3,619 of one cell's
        4,456 items. Each cell is its own process, so the age clock restarts
        every ~20 minutes and a 2400 s TTL never fires -- while `gcloud auth
        print-access-token` returns its CACHED token, which may already be
        fifty minutes into a sixty-minute life. The age check is kept as a
        cheap first line; `force` is what actually saves a cell, driven by a
        401 coming back from the wire.

        Under the lock so that eight worker threads refused at once mint one
        token between them rather than eight.
        """
        if not self._key_refreshable:
            return self.key
        with self._lock:
            stale = time.monotonic() - self._key_at >= self.token_ttl_s
            if force and time.monotonic() - self._key_at < 5:
                return self.key   # another thread just refreshed; use theirs
            if force or stale:
                try:
                    self.key = self._resolve_key(self._env_names)
                    self._key_at = time.monotonic()
                except AlignerError as e:
                    # Keep the old one; it may still have minutes left, and
                    # failing here would abandon a cell that could finish.
                    print(f"  [{self.name}] token refresh failed, keeping the "
                          f"current one: {e}", file=sys.stderr)
        return self.key

    # ---- one utterance ----------------------------------------------------
    def align(self, audio_path, transcript=None, phone_seq=None, mode="A") -> AlignerOutput:
        self.load()
        try:
            blob = Path(audio_path).read_bytes()
        except OSError as e:
            raise AlignerError(f"{self.name}: cannot read {audio_path}: {e}") from e

        path_cache = self._cache_path(blob)
        if path_cache is not None and path_cache.exists():
            try:
                rec = json.loads(path_cache.read_text())
            except (OSError, json.JSONDecodeError):
                rec = None    # unreadable entry is a miss, not a failure
            if rec is not None:
                with self._lock:
                    self._n_hit += 1
                if "raw" in rec:
                    # Re-parse every time. A corrected reading of the response
                    # then costs nothing, which is the whole reason the raw
                    # body is what gets stored.
                    words, meta = self._parse(rec["raw"], self.model, self._call_opts)
                    # Replay the timing of the call that FETCHED this response,
                    # never the disk read. Not doing so lost the measurement
                    # entirely: a re-run of a cached cell rewrote hyp.jsonl with
                    # records carrying no latency, so a cell measured at 400
                    # requests came back reporting one. The timing belongs to
                    # the response, `fetched_at` says when it was taken, and
                    # `cached` says the row was not re-measured.
                    replay = {k: rec[k] for k in ("latency_s", "audio_s", "setup_s",
                                                  "retries", "backoff_s", "n_polls")
                              if rec.get(k) is not None}
                    return self._to_output(words, {**meta, **replay, "cached": True,
                                                   "fetched_at": rec.get("fetched_at")})
                # Pre-raw entry. Kept readable so an early cache is not wasted.
                return self._to_output(rec.get("words") or [],
                                       {**(rec.get("meta") or {}), "cached": True,
                                        "legacy_cache": True})

        if self.max_calls is not None:
            with self._lock:
                if self._n_call >= self.max_calls:
                    raise AlignerError(
                        f"{self.name}: max_calls={self.max_calls} reached. Raise it "
                        f"or unset it in the recipe once the cost is understood.")
        self._throttle()
        H.reset_stats()
        t0 = time.monotonic()
        try:
            raw = self._call(blob, str(audio_path), self.model, self._call_opts,
                             self._fresh_key(), self.timeout_s, self.retries)
        except CloudASRError as e:
            # A 401 is not retried by the HTTP layer, and rightly so: a wrong
            # key must not burn five paid attempts. An EXPIRED token is the one
            # case where the same status is worth exactly one more try, with a
            # newly minted credential.
            if not (self._key_refreshable and _is_auth_error(e)):
                raise
            print(f"  [{self.name}] credential refused, re-minting and retrying "
                  f"once", file=sys.stderr)
            raw = self._call(blob, str(audio_path), self.model, self._call_opts,
                             self._fresh_key(force=True), self.timeout_s,
                             self.retries)
        latency_s = time.monotonic() - t0
        words, meta = self._parse(raw, self.model, self._call_opts)
        dur = P.duration_s(blob)
        # Wall time for the whole vendor interaction, with the parts that are
        # OURS recorded beside it: retries and their backoff, and for the one
        # asynchronous provider the polling. A percentile can then be read
        # without wondering whether a slow call was a slow vendor or our client.
        st = H.stats()
        meta = {**meta, "latency_s": latency_s, "audio_s": dur,
                **{k: v for k, v in st.items() if v}}
        if self._setup_s is not None:
            # The DNS + TCP + TLS floor for this endpoint from this machine.
            # Carried on every record so a fixed-cost figure can be read net of
            # the network, which is not a property of the service.
            meta["setup_s"] = self._setup_s
        with self._lock:
            self._n_call += 1
            self._billed_s += dur or 0.0

        if path_cache is not None:
            try:
                path_cache.parent.mkdir(parents=True, exist_ok=True)
                tmp = path_cache.with_suffix(".tmp")
                # The VENDOR'S OWN response, not our reading of it.
                entry = {
                    "raw": raw, "provider": self.provider, "model": self.model,
                    "opts": self.opts, "audio": str(audio_path),
                    "fetched_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
                    # The timing of THIS call, stored with the response it
                    # produced, so a later cache hit can report it instead of
                    # losing it. See the replay in the hit path above.
                    "latency_s": latency_s, "audio_s": dur,
                    "setup_s": self._setup_s,
                }
                entry.update({k: v for k, v in st.items() if v})
                tmp.write_text(json.dumps(entry))
                tmp.replace(path_cache)           # atomic: a killed run leaves no half file
            except OSError:
                pass
        return self._to_output(words, {**meta, "cached": False})

    # ---- a whole cell -----------------------------------------------------
    def align_corpus(self, items) -> dict:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.load()
        # Once per cell, before any paid call: what the network costs before
        # the service does anything. urllib does not pool connections, so this
        # is paid per request, not once.
        if self._setup_s is None:
            self._setup_s = H.probe_connect(P.host_for(self.provider, self._call_opts))
        out: dict = {}
        n_fail, first = 0, ""

        halt: list[str] = []          # first fatal reason, if any

        def _one(it):
            if halt:
                # The account is out, not the network. Every remaining call
                # would fail the same way, so stop paying the round trip.
                raise AlignerError(f"{self.name}: halted, {halt[0]}")
            return it.item_id, self.align(it.audio_path, it.transcript, mode=it.mode)

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = [ex.submit(_one, it) for it in items]
            for fut in as_completed(futures):
                try:
                    item_id, res = fut.result()
                except Exception as e:            # contract: omit, never abort
                    n_fail += 1
                    if not first:
                        first = f"{type(e).__name__}: {e}"
                    why = _exhausted(e)
                    if why and not halt:
                        halt.append(why)
                    continue
                out[item_id] = res
        if halt:
            print(f"  [{self.name}] STOPPED: {halt[0]}", file=sys.stderr)
        # What this cell cost, every time, because a paid sweep that does not
        # say what it spent is a sweep nobody can budget for.
        setup = f", {self._setup_s * 1000:.0f} ms connect floor" if self._setup_s else ""
        print(f"  [{self.name}] {len(items)} items: {self._n_call} api calls, "
              f"{self._n_hit} cached, {self._billed_s / 60.0:.1f} audio min sent{setup}",
              file=sys.stderr)
        if n_fail:
            print(f"  [{self.name}] {n_fail}/{len(items)} items failed "
                  f"(omitted); first: {first}", file=sys.stderr)
        return out

    # ---- helpers ----------------------------------------------------------
    def _cache_path(self, blob: bytes) -> Path | None:
        if self.cache_dir is None:
            return None
        h = hashlib.sha256()
        for part in (self.provider, self.model, json.dumps(self.opts, sort_keys=True)):
            h.update(part.encode()); h.update(b"\0")
        h.update(blob)
        d = h.hexdigest()
        # Two-level fan-out: a Buckeye sweep is ~45k entries and one flat
        # directory of those is slow to stat on every lookup.
        return self.cache_dir / d[:2] / f"{d}.json"

    def _to_output(self, words, meta) -> AlignerOutput:
        """Vendor words -> Intervals, COUNTING what has to be repaired.

        Two repairs happen here and both destroy evidence: `max(end, start)`
        hides a reversed interval and the sort hides one emitted out of order.
        Neither is recoverable from hyp.jsonl afterwards, so the counts go in
        the record. Everything else about a cloud row can be re-derived from
        the cached raw body at any time; these two cannot, which is the only
        reason they are counted here rather than added later.
        """
        ivs = []
        n_reversed = n_zero = 0
        for w in words:
            # Same normalisation the subprocess workers get in
            # SubprocessAligner.align_corpus, so these rows are comparable with
            # CrisperWhisper's and Parakeet's rather than differing by casing.
            label = str(w[0] or "").strip().strip(".,!?").lower()
            if not label:
                continue
            start, end = float(w[1]), float(w[2])
            conf = float(w[3]) if len(w) > 3 and w[3] is not None else None
            if end < start - 1e-9:
                n_reversed += 1
            elif abs(end - start) < 1e-9:
                n_zero += 1
            ivs.append(Interval(label, start, max(end, start), conf))
        n_disordered = sum(1 for a, b in pairwise(ivs) if b.start < a.start - 1e-9)
        ivs.sort(key=lambda iv: (iv.start, iv.end))
        for k, v in (("n_reversed", n_reversed), ("n_zero_len", n_zero),
                     ("n_disordered", n_disordered)):
            if v:
                meta = {**meta, k: v}
        return AlignerOutput(words=ivs, phones=[], meta=meta)


class Deepgram(CloudASR):
    """Deepgram Nova. One POST, words with per-word confidence."""
    provider = "deepgram"
    default_model = "nova-3"


class AssemblyAI(CloudASR):
    """AssemblyAI Universal. Upload, submit, poll."""
    provider = "assemblyai"
    default_model = "universal-3-5-pro"


class ElevenLabs(CloudASR):
    """ElevenLabs Scribe. Multipart; the word list interleaves spacing entries."""
    provider = "elevenlabs"
    default_model = "scribe_v2"
    #: MEASURED: every offset v1 and v2 return lands on a 20 ms grid.
    frame_s = 0.020


class IBMWatson(CloudASR):
    """IBM Watson Speech to Text v1. Synchronous; word times are opt-in."""
    provider = "ibm"
    default_model = "en-US"
    #: MEASURED: en-US and en-US_Multimedia both land on a 20 ms grid; the
    #: deprecated en-US_BroadbandModel is 10 ms.
    frame_s = 0.020


class Speechmatics(CloudASR):
    """Speechmatics batch v2. Asynchronous, and the transcript is a third call."""
    provider = "speechmatics"
    default_model = "enhanced"
    #: MEASURED 2026-09-17: every offset lands on a 40 ms grid, on both
    #: operating points. Speechmatics exposes no named checkpoint, only
    #: standard and enhanced, so there is nothing finer to select.
    frame_s = 0.040


class AWSTranscribe(CloudASR):
    """Amazon Transcribe batch. Audio goes through S3 and the job is polled."""
    provider = "aws"
    default_model = "en-US"
    #: UNMEASURED until the first sweep. Amazon publishes no frame step and
    #: the item times come back as decimal strings, so whether they land on a
    #: grid is a question for the hypotheses rather than the documentation.
    #: Left unset on purpose. Setting a wrong one here would be worse than
    #: setting none, and evals/measure_grid.py reads it off the output.
    frame_s = None

    def credential_hint(self) -> str:
        # The generic message names one variable, and AWS needs four things.
        # A user who sets only the one it names gets a signature error next,
        # which says nothing about what is actually missing.
        return ("\n  AWS needs four, not one:\n"
                "    AWS_ACCESS_KEY_ID        the other half of the signature\n"
                "    AWS_SECRET_ACCESS_KEY    this one\n"
                "    AWS_REGION               e.g. us-east-1\n"
                "    AWS_S3_BUCKET            Transcribe batch reads from S3 "
                "and will not take bytes in the request.\n"
                "                             Same region as the endpoint.\n"
                "  AWS_SESSION_TOKEN too if the credentials are temporary.")


class AzureSpeech(CloudASR):
    """Azure AI Speech, fast transcription. One multipart POST, word times by
    default, and the only provider here that glues punctuation to the word."""
    provider = "azure"
    default_model = "en-US"
    #: MEASURED 2026-09-17 over 12 TIMIT utterances, 107 words: every offset
    #: lands on a 10 ms grid, on the short-audio endpoint and on both fast
    #: transcription api-versions alike. That is
    #: the finest step of any commercial endpoint here -- IBM and ElevenLabs
    #: are 20 ms, Google and Speechmatics 40, Deepgram 80 -- so unlike those
    #: this row carries no arithmetic ceiling at the 20 ms tolerance.
    frame_s = 0.010

    def credential_hint(self) -> str:
        # The key alone does not say WHERE to send it. Azure issues a host per
        # Speech resource, and without it the next failure is a DNS error that
        # says nothing about Azure.
        return ("\n  Azure needs the endpoint too:\n"
                "    AZURE_SPEECH_ENDPOINT    the resource host from the "
                "portal's Keys and Endpoint page,\n"
                "                             "
                "https://<resource>.cognitiveservices.azure.com\n"
                "  or AZURE_SPEECH_REGION for the regional gateway instead.")


class GoogleSTT(CloudASR):
    """Google Cloud Speech-to-Text. v1 with an API key, v2 with a bearer token."""
    provider = "google_stt"
    default_model = "latest_long"

    #: MEASURED 2026-09-16: every offset chirp_2 and chirp_3 return lands on a
    #: 40 ms grid, and it is Google's floor -- the v2 long/short models and
    #: every v1 model are 100 ms. Quantisation alone therefore puts about a
    #: 10 ms floor under this row's word MAE, against 16.9 ms for Olign's whole
    #: clean error. See evals/timestamp_asrs/google_stt/exps/chirp2/config.yaml.
    frame_s = 0.040

    def requires_bearer(self) -> bool:
        # project_id is what selects v2, and v2 rejects API keys outright.
        return bool(self.params.get("project_id"))
