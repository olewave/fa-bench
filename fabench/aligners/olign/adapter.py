# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""olign — Olewave's speech-assessment service, as a FA-Bench aligner.

olign returns a pronunciation *scorecard* (per-word and per-phone scores) that
also carries per-word/per-phone ``begin``/``end`` timings, which is what makes it
scoreable as a forced aligner at all. See this package's ``README.md`` for the
wire contract.

It targets **Olign 0.9**, the version in the published results and the paper, through
Olign's v0.9 API, over REST: ``POST <base>?ref_text=...`` with the raw audio as
the body. The server transcodes any container/codec itself, so FA-Bench hands
it the corpus WAV untouched. Per-item, stateless.

Mode A (from text) only: olign aligns against a reference transcript, like BFA.

Phone labels are lowercase, stress-less CMU/ARPABET (e.g. ``"w"``, ``"ah"``)
-> canonicalize via the existing ``"arpabet"`` normalization source.

``begin``/``end``/``dur`` are milliseconds.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from fabench.aligners.base import (
    AlignerAdapter,
    AlignerError,
    AlignerOutput,
    ModeUnsupported,
    clamp_intervals,
)
from fabench.schema import Interval

#: Public endpoint. The version is in the PATH -- a client selects the contract
#: by choosing the URL, there is no version header to negotiate. This adapter
#: speaks the synchronous contract (raw audio body, query parameters), which is
#: `v0.9`; olign's `/olign/v1` is a different, job-based API (multipart upload,
#: then poll) that this adapter does not use.
#:
#: Override with params.base_url, or with the OLIGN_BASE_URL environment
#: variable.
_DEFAULT_BASE = os.environ.get(
    "OLIGN_BASE_URL", "https://api.olewave.com/olign/v0.9"
)

#: The endpoint answers Python-urllib's default User-Agent with HTTP 403, so the
#: adapter names itself.
_USER_AGENT = "fa-bench-olign/1"


def _auth_headers() -> dict[str, str]:
    """The service-token headers for the hosted endpoint, from
    CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET (put them in .fabench.env,
    which is untracked: they are credentials, never config). Read at call
    time so the CLI's env-file load is always seen. Unset, no auth headers are
    sent."""
    cid = os.environ.get("CF_ACCESS_CLIENT_ID")
    secret = os.environ.get("CF_ACCESS_CLIENT_SECRET")
    return {"CF-Access-Client-Id": cid, "CF-Access-Client-Secret": secret} if cid and secret else {}
_DEFAULT_CORE_TYPE = "en.phone.align"
_DEFAULT_TIMEOUT_S = 60.0

#: begin/end/dur are milliseconds.
_MS_PER_S = 1000.0


def build_query(
    transcript: str, *, core_type: str = _DEFAULT_CORE_TYPE, accent: int = 2, rank: int = 100,
    edge_snap: int | None = None, refine_boundaries: int | None = None,
) -> str:
    """The REST query string (doc §2). Everything except the audio goes here.

    ``edge_snap`` / ``refine_boundaries`` are server-side toggles (0/1) that
    move word begin and end times only. Omit either (None) for the server
    default. Scores are byte-identical across settings.
    """
    q: dict = {
        "ref_text": transcript,
        "core_type": core_type,
        "rank": rank,
        "accent": accent,
        "show_phone_details": 1,
    }
    if edge_snap is not None:
        q["edge_snap"] = int(edge_snap)
    if refine_boundaries is not None:
        q["refine_boundaries"] = int(refine_boundaries)
    return urllib.parse.urlencode(q)


def parse_olign_result(payload: dict) -> tuple[list[Interval], list[Interval]]:
    """olign scorecard JSON -> FA-Bench word/phone :class:`Interval` lists.

    Handles the flat ``result.details[]`` per-word shape, which is what the
    alignment ``core_type`` returns.

    Zero-length phones, out-of-order ones among them, are dropped rather than
    emitted as invalid intervals, and the rest are sorted by time, so downstream
    scoring never sees a non-monotonic or negative-length phone.
    """
    words: list[Interval] = []
    phones: list[Interval] = []
    for w in payload.get("result", {}).get("details", []):
        try:
            ws, we = w["begin"] / _MS_PER_S, w["end"] / _MS_PER_S
        except (KeyError, TypeError):
            continue
        if we > ws:
            words.append(Interval(str(w.get("char", "")), ws, we, w.get("score")))
        for p in w.get("phone", []):
            try:
                ps, pe = p["begin"] / _MS_PER_S, p["end"] / _MS_PER_S
            except (KeyError, TypeError):
                continue
            if pe <= ps:
                continue  # zero/negative-length placeholder — not a real phone
            phones.append(Interval(str(p.get("char", "")), ps, pe, p.get("score")))
    phones.sort(key=lambda iv: (iv.start, iv.end))
    return words, phones


