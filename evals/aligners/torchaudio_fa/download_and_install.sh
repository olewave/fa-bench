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

# torchaudio forced alignment for FA-Bench -- PRIVATE venv.
#
# Own venv, not the shared .venv. It was the LAST tool importing torch
# in-process, so the shared environment carried a ~3 GB CUDA build for exactly
# one consumer -- and this tool's numbers were set by whatever that shared
# environment resolved to. Installing whisperx there once moved torch 2.13 ->
# 2.8 under Charsiu and BFA; the same exposure applied here.
#
# VERSIONS ARE PINNED TO WHAT PRODUCED THE PUBLISHED ROWS. torch/torchaudio
# 2.8.0+cu128 and transformers 5.14.1 are exactly what the shared .venv carried
# when summary/aligners/ was last built. Bump deliberately, then re-run the
# cells and diff -- a different CTC build can move boundaries.
#
# TORCH BUILD: the host driver is 12.9, so a cu130 wheel loads but reports
# torch.cuda.is_available() == False and everything silently runs on CPU. cu128
# is correct for these 3090s.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PHONEME=${PHONEME:-facebook/wav2vec2-lv-60-espeak-cv-ft}

uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
# transformers for the phoneme model; soundfile + scipy for the same audio read
# and polyphase resample fabench.audio uses, so Mode A/B inputs are identical.
# phonemizer is a HARD requirement of Wav2Vec2PhonemeCTCTokenizer, which the
# espeak phoneme model uses -- transformers raises ImportError at load without
# it. It was present in the shared .venv, so the in-process version never named
# it; a private venv has to.
uv pip install --python "$HERE/venv/bin/python" \
    transformers==5.14.1 soundfile==0.14.0 scipy==1.18.0 phonemizer

"$HERE/venv/bin/python" - <<PY
import torch, torchaudio
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
b = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
b.get_model(); print("bundle ok", b.sample_rate, "Hz")
from transformers import AutoProcessor, AutoModelForCTC
print("fetching $PHONEME ...")
AutoProcessor.from_pretrained("$PHONEME"); AutoModelForCTC.from_pretrained("$PHONEME")
print("torchaudio_fa ok")
PY
