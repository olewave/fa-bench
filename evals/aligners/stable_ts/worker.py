#!/usr/bin/env python
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

"""Batch forced-alignment worker for stable-ts.

Runs in the tool's OWN interpreter (evals/aligners/stable_ts/venv/bin/python).
stable-ts pins its own openai-whisper and a torch range; installing it into
FA-Bench's shared .venv would move torch/transformers under charsiu and bfa, as
whisperx already did once in this repo.

FORCED ALIGNMENT, NOT TRANSCRIPTION. We call `model.align(audio, text, ...)`,
which consumes the reference transcript and returns one word per reference
token. `model.transcribe()` is deliberately NOT used -- that would decode its
own words and make this a track-2 system.

Protocol: JSONL job records on argv[1], JSONL results to stdout.
    in : {"item_id": ..., "audio_path": ..., "transcript": ...}
    out: {"item_id": ..., "words": [[text, start, end], ...]}   on success
         {"item_id": ..., "error": "..."}                        on failure

argv[2] is the Whisper model name (default "base"); argv[3], if present, the
device.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    jobs_path = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "base"
    device = sys.argv[3] if len(sys.argv) > 3 else None

    import stable_whisper

    # Load ONCE for the whole batch -- a subprocess per utterance would pay
    # model load every time, which is what makes the isolation affordable.
    model = stable_whisper.load_model(model_name, device=device)

    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            out = {"item_id": job["item_id"]}
            try:
                res = model.align(
                    job["audio_path"], job["transcript"], language="en",
                    # keep the reference tokens intact: no regrouping, no
                    # splitting, or the emitted words stop matching the
                    # reference sequence the scorer pairs against
                    regroup=False,
                )
                words = []
                for seg in res.segments:
                    for w in getattr(seg, "words", None) or []:
                        txt = (w.word or "").strip()
                        if txt:
                            words.append([txt, float(w.start), float(w.end)])
                if not words:
                    raise RuntimeError("align() returned no word timings")
                out["words"] = words
            except Exception as e:
                out["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
