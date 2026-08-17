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

"""Parakeet-TDT batch worker — runs in its OWN interpreter.

TDT predicts token durations, so NeMo returns word timestamps directly when
`timestamps=True`. Model loads once for the whole batch.

Protocol: JSONL jobs on argv[1] -> JSONL results on stdout.
    in : {"item_id":..., "audio_path":...}          # NO transcript: this is ASR
    out: {"item_id":..., "words":[[text,start,end],...]} | {"item_id":..., "error":...}
"""
import json
import sys

import nemo.collections.asr as nemo_asr


def main() -> int:
    with open(sys.argv[1]) as _jf:
        jobs = [json.loads(l) for l in _jf if l.strip()]
    name = sys.argv[2] if len(sys.argv) > 2 else "nvidia/parakeet-tdt-0.6b-v3"
    model = nemo_asr.models.ASRModel.from_pretrained(name)
    # bf16 autocast on CUDA, matching how this model is run in production
    # elsewhere; fp32 is available but bf16 is the default path and what the
    # published RTF figures reflect.
    import torch
    use_cuda = torch.cuda.is_available()
    if use_cuda:
        model = model.cuda()
    paths = [j["audio_path"] for j in jobs]
    out = sys.stdout
    try:
        if use_cuda:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                hyps = model.transcribe(paths, timestamps=True, batch_size=8)
        else:
            hyps = model.transcribe(paths, timestamps=True, batch_size=8)
    except Exception as e:
        for j in jobs:
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
        return 0
    for j, h in zip(jobs, hyps):
        try:
            ts = (getattr(h, "timestamp", None) or {}).get("word", [])
            words = [[w["word"], float(w["start"]), float(w["end"])] for w in ts]
            out.write(json.dumps({"item_id": j["item_id"], "words": words}) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
    out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