class Olign(AlignerAdapter):
    source = "arpabet"
    emits_confidence = True  # per-phone 0..rank pronunciation score, as a proxy
    granularity = ("word", "phone")
    #: Take the runner's concurrent align_corpus path (runner.py::_align_batch).
    #: olign is a *network* aligner, so "batch" means fan the per-item REST calls
    #: across a thread pool instead of one slow serial loop -- the calls are
    #: I/O-bound (urllib releases the GIL while blocked on the socket), so threads
    #: give real concurrency. Worker count = params["concurrency"] (default 1).
    batch = True

    # ---- transport ----------------------------------------------------------
    def _align_rest(self, audio_path: str, transcript: str) -> dict:
        base = self.params.get("base_url", _DEFAULT_BASE)
        url = "{}?{}".format(base, build_query(
            transcript,
            core_type=self._core_type(),
            accent=int(self.params.get("accent", 2)),
            edge_snap=self.params.get("edge_snap"),
            refine_boundaries=self.params.get("refine_boundaries"),
        ))
        with open(audio_path, "rb") as f:
            body = f.read()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/octet-stream",
                     "User-Agent": _USER_AGENT, **_auth_headers()},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout()) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise AlignerError(f"olign HTTP {e.code}: {e.read()[:200]!r}") from e
        except Exception as e:
            raise AlignerError(f"olign REST call failed: {e}") from e

    # ---- helpers ----------------------------------------------------------
    def _core_type(self) -> str:
        return self.params.get("core_type", _DEFAULT_CORE_TYPE)

    def _timeout(self) -> float:
        return float(self.params.get("timeout_s", _DEFAULT_TIMEOUT_S))

    # ---- contract ---------------------------------------------------------
    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        if mode == "B":
            raise ModeUnsupported("olign is text-driven (Mode A only)")
        self.load()

        transport = self.params.get("transport", "rest")
        if transport != "rest":
            raise AlignerError(f"unknown olign transport {transport!r}, rest is the only one")
        payload = self._align_rest(audio_path, transcript)

        # errId can be non-zero even on HTTP 200 (doc §3) — always check it.
        err_id = payload.get("errId", 0)
        if err_id:
            raise AlignerError(f"olign errId={err_id}: {payload.get('error', '')}")

        words, phones = parse_olign_result(payload)
        if not phones and not words:
            raise AlignerError("olign returned no word/phone details")

        from fabench.audio import load_resample

        x, sr = load_resample(audio_path, 16000)
        dur = len(x) / sr
        # Since 2026-10-11 the body carries a versions object. Kept as given,
        # its keys unread, so each hyp record says what aligned it. Older
        # bodies carry none and add nothing.
        return AlignerOutput(
            words=clamp_intervals(words, dur), phones=clamp_intervals(phones, dur),
            meta={"versions": payload["versions"]} if "versions" in payload else {},
        )

    def align_corpus(self, items) -> dict:
        """Align a whole corpus, fanning the per-item REST calls across
        ``params["concurrency"]`` worker threads. Returns ``{item_id:
        AlignerOutput}`` with failed items omitted (the adapter contract) so one
        item's failure never aborts the batch; a summary count is logged.

        Keep ``concurrency`` at or below what the endpoint serves.
        """
        import sys
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.load()
        workers = max(1, int(self.params.get("concurrency", 1)))

        def _one(it):
            return it.item_id, self.align(it.audio_path, it.transcript, mode=it.mode)

        out: dict = {}
        n_fail = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_one, it) for it in items]
            for fut in as_completed(futures):
                try:
                    item_id, result = fut.result()
                except Exception:  # AlignerError etc. -> omit (contract-compliant)
                    n_fail += 1
                    continue
                out[item_id] = result
        if n_fail:
            print(
                f"  [olign] {n_fail}/{len(items)} items failed (omitted from batch)",
                file=sys.stderr,
            )
        return out
