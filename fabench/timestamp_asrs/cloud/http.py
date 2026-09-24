# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Stdlib HTTP for the commercial ASR APIs. No vendor SDKs.

WHY NO SDKs. Four vendors would bring four dependency trees into a benchmark
whose stated property is that one tool's dependency resolution cannot move
another tool's numbers, and the machine the sweeps run on has no PyPI route
(pypi.org is IPv6-only there, see the offline-host notes in evals/README.md). All
four APIs are plain HTTPS and JSON, so urllib does the whole job and these rows
need no venv, no installer and no lock file. The cost is that every request is
spelled out here rather than hidden behind a client object, which for four
endpoints is a fair trade and makes the wire format auditable.

Retries are the other reason this is shared. A paid API fails differently from
a local model: 429 and 5xx are routine and retryable, 401 and 400 are not, and
retrying the second kind burns money for nothing. That distinction is made once,
here, rather than four times.
"""
from __future__ import annotations

import json
import random
import socket
import ssl
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable

#: Retryable. 408 request timeout, 429 rate limit, 5xx server side.
RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

#: Per-call counters, THREAD-LOCAL because align_corpus fans these calls across
#: a pool and a shared dict would mix one utterance's retries into another's.
#: Thread-local rather than a parameter so provider signatures stay about the
#: vendor rather than about bookkeeping.
_local = threading.local()


def reset_stats() -> None:
    _local.stats = {"retries": 0, "backoff_s": 0.0}


def stats() -> dict:
    cur = getattr(_local, "stats", None)
    return dict(cur) if cur else {}


def _bump(key: str, by=1) -> None:
    cur = getattr(_local, "stats", None)
    if cur is not None:
        cur[key] = cur.get(key, 0) + by


def _note(key: str, value) -> None:
    """Record a fact about the call, such as the endpoint it went to.

    A closed service's row claims only "this is what it returned on this date",
    and that claim is not checkable without saying WHICH endpoint answered. The
    model name alone is not enough: Google serves the same chirp_2 from v1 and
    v2 paths and from several regions, and a URL pins all of it.
    """
    cur = getattr(_local, "stats", None)
    if cur is not None:
        cur[key] = value


class CloudASRError(Exception):
    """A request failed in a way that is not worth retrying, or ran out of tries."""


def request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | Callable[[], dict[str, str]] | None = None,
    data: bytes | None = None,
    timeout_s: float = 300.0,
    retries: int = 5,
    backoff_s: float = 1.0,
    max_backoff_s: float = 60.0,
    retry_body: tuple[str, ...] = (),
    retry_empty: tuple[int, ...] = (),
) -> bytes:
    """One HTTP call with exponential backoff on the retryable statuses.

    `Retry-After` wins over the computed backoff when the server sends one,
    which is what the vendors' rate limiters actually want. Jitter keeps a
    thread pool from re-colliding in lockstep after a 429.

    `retry_empty` EXISTS FOR AZURE, and is the same kind of thing. Its
    short-audio endpoint answers a throttle with 401 and an EMPTY body, while
    a genuinely bad key gets 401 with a JSON message naming the problem. A 401
    is otherwise never retried, and rightly, so without this a throttled sweep
    loses every call it throttles -- 146 of 192 on the first attempt. Retrying
    only the empty-bodied ones keeps a bad key from burning its five tries.

    `headers` MAY BE A CALLABLE, and for AWS it has to be. A SigV4 signature
    carries the time it was made and Amazon refuses one older than five
    minutes, while S3 refuses a request whose time is off by more than
    fifteen. Signing once and reusing the headers therefore turns a retry into
    a guaranteed failure the moment the backoff and the attempts before it add
    up past five minutes -- which, with eight retries against a 900 s timeout,
    they do. Observed in the first Transcribe sweep as four items lost to
    InvalidSignatureException and RequestTimeTooSkewed, none of which was
    anything but our own stale signature. A callable is re-evaluated per
    attempt, so each attempt is signed when it is actually sent.

    `retry_body` EXISTS FOR AWS, and it is not a nicety. The AWS JSON protocol
    signals throttling as ThrottlingException with HTTP 400, not 429, so the
    status alone cannot tell a rate limit from a malformed request. A 400 is
    correctly never retried, and the result would be that every throttled AWS
    call is dropped rather than backed off -- silent item loss on exactly the
    cells that are running fastest. Naming the exception strings makes those
    and only those retryable.
    """
    last = ""
    for attempt in range(retries + 1):
        h = headers() if callable(headers) else (headers or {})
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()[:400]
            except Exception:  # noqa: S110 - the status line is the error
                pass
            last = f"HTTP {e.code}: {body!r}"
            text = body.decode("utf-8", "replace")
            retryable = (e.code in RETRY_STATUS
                         or any(t in text for t in retry_body)
                         or (e.code in retry_empty and not body.strip()))
            if not retryable or attempt == retries:
                raise CloudASRError(last) from e
            wait = _retry_after(e) or min(max_backoff_s, backoff_s * 2 ** attempt)
        except Exception as e:                      # URLError, socket.timeout, ssl
            last = f"{type(e).__name__}: {e}"
            if attempt == retries:
                raise CloudASRError(last) from e
            wait = min(max_backoff_s, backoff_s * 2 ** attempt)
        slept = wait * (0.5 + random.random())
        # Counted so a latency percentile can be read without wondering whether
        # a slow call was a slow VENDOR or our own backoff.
        _bump("retries")
        _bump("backoff_s", slept)
        time.sleep(slept)
    raise CloudASRError(last or "no attempt made")


def request_json(url: str, **kw) -> dict:
    raw = request(url, **kw)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise CloudASRError(f"non-JSON response: {raw[:200]!r}") from e


def post_json(url: str, payload: dict, headers: dict[str, str], **kw) -> dict:
    h = dict(headers)
    h.setdefault("Content-Type", "application/json")
    return request_json(url, method="POST",
                        data=json.dumps(payload).encode(), headers=h, **kw)


def multipart(fields: dict[str, str],
              files: dict[str, tuple[str, str, bytes]]) -> tuple[str, bytes]:
    """`(content_type, body)` for a multipart/form-data POST.

    `files` maps a form field to `(filename, content_type, bytes)`. Only
    ElevenLabs needs this; its endpoint takes no JSON body at all.
    """
    boundary = "----fabench" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                f"{v}\r\n").encode()
    for k, (fname, ctype, blob) in files.items():
        out += (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n").encode()
        out += blob
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return f"multipart/form-data; boundary={boundary}", bytes(out)


def probe_connect(host: str, port: int = 443, n: int = 3,
                  timeout_s: float = 10.0) -> float | None:
    """Median seconds for DNS + TCP + TLS to `host`, carrying no payload.

    This is the floor under every request, and it is a property of the network
    between this machine and that endpoint rather than of the service. Recorded
    per cell so a fixed-cost figure can be read net of it: without this,
    lat_fixed_s is "queueing plus round trip plus handshake" with no way to tell
    which moved.

    urllib opens a new connection per request and does not pool, so this floor
    is paid on every call rather than once.
    """
    out = []
    ctx = ssl.create_default_context()
    for _ in range(n):
        t0 = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout_s) as sock, \
                    ctx.wrap_socket(sock, server_hostname=host):
                pass
        except Exception:
            return None
        out.append(time.monotonic() - t0)
    return float(statistics.median(out)) if out else None


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    try:
        v = e.headers.get("Retry-After")
    except Exception:
        return None
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        return None          # HTTP-date form; fall back to the computed backoff
