#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

# rumblex for FA-Bench -- in a PRIVATE venv.
#
#   https://github.com/EdwardGlockner/rumblex
#   https://huggingface.co/Reson8/Rumble-2-Flash
#
# A FORCED ALIGNER here, not an ASR: `rumblex.align` takes audio and a reference
# transcript and places the words with the checkpoint's CTC head. That is why
# it lives in evals/aligners/ and not evals/timestamp_asrs/.
#
# Own venv, not the shared .venv: rumblex needs transformers >= 5.21 for the
# Rumble-2-Flash model class.
#
# TORCH BUILD: the same pin as the other recipes (see qwen3_fa's for why cu128).
# rumblex itself only asks for torch >= 2.6. These pins were checked on CPU
# only, with the +cpu wheel; the cu128 build has not been run with rumblex.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-Reson8/Rumble-2-Flash}

# Re-runnable: reuse a venv that already has an interpreter.
[ -x "$HERE/venv/bin/python" ] || uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
# rumblex VERSION PINNED. Not below 0.5.0: earlier releases put word ends too
# early when the transcript has no punctuation, as Buckeye's has not. 0.6.0
# adds the learned start and end correction, which moves every word time.
# Bump deliberately + re-run the sweep.
uv pip install --python "$HERE/venv/bin/python" rumblex==0.6.0

# uv venvs have no pip of their own; ask uv, not the venv.
uv pip freeze --python "$HERE/venv/bin/python" > "$HERE/requirements.lock"

"$HERE/venv/bin/python" - <<PY
import torch
import rumblex
print("rumblex", rumblex.__version__, "| torch", torch.__version__, "cuda", torch.cuda.is_available())
print("fetching $MODEL ...")
rumblex.load_model("$MODEL", device="cpu")
print("rumblex ok")
PY
