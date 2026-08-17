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

"""Batch forced-alignment worker for Qwen3-ForcedAligner-0.6B.

Runs in the tool's OWN interpreter (evals/aligners/qwen3_fa/venv/bin/python), not
in FA-Bench's. That is required, not tidiness: `qwen_asr` needs transformers
4.57.6 while the shared .venv has 5.14.1, and mixing the two site-packages into
one process fails on native extensions --

    Version mismatch: this is the 'cffi' package version 2.1.1 ...
    when we import the top-level '_cffi_backend' extension module,
    we get version 2.1.0 ...

sys.path tricks cannot fix a compiled-extension mismatch; a separate
interpreter can.

Protocol: JSONL job records on argv[1], JSONL results to stdout.
    in : {"item_id": ..., "audio_path": ..., "transcript": ...}
    out: {"item_id": ..., "words": [[text, start, end], ...]}          on success
         {"item_id": ..., "error": "..."}                              on failure

The model is loaded ONCE for the whole batch — that is the point of running as a
batch adapter rather than a subprocess per utterance.
"""
import json
import sys

from qwen_asr import Qwen3ForcedAligner


def main() -> int:
    with open(sys.argv[1]) as _jf:
        jobs = [json.loads(l) for l in _jf if l.strip()]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "Qwen/Qwen3-ForcedAligner-0.6B"
    language = sys.argv[3] if len(sys.argv) > 3 else "English"

    # device_map is REQUIRED. `from_pretrained` does NOT forward **kwargs to
    # AutoModel, so without it every parameter stays on CPU while
    # torch.cuda.is_available() still reports True -- the tool looks
    # GPU-enabled and silently is not.
    #
    # Measured on 6 TIMIT utterances after warmup:
    #     CPU 3.800 s/utt      GPU 0.249 s/utt      (15x)
    #
    # That placement bug, not model cost, is what made the Buckeye cells
    # exceed a 2 h timeout.
    import torch

    dev = sys.argv[4] if len(sys.argv) > 4 else (
        "cuda:0" if torch.cuda.is_available() else "cpu")
    model = Qwen3ForcedAligner.from_pretrained(model_name, device_map=dev)
    print(f"# qwen3_fa on {dev}", file=sys.stderr)

    out = sys.stdout
    for j in jobs:
        try:
            res = model.align(
                audio=j["audio_path"], text=j["transcript"], language=language
            )
            items = res[0].items if res else []
            words = [[it.text, float(it.start_time), float(it.end_time)] for it in items]
            out.write(json.dumps({"item_id": j["item_id"], "words": words}) + "\n")
        except Exception as e:  # one bad utterance must not lose the batch
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
