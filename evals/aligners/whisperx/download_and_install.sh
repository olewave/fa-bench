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

# whisperx for FA-Bench -- in a PRIVATE venv.
#
# Not the shared .venv: whisperx pins transformers and torch, and installing it
# there moved transformers 5.14.1 -> 4.57.6 and torch 2.13 -> 2.8 for Charsiu
# and BFA, which import in-process from that same environment.
#
# The adapter appends this venv's site-packages to sys.path, so whisperx is
# found here while torch/transformers still resolve to the shared env. That
# only works while both agree on torch, hence the explicit pin below.
#
# TORCH BUILD: this box's driver is 12.9, so a cu130 wheel loads but reports
# torch.cuda.is_available() == False and every aligner silently runs on CPU.
# cu128 is the correct index for these 3090s.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
uv venv "$HERE/venv" --python 3.12
# whisperx VERSION PINNED to what produced the published numbers (provenance
# table in results/README.md). Bump deliberately + re-run the sweep.
# soundfile + scipy: the worker reads audio and resamples the same
# way fabench.audio does. They were absent while the adapter ran
# in-process and borrowed the shared venv for everything but whisperx.
uv pip install --python "$HERE/venv/bin/python" whisperx soundfile==0.14.0 scipy==1.18.0==3.8.6 \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
"$HERE/venv/bin/python" -c "import whisperx, torch; print('whisperx ok | torch', torch.__version__, 'cuda', torch.cuda.is_available())"
