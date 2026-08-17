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

"""olign — the user's own speech-assessment service, as a FA-Bench aligner.

olign returns a pronunciation *scorecard* (per-word and per-phone scores) that
also carries per-word/per-phone ``begin``/``end`` timings, which is what makes it
scoreable as a forced aligner at all. See this package's ``README.md`` for the
wire contract.

Transports
----------
Two doors, both documented; REST is the default because it is the one that is
actually published and reachable:

* ``rest`` (default) — ``POST <base>?ref_text=...`` with the raw audio as the
  body. The server transcodes any container/codec itself, so FA-Bench hands it
  the corpus WAV untouched. Per-item, stateless.
* ``grpc`` — the legacy bidi-streaming door (``olewave.olign.OlewaveSpeech/
  StreamingInference``): one JSON config message, then headerless 16 kHz mono
  PCM16 chunks. Kept because it is still served and is the lower-overhead path,
  but it requires the stubs in ``olign_proto/``.

Mode A (from text) only: olign aligns against a reference transcript, like BFA.

Phone labels are lowercase, stress-less CMU/ARPABET (e.g. ``"w"``, ``"ah"``)
-> canonicalize via the existing ``"arpabet"`` normalization source.

History — a REST timing defect, fixed server-side 2026-07-20
------------------------------------------------------------
Until 2026-07-20 the REST door mangled the audio before alignment: it detected
the speech onset but then laid every subsequent phone out at a fixed nominal
30 ms (92.7 % of TIMIT phones exactly 30 ms) and ended the alignment far short
of the audio, so matched-set MAE was ~940 ms — layout drift, not alignment. The
acoustic extractor (still v0.5.0) was never at fault; the REST audio path was.
Once fixed, olign scores a real full-corpus MAE of ~20.5 ms (TIMIT) / ~18.7 ms
(Buckeye) — best of all tested aligners on spontaneous speech; see
summary/. ``test_olign.py::test_fixture_has_varied_real_timings`` guards
against a regression.

TIME UNITS
----------
``begin``/``end``/``dur`` are **milliseconds**, not the "10 ms units" stated in
olign's own API notes. Verified empirically: the first-phone onset tracks the
TIMIT gold speech onset only under the ms reading (gold 0.19 s -> olign 0.13 s;
the 10 ms reading gives 1.30 s, past the end of several utterances). ``wavetime``
is separately unreliable and is not used here.
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
#: by choosing the URL, there is no version header to negotiate -- and `v1` only
#: moves on a breaking change, so this default does not rot under additive ones.
#:
#: Override with params.base_url, or with the OLIGN_BASE_URL environment
#: variable, which is how a self-hosted or LAN instance is pointed at WITHOUT
#: putting a private address in a tracked file.
_DEFAULT_BASE = os.environ.get(
    "OLIGN_BASE_URL", "https://api.olewave.com/olign/v1"
)
_DEFAULT_GRPC_HOST = os.environ.get("OLIGN_GRPC_HOST", "")
_DEFAULT_CORE_TYPE = "en.phone.align"
_DEFAULT_CHUNK_BYTES = 3200  # 100 ms @ 16 kHz mono int16, the doc's own cadence
_DEFAULT_TIMEOUT_S = 60.0

#: begin/end/dur are milliseconds (see module docstring — this contradicts the
#: doc, and was settled against TIMIT gold onsets rather than taken on faith).
_MS_PER_S = 1000.0


def build_query(
    transcript: str, *, core_type: str = _DEFAULT_CORE_TYPE, accent: int = 2, rank: int = 100,
    edge_snap: int | None = None, refine_boundaries: int | None = None,
    filler_align: int | None = None, edge_phone_cap: int | None = None,
) -> str:
    """The REST query string (doc §2). Everything except the audio goes here.

    ``edge_snap`` / ``refine_boundaries`` are the server's boundary
    post-processing toggles (0/1): energy edge-snap, and first-order
    fbank-derivative refinement (rising-edge at word begins, falling-edge at
    ends, ±25 ms). Omit either (None) -> server default (edge_snap on, refine
    off). They move word begin/end only; scores are byte-identical across modes.
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
    if filler_align is not None:
        q["filler_align"] = int(filler_align)   # offer laughter/noise/oov in the optional-silence slot
    if edge_phone_cap is not None:
        q["edge_phone_cap"] = int(edge_phone_cap)  # ms cap on an edge phone (blunt bound; default off)
    return urllib.parse.urlencode(q)


def build_config(
    transcript: str, *, core_type: str = _DEFAULT_CORE_TYPE, vad_enable: int = 0
) -> dict:
    """The gRPC/WebSocket config JSON (doc §"gRPC / WebSocket").

    Keys are **snake_case** (``core_type``/``ref_text``, not
    ``coreType``/``refText``).
    """
    return {
        "audio": {"audio_type": "wav", "sample_rate": 16000, "channel": 1, "sample_bytes": 2},
        "app": {"user_id": "fabench", "application_id": "fabench"},
        "request": {
            "core_type": core_type,
            "ref_text": transcript,
            "rank": 100,
            "accent": 2,
            "result": {"details": {"raw": 1, "sym": 0, "phone": 1}},
        },
        "vad": {"vad_enable": vad_enable},
    }


