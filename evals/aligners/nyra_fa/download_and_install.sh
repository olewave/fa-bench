#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0
# Build the nyra forced aligner's own environment and fetch its model.
#
# The package needs espeak-ng for words outside its lexicon. Install it first
# with your system's package manager, for example `apt install espeak-ng`.
#
# The model is under the nyra health Non-Commercial Research License.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-nyralabs/nyra_forced_aligner_en}

command -v espeak-ng >/dev/null || { echo "espeak-ng is missing, install it first" >&2; exit 1; }
uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" nyra-forced-aligner==0.2.4 soundfile

"$HERE/venv/bin/python" - <<PY
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
from nyra_align import Aligner
print("fetching $MODEL ...")
Aligner("$MODEL", device="cpu")
print("nyra_fa ok")
PY
