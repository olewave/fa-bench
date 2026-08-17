#!/bin/bash
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

# Charsiu (wav2vec2 frame classifier) -- self-contained under evals/charsiu/repo/
#   repo/charsiu/  the checkout; its src/ must be on sys.path (custom model
#                  classes, so pip alone is not enough)
#   repo/env/      venv with torch + transformers
# The original run used FA-Bench's own .venv (torch 2.12.1+cu130,
# transformers 5.13.0); here it gets its own env so versions are pinned.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$HERE/repo; mkdir -p "$REPO"
# PINNED. An unpinned clone means the benchmark measures whatever upstream
# happened to be on the day you installed, and a re-run months later silently
# measures something else. Same failure we hit with an unpinned `pip install
# torch`, which resolved to a cu130 wheel this box's CUDA 12.9 driver cannot
# use and left the tool silently on CPU.
#
# Published FA-Bench numbers for charsiu were produced at this commit.
CHARSIU_COMMIT=13a69f2a22ca0c0962b75cc693399b0ae23a12c9   # 2022-09-18
if [ ! -d "$REPO/charsiu" ]; then
  # --depth 1 cannot take a SHA, so fetch the single commit instead of cloning
  # the history. GitHub allows fetch-by-SHA; if a mirror does not, drop
  # --depth 1 and use a full clone + checkout.
  mkdir -p "$REPO/charsiu"
  git -C "$REPO/charsiu" init -q
  git -C "$REPO/charsiu" remote add origin https://github.com/lingjzhu/charsiu
  git -C "$REPO/charsiu" fetch -q --depth 1 origin "$CHARSIU_COMMIT"
  git -C "$REPO/charsiu" checkout -q FETCH_HEAD
fi
got=$(git -C "$REPO/charsiu" rev-parse HEAD 2>/dev/null)
[ "$got" = "$CHARSIU_COMMIT" ] || {
  echo "WARNING: charsiu is at $got, expected $CHARSIU_COMMIT" >&2; }
[ -d "$REPO/env" ] || python3 -m venv "$REPO/env"
# torch MUST come from the cu128 wheel index. Plain `pip install torch`
# now resolves to 2.13.0+cu130, and this box's driver is CUDA 12.9, so
# torch.cuda.is_available() silently returns False and the tool runs on
# CPU ~40x slower with no error. Measured: 2.8.0+cu128 -> cuda True,
# 2.13.0+cu130 -> cuda False. Pin the index, not just the version.
TORCH_INDEX="https://download.pytorch.org/whl/cu128"
#
# --force-reinstall AND an exact version are both required. Without them
# `pip install --index-url <cu128> torch` is a NO-OP when torch is already
# present: pip checks whether the requirement is satisfied, not which index
# it came from, so a cu130 build stays put and cuda stays False. Verified
# the hard way -- the un-forced form reported success and changed nothing.
"$REPO/env/bin/pip" install -q --upgrade pip
"$REPO/env/bin/pip" install -q --force-reinstall --index-url "$TORCH_INDEX" torch==2.8.0 torchaudio==2.8.0
# nltk and g2pM are named explicitly: charsiu's G2P imports both directly, and
# neither arrived as a g2p_en dependency here -- the first sweep failed every
# cell with "No module named 'nltk'". g2p_en also needs the cmudict corpus at
# RUNTIME, which pip does not fetch, so pull it now rather than on first align.
"$REPO/env/bin/pip" install -q transformers librosa soundfile numpy scipy \
    g2p_en g2pM nltk praatio
"$REPO/env/bin/python" -c "import nltk; nltk.download('cmudict', quiet=True)"
PYTHONPATH="$REPO/charsiu/src" "$REPO/env/bin/python" -c "
import torch,transformers; print('  torch',torch.__version__,'cuda',torch.cuda.is_available(),'transformers',transformers.__version__)"
echo "  repo_path: $REPO/charsiu/src"
