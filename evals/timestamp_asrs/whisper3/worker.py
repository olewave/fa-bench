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


"""Whisper large-v3 in its OWN interpreter.

    in : {"item_id":..., "audio_path":...}
    out: {"item_id":..., "words": [[label, start_s, end_s], ...]}

`return_timestamps="word"` yields chunks as {"text": " word", "timestamp":
(start, end)}. A trailing chunk can carry a None end when the model runs to the
edge of the audio; those are clipped to the clip duration rather than dropped,
so a truncated final word still contributes a boundary.
"""
from __future__ import annotations

import json
import sys


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    name = argv[1] if len(argv) > 1 else "openai/whisper-large-v3"
    with open(jobs_path) as f:
        jobs = [json.loads(line) for line in f if line.strip()]

    import torch
    from transformers import pipeline

    cuda = torch.cuda.is_available()
    pipe = pipeline(
        "automatic-speech-recognition",
        model=name,
        torch_dtype=torch.float16 if cuda else torch.float32,
        device="cuda:0" if cuda else "cpu",
    )

    out = sys.stdout
    for j in jobs:
        try:
            r = pipe(j["audio_path"], return_timestamps="word",
                     generate_kwargs={"language": "english", "task": "transcribe"})
            words = []
            for ch in r.get("chunks", []):
                lab = (ch.get("text") or "").strip()
                ts = ch.get("timestamp") or (None, None)
                st, en = ts[0], ts[1]
                if not lab or st is None:
                    continue
                if en is None:                       # ran to the edge of the clip
                    en = j.get("duration_s") or st
                words.append([lab, float(st), float(en)])
            out.write(json.dumps({"item_id": j["item_id"], "words": words}) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"],
                                  "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
