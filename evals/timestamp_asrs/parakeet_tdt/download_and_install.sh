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

# NVIDIA Parakeet-TDT 0.6B v3 -- ASR WITH WORD TIMESTAMPS.
#   https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
#
# TDT = Token-and-Duration Transducer: it predicts token DURATIONS, so word
# timestamps are intrinsic rather than bolted on. A production-grade ASR rather
# than a research checkpoint, which makes it an operationally relevant row.
#
# Lives in timestamp_asrs: audio only, own transcript.
# Own venv (nemo pins heavily) + own interpreter at run time. cu128 for the 12.9
# driver, as everywhere else here.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-nvidia/parakeet-tdt-0.6b-v3}
uv venv "$HERE/venv" --python 3.12
# VERSIONS PINNED to requirements.observed -- the environment the published
# Parakeet-TDT numbers were actually measured in (nemo 2.7.3 + torch
# 2.11.0+cu128). The earlier torch==2.8.0 here was aspirational: it matched
# the other tools, not the env that produced the rows, so a fresh install
# would have measured a different stack than the tables report.
#
# The numba/llvmlite chain can defeat this install; see evals/aligners/
# stable_ts/download_and_install.sh for the fix (pin a 3.12-capable numba
# BEFORE the toolkit, so 0.53.1 leaves the solution set).
uv pip install --python "$HERE/venv/bin/python" torch==2.11.0 torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple
uv pip install --python "$HERE/venv/bin/python" "nemo_toolkit[asr]==2.7.3" soundfile librosa
# nemo's resolution REPLACES the torch just pinned above: that install carries no
# index-url, so torch comes from PyPI, whose 2.11.0 is +cu130. The version
# string still reads "2.11.0" and every version check passes, but cu130 needs a
# CUDA 13 driver -- on the 12.9 driver here torch.cuda.is_available() silently
# became False and the tool would have run on CPU. So pin it back AFTER, with
# the LOCAL version spelled out: plain `torch==2.11.0` is considered satisfied
# by 2.11.0+cu130 and uv skips the reinstall ("Audited 2 packages").
uv pip install --python "$HERE/venv/bin/python" \
    --reinstall-package torch --reinstall-package torchaudio \
    "torch==2.11.0+cu128" "torchaudio==2.11.0+cu128" \
    --index-url https://download.pytorch.org/whl/cu128
# env -u LD_LIBRARY_PATH: a login shell pointing at the system CUDA libs makes
# torch find cuDNN 9.11 while it was built against 9.19, which aborts model
# construction with a cuDNN version incompatibility. torch ships its own.
env -u LD_LIBRARY_PATH "$HERE/venv/bin/python" - <<PY
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
assert torch.version.cuda and torch.cuda.is_available(), \
    "CUDA unavailable -- check the torch build tag above is +cu128, not +cu130"
import nemo.collections.asr as nemo_asr
nemo_asr.models.ASRModel.from_pretrained("$MODEL")
print("parakeet_tdt ok")
PY
