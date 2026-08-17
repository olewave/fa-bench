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

# NeuFA for FA-Bench -- PRIVATE venv. Builds the environment and clones the
# repo; it CANNOT finish on its own, because NeuFA publishes no trained
# checkpoint. Train one or obtain it from the authors, place it at
# repo/neufa.pt (or point params.model_path elsewhere), then enable the tool in
# evals/config.yaml.
#
# Torch pinned to what the rest of the benchmark runs (2.8.0+cu128, correct for
# a 12.9 driver; a cu130 wheel loads and silently reports no CUDA).
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=${REPO:-https://github.com/thuhcsi/NeuFA}

[ -d "$HERE/repo" ] || git clone --recursive "$REPO" "$HERE/repo"

uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" \
    torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
# librosa + sequitur-g2p are NeuFA's own; soundfile + scipy are what the worker
# reads and resamples with, matching fabench.audio.
uv pip install --python "$HERE/venv/bin/python" \
    librosa sequitur-g2p soundfile==0.14.0 scipy==1.18.0

"$HERE/venv/bin/python" - <<PY
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
PY
echo
echo "NeuFA environment ready. Still needed: a trained checkpoint at"
echo "  $HERE/repo/neufa.pt"
echo "then set enabled: true in evals/config.yaml."