def parse_olign_result(payload: dict) -> tuple[list[Interval], list[Interval]]:
    """olign scorecard JSON -> FA-Bench word/phone :class:`Interval` lists.

    Handles the flat ``result.details[]`` per-word shape, which is what the
    alignment ``core_type`` returns.

    Two real-data shapes are defended against, both observed against the live
    server: zero-duration phones (2.4 % of a TIMIT sample) and a phone whose
    ``begin`` resets to 0 mid-utterance (seen on a zero-scored word). Both are
    dropped rather than emitted as invalid intervals, so downstream scoring never
    sees a non-monotonic or negative-length phone.
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

    # ---- transports -------------------------------------------------------
    def _align_rest(self, audio_path: str, transcript: str) -> dict:
        base = self.params.get("base_url", _DEFAULT_BASE)
        url = "{}?{}".format(base, build_query(
            transcript,
            core_type=self._core_type(),
            accent=int(self.params.get("accent", 2)),
            edge_snap=self.params.get("edge_snap"),
            refine_boundaries=self.params.get("refine_boundaries"),
            filler_align=self.params.get("filler_align"),
            edge_phone_cap=self.params.get("edge_phone_cap"),
        ))
        with open(audio_path, "rb") as f:
            body = f.read()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout()) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise AlignerError(f"olign HTTP {e.code}: {e.read()[:200]!r}") from e
        except Exception as e:
            raise AlignerError(f"olign REST call failed: {e}") from e

    def _align_grpc(self, audio_path: str, transcript: str) -> dict:
        import numpy as np

        from fabench.audio import load_resample

        self._load_grpc()
        x, _sr = load_resample(audio_path, 16000)
        pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
        config = build_config(
            transcript,
            core_type=self._core_type(),
            vad_enable=int(self.params.get("vad_enable", 0)),
        )
        chunk = int(self.params.get("chunk_bytes", _DEFAULT_CHUNK_BYTES))

        def gen():
            yield self.pb2.StreamingInferenceRequest(
                json_config=self.pb2.JsonConfig(config=json.dumps(config))
            )
            for i in range(0, len(pcm), chunk):
                yield self.pb2.StreamingInferenceRequest(audio_content=pcm[i : i + chunk])

        try:
            responses = list(self.stub.StreamingInference(gen(), timeout=self._timeout()))
        except self.grpc.RpcError as e:
            raise AlignerError(f"olign RPC failed: {e.code()} {e.details()}") from e
        if not responses:
            raise AlignerError("olign returned no responses")
        return json.loads(responses[-1].json_output)

    # ---- helpers ----------------------------------------------------------
    def _core_type(self) -> str:
        return self.params.get("core_type", _DEFAULT_CORE_TYPE)

    def _timeout(self) -> float:
        return float(self.params.get("timeout_s", _DEFAULT_TIMEOUT_S))

    def _load_grpc(self) -> None:
        if getattr(self, "_grpc_ready", False):
            return
        try:
            import grpc

            from fabench.aligners.olign.proto import olign_pb2, olign_pb2_grpc
        except Exception as e:  # pragma: no cover - optional dependency
            raise AlignerError(
                "olign gRPC transport needs `grpcio` plus the compiled stubs in "
                "fabench/aligners/olign/proto/ (see olign.proto for the regen "
                f"command). Use transport: rest to avoid them. ({e})"
            ) from e
        self.grpc = grpc
        self.pb2 = olign_pb2
        self.channel = grpc.insecure_channel(self.params.get("host", _DEFAULT_GRPC_HOST))
        self.stub = olign_pb2_grpc.OlewaveSpeechStub(self.channel)
        self._grpc_ready = True

    # ---- contract ---------------------------------------------------------
    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        if mode == "B":
            raise ModeUnsupported("olign is text-driven (Mode A only)")
        self.load()

        transport = self.params.get("transport", "rest")
        if transport == "rest":
            payload = self._align_rest(audio_path, transcript)
        elif transport == "grpc":
            payload = self._align_grpc(audio_path, transcript)
        else:
            raise AlignerError(f"unknown olign transport {transport!r} (rest|grpc)")

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
        return AlignerOutput(
            words=clamp_intervals(words, dur), phones=clamp_intervals(phones, dur)
        )

    def align_corpus(self, items) -> dict:
        """Align a whole corpus, fanning the per-item REST calls across
        ``params["concurrency"]`` worker threads. Returns ``{item_id:
        AlignerOutput}`` with failed items omitted (the adapter contract) so one
        item's failure never aborts the batch; a summary count is logged.

        Keep ``concurrency`` at or below what the olign deployment can serve
        (docs: ~1 concurrent stream/core). Only the REST transport is
        concurrency-hardened -- gRPC shares a single stub, so leave concurrency
        at 1 for ``transport: grpc``.
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
