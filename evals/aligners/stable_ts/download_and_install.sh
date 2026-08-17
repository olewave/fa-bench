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

# stable-ts in its OWN venv. https://github.com/jianfch/stable-ts
#
# Pinned to a COMMIT, not a branch: a pip install from a moving ref makes the
# published number unreproducible the moment upstream pushes, and this repo has
# already been bitten by unpinned installs (an unpinned torch pulled
# 2.13.0+cu130 against a 12.9 driver and silently fell back to CPU).
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV="$HERE/venv"
# jianfch/stable-ts @ 2026-08-11
COMMIT=${STABLE_TS_COMMIT:-e312072cc024ae9fceb25b057d7d18524873a02b}
# cu128 matches the 12.9 driver on this box; see the torch note above.
TORCH_INDEX=${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}

command -v uv >/dev/null || { echo "uv not found" >&2; exit 1; }

echo "  creating $VENV"
uv venv --python 3.12 "$VENV"

echo "  torch (pinned, cu128)"
uv pip install --python "$VENV/bin/python" --index-url "$TORCH_INDEX" \
    "torch==2.8.0" "torchaudio==2.8.0"

# numba FIRST, and pinned modern. Left to the resolver, openai-whisper drags in
# numba 0.53.1 -> llvmlite 0.36, which refuses to build on Python >=3.10:
#   RuntimeError: Cannot install on Python version 3.12.3; only versions
#   >=3.6,<3.10 are supported.
# This is the same chain that defeated a fresh parakeet install in this repo.
# Installing a 3.12-capable numba up front removes 0.53.1 from the solution set.
echo "  numba/llvmlite (pinned ahead of the resolver)"
uv pip install --python "$VENV/bin/python" "numba>=0.60" "llvmlite>=0.43"

echo "  stable-ts @ ${COMMIT:0:12}"
uv pip install --python "$VENV/bin/python" \
    "git+https://github.com/jianfch/stable-ts@${COMMIT}"

echo "  freezing"
# uv venvs have no pip of their own; ask uv, not the venv.
uv pip freeze --python "$VENV/bin/python" > "$HERE/requirements.lock"

echo "  verifying"
"$VENV/bin/python" - <<'PY'
import torch, stable_whisper
print(f"    torch {torch.__version__}  cuda={torch.cuda.is_available()}")
print(f"    stable_whisper {getattr(stable_whisper, '__version__', '(no __version__)')}")
assert hasattr(stable_whisper, "load_model"), "no load_model"
m = stable_whisper.load_model  # noqa: F841
print("    load_model present; align() checked at first run")
PY
echo "  done -- set params.venv to $VENV"
