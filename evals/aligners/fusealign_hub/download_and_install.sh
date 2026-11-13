#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

# fusealign_hub (Zyphra's packaged FuseAlign) for FA-Bench -- PRIVATE venv.
#
#   https://github.com/Zyphra/fusealign-multilingual
#   https://huggingface.co/Zyphra/fusealign
#
# The package is installed at a pinned commit and the checkpoint fetched at a
# pinned revision (the same pins as config.yaml), into the Hugging Face cache the
# worker reads, so the worker runs offline afterwards.
#
# PINS: the package's own dev lock (torch/torchaudio 2.9.1 cu128, transformers
# 4.57.3, safetensors 0.7.0, huggingface-hub 0.36.0, silero-vad 6.2.3), so the
# numbers are comparable to its README. soundfile is the worker's audio reader.
# The import check loads the checkpoint on CPU.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMMIT=${COMMIT:-1f141d60bd983c6af7cba25ea5dae8951ad65818}
MODEL=${MODEL:-Zyphra/fusealign}
REVISION=${REVISION:-59f266809e743bbc2ae25bff45e738406090bc50}
CHECKPOINT=${CHECKPOINT:-fusealign-multilingual-cjkft-step2500.safetensors}

uv venv --clear "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" \
    torch==2.9.1 torchaudio==2.9.1 transformers==4.57.3 safetensors==0.7.0 \
    huggingface-hub==0.36.0 silero-vad==6.2.3 soundfile \
    "fusealign-hub @ git+https://github.com/Zyphra/fusealign-multilingual.git@$COMMIT"
uv pip freeze --python "$HERE/venv/bin/python" > "$HERE/requirements.lock"

"$HERE/venv/bin/python" - "$MODEL" "$REVISION" "$CHECKPOINT" <<'PY'
import sys, torch
from huggingface_hub import hf_hub_download
from fusealign_hub import load_aligner
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
path = hf_hub_download(repo_id=sys.argv[1], revision=sys.argv[2], filename=sys.argv[3])
a = load_aligner(path, device="cpu")
print("fusealign_hub ok on", a.device, "from", path)
PY
