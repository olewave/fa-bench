#!/usr/bin/env bash
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

# Qwen3-ForcedAligner-0.6B for FA-Bench -- PRIVATE venv.
#
#   https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B
#
# A FORCED ALIGNER, not an ASR: it takes audio + a reference transcript + a
# language and returns word/character units with start_time and end_time. That
# is why it lives in evals/aligners/ and not evals/timestamp_asrs/ -- see fabench/paths.py.
#
# Own venv, not the shared .venv: it ships as `qwen_asr`, which pins its own
# transformers, and the shared env is what Charsiu and BFA import in-process.
#
# TORCH BUILD: the host driver is 12.9, so a cu130 wheel loads but reports
# torch.cuda.is_available() == False and everything silently runs on CPU. cu128
# is correct for these 3090s; keep it equal to the shared .venv's torch.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-Qwen/Qwen3-ForcedAligner-0.6B}

uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
# qwen-asr VERSION PINNED to what produced the published numbers (provenance
# table in results/README.md). Bump deliberately + re-run the sweep.
uv pip install --python "$HERE/venv/bin/python" qwen-asr==0.0.6 soundfile librosa

"$HERE/venv/bin/python" - <<PY
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
from qwen_asr import Qwen3ForcedAligner
print("fetching $MODEL ...")
Qwen3ForcedAligner.from_pretrained("$MODEL")
print("qwen3_fa ok")
PY
