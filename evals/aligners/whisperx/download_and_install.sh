#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
# Re-runnable: a failed install leaves a partial venv behind, and `uv venv`
# then refuses to touch it -- so the recipe could not be retried without
# manually deleting a directory the error message did not name. Reuse a venv
# that already has an interpreter; the pip install below is idempotent.
[ -x "$HERE/venv/bin/python" ] || uv venv "$HERE/venv" --python 3.12
# whisperx VERSION PINNED to what produced the published numbers (provenance
# table in results/README.md). Bump deliberately + re-run the sweep.
# soundfile + scipy: the worker reads audio and resamples the same
# way fabench.audio does. They were absent while the adapter ran
# in-process and borrowed the shared venv for everything but whisperx.
uv pip install --python "$HERE/venv/bin/python" whisperx==3.8.6 soundfile==0.14.0 scipy==1.18.0 \
    torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 \
    --extra-index-url https://pypi.org/simple
"$HERE/venv/bin/python" -c "import whisperx, torch; print('whisperx ok | torch', torch.__version__, 'cuda', torch.cuda.is_available())"
