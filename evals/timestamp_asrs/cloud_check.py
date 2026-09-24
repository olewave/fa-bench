#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Check a commercial ASR credential on ONE utterance before spending a sweep.

Run this first. A full sweep over both corpora is roughly 48,000 calls and 65
audio hours per provider, so the wrong key, the wrong region or the wrong model
name should cost one second of audio to find out, not an afternoon's billing.

    evals/timestamp_asrs/cloud_check.py                    # every configured provider
    evals/timestamp_asrs/cloud_check.py --audio some.wav
    evals/timestamp_asrs/cloud_check.py deepgram elevenlabs
    evals/timestamp_asrs/cloud_check.py --no-cache         # force a real call

With no --audio it looks for a staged corpus file, and failing that synthesises
a second of silence, which is enough to prove the credential and the response
shape even though it recognises nothing.

Prints, per provider: whether a credential was found, whether the call
succeeded, and the words with their times. A provider with no credential is
reported and skipped, not failed -- registering them one at a time is the
normal way to do this.
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml                                                    # noqa: E402

from fabench.aligners import get_adapter                       # noqa: E402
from fabench.config import AlignerSpec                         # noqa: E402
from fabench.envfile import load_env_file                      # noqa: E402
from fabench.paths import tool_index                           # noqa: E402

#: Every commercial recipe, so `cloud_check.py` with no argument checks
#: everything that can bill. The list went stale twice by being written
#: here and not updated when a provider was added, which is exactly the
#: failure that makes a smoke test worthless, so it is derived from the
#: registry rather than retyped.
def _commercial_tools() -> tuple[str, ...]:
    from fabench.timestamp_asrs.cloud.providers import PROVIDERS
    names = {"google_stt"} | set(PROVIDERS)
    return tuple(sorted(names))


TOOLS = _commercial_tools()


#: Noise corpora live under data/ too, and a music clip proves nothing about a
#: recognizer. Only speech is worth one paid call.
_NOT_SPEECH = ("musan", "rirs", "noise", "/music/", "babble",
               "reverb", "noisy")


#: A sync recognize endpoint caps around here, and a check is meant to cost
#: seconds of audio. Buckeye's SOURCE files are whole 10-minute interviews, so
#: picking one by rglob sends 623 s to a paid endpoint that will refuse it.
_MAX_CHECK_S = 60.0


def _cut_utterances() -> list[str]:
    """The exact per-utterance files a sweep sends, from the mix manifests."""
    import json
    import os

    # The repo's own data/work, which is Config.work_dir()'s default, unless
    # FABENCH_WORK_DIR points elsewhere. A machine path here would name the
    # box the sweep ran on, in a public file.
    work = (os.environ.get("FABENCH_WORK_DIR")
            or str(Path(__file__).resolve().parents[2] / "data" / "work"))
    out = []
    for man in sorted(Path(work).glob("manifests/*__*.jsonl"))[:1]:
        for line in man.read_text().splitlines()[:50]:
            if line.strip():
                out.append(json.loads(line)["mixed_audio_path"])
    return out


def _sample_audio(dest: Path) -> str:
    """One CUT utterance if the mixes are staged, else a synthetic tone."""
    for p in _cut_utterances():
        d = _duration(p)
        if d and d <= _MAX_CHECK_S:
            return p
    for p in sorted(ROOT.glob("data/**/*.wav")):
        if any(k in str(p).lower() for k in _NOT_SPEECH):
            continue
        d = _duration(str(p))
        if d and d <= _MAX_CHECK_S:
            return str(p)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * 220 * t / rate)))
            for t in range(rate)))
    return str(dest)


def _duration(path: str) -> float | None:
    try:
        with wave.open(path) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return None


def _trace_responses() -> None:
    """Print every response before the parser sees it.

    The adapters were written against published response SHAPES, not against
    traffic, so the first real call to each vendor is also the first test of
    that reading. When a shape has moved, the failure surfaces as a KeyError
    naming a field, which says nothing about what did arrive. This prints the
    payload first, so one call diagnoses itself instead of needing a second.
    """
    import json as _json

    from fabench.timestamp_asrs.cloud import providers as _P

    for fname in ("request_json", "post_json"):
        orig = getattr(_P, fname)

        def traced(*args, _orig=orig, **kw):
            out = _orig(*args, **kw)
            url = args[0] if args else kw.get("url", "?")
            body = _json.dumps(out, indent=2)
            print(f"    --- raw response from {url}")
            for line in body.splitlines()[:60]:
                print(f"    {line}")
            if len(body.splitlines()) > 60:
                print(f"    ... {len(body.splitlines()) - 60} more lines")
            return out

        setattr(_P, fname, traced)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tools", nargs="*", default=None,
                    help=f"which to check (default: all of {', '.join(TOOLS)})")
    ap.add_argument("--audio", help="a wav to send; default is a staged or synthetic one")
    ap.add_argument("--no-cache", action="store_true",
                    help="bypass the response cache and make a real call")
    ap.add_argument("--raw", action="store_true",
                    help="print each response before it is parsed")
    a = ap.parse_args(argv)

    if a.raw:
        _trace_responses()

    load_env_file(ROOT)
    audio = a.audio or _sample_audio(ROOT / "summary" / "local" / "cloud_check.wav")
    secs = _duration(audio)
    print(f"audio: {audio}  ({secs:.2f} s)" if secs else f"audio: {audio}")
    if secs and secs > _MAX_CHECK_S:
        print(f"\nREFUSING: {secs:.0f} s is past the {_MAX_CHECK_S:.0f} s a sync "
              f"endpoint accepts, and a check should cost seconds of audio, not "
              f"minutes.\nPass a shorter --audio.", file=sys.stderr)
        return 1
    print()

    rc = 0
    for tool in (a.tools or TOOLS):
        # tool_index, not a path guess: a recipe may be nested under exps/ or
        # v*/, which is where the Chirp 2 variant lives, and a hand-built
        # <tool>/config.yaml path silently misses those.
        found = tool_index(ROOT).get(tool)
        cfg = (found[1] / "config.yaml") if found else None
        if cfg is None or not cfg.exists():
            print(f"{tool:18s} NO RECIPE named {tool!r} under evals/")
            rc = 1
            continue
        spec = yaml.safe_load(cfg.read_text())
        if a.no_cache:
            spec.setdefault("params", {})["cache"] = False
            spec["params"]["cache_dir"] = None
        adapter = get_adapter(AlignerSpec.from_dict(spec))
        try:
            adapter.load()
        except Exception as e:
            # Almost always a missing key, which is expected until it is registered.
            print(f"{tool:12s} SKIP  {e}\n"); continue

        t0 = time.time()
        try:
            out = adapter.align(audio)
        except Exception as e:
            print(f"{tool:12s} FAIL  {type(e).__name__}: {str(e)[:300]}\n")
            rc = 1
            continue
        dt = time.time() - t0
        cached = out.meta.get("cached")
        print(f"{tool:12s} OK    {len(out.words)} words in {dt:.1f}s"
              f"{'  (from cache, no call made)' if cached else ''}"
              f"  model={out.meta.get('api_model')}")
        for w in out.words[:12]:
            c = f"{w.conf:.3f}" if w.conf is not None else "   -  "
            print(f"             {w.start:7.3f} {w.end:7.3f}  {c}  {w.label}")
        if len(out.words) > 12:
            print(f"             ... {len(out.words) - 12} more")
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
