#!/usr/bin/env bash
# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

# IBM Granite Speech 4.1 2B-plus -- ASR WITH WORD TIMESTAMPS, in its own venv.
#   https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus
#
# Native support needs transformers >= 5.8, newer than any other tool here
# pins, which is one more reason it gets a venv of its own.
# PIP_CONFIG_FILE is neutralised: see the note in qwen3_asr's installer.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-ibm-granite/granite-speech-4.1-2b-plus}
export PIP_CONFIG_FILE=/dev/null
uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" "torch==2.11.0+cu128" "torchaudio==2.11.0+cu128" \
    --index-url https://download.pytorch.org/whl/cu128
# transformers and accelerate come from PyPI with torch already satisfied, so
# the +cu128 build stays (see parakeet_tdt's installer for what happens when a
# later resolution is allowed to replace it).
uv pip install --python "$HERE/venv/bin/python" --index-url https://pypi.org/simple \
    "transformers>=5.8" accelerate soundfile
uv pip freeze --python "$HERE/venv/bin/python" > "$HERE/requirements.observed"
env -u LD_LIBRARY_PATH "$HERE/venv/bin/python" - <<PY
import torch, transformers
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), "transformers", transformers.__version__)
assert torch.version.cuda and torch.cuda.is_available(), "CUDA unavailable"
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
AutoProcessor.from_pretrained("$MODEL")
AutoModelForSpeechSeq2Seq.from_pretrained("$MODEL")
print("granite_speech_plus ok")
PY
