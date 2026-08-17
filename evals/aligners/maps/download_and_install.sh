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

# MAPS (Mason-Alberta Phonetic Segmentor) -- self-contained under evals/maps/repo/
#   repo/MAPS/     the checkout (incl. ensemble_model/timbuck_eng_{1..10}.tf)
#   repo/env/      python 3.11 env
#
# Versions copied from the original working install, NOT guessed:
#   python 3.11, tensorflow===2.12.1, numpy==1.24.3  (repo requirements.txt)
# the reproduction host has only python3.12 and TF 2.12 caps at 3.11, so the env comes from
# micromamba rather than venv.
#
# LEAKAGE: the model files are named `timbuck` = TIMIT + Buckeye. MAPS is
# trained on both benchmark corpora; its numbers are train=test here.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$HERE/repo; mkdir -p "$REPO"
# PINNED. An unpinned clone means the benchmark measures whatever upstream
# happened to be on the day you installed, and a re-run months later silently
# measures something else. Same failure we hit with an unpinned `pip install
# torch`, which resolved to a cu130 wheel this box's CUDA 12.9 driver cannot
# use and left the tool silently on CPU.
#
# Published FA-Bench numbers for maps were produced at this commit.
MAPS_COMMIT=bf797f434b83dcb49dac64d575211c4af1253e81   # 2026-02-23
if [ ! -d "$REPO/MAPS" ]; then
  # --depth 1 cannot take a SHA, so fetch the single commit instead of cloning
  # the history. GitHub allows fetch-by-SHA; if a mirror does not, drop
  # --depth 1 and use a full clone + checkout.
  mkdir -p "$REPO/MAPS"
  git -C "$REPO/MAPS" init -q
  git -C "$REPO/MAPS" remote add origin https://github.com/MasonPhonLab/MAPS
  git -C "$REPO/MAPS" fetch -q --depth 1 origin "$MAPS_COMMIT"
  git -C "$REPO/MAPS" checkout -q FETCH_HEAD
fi
got=$(git -C "$REPO/MAPS" rev-parse HEAD 2>/dev/null)
[ "$got" = "$MAPS_COMMIT" ] || {
  echo "WARNING: MAPS is at $got, expected $MAPS_COMMIT" >&2; }
MAMBA_ROOT_PREFIX=$(cd "$HERE/../mfa/repo/mamba" && pwd)
export MAMBA_ROOT_PREFIX
BIN=$MAMBA_ROOT_PREFIX/bin/micromamba
[ -x "$BIN" ] || { echo "run evals/mfa/download_and_install.sh first (provides micromamba)"; exit 1; }
[ -d "$REPO/env" ] || "$BIN" create -y -q -p "$REPO/env" -c conda-forge python=3.11
"$REPO/env/bin/pip" install -q -r "$REPO/MAPS/requirements.txt"
"$REPO/env/bin/python" -c "import tensorflow as tf,numpy;print('  tf',tf.__version__,'numpy',numpy.__version__,'gpus',len(tf.config.list_physical_devices('GPU')))"
ls "$REPO/MAPS/ensemble_model" | head -3

# g2p_en goes in FA-BENCH's venv, not this one. The adapter builds MAPS's
# pronunciation dictionary from the corpus vocabulary before MAPS is invoked,
# in fa-bench's own process -- MAPS never imports it, which is why it is absent
# from the requirements.txt installed above and no amount of work on this env
# can supply it. Installed here because this script is what a user runs to make
# MAPS work, and without it `fabench run` reports "MAPS needs g2p_en", exits 0,
# and leaves whatever hypotheses were already on disk.
FB=$(cd "$HERE/../../.." && pwd)
if [ -x "$FB/.venv/bin/python" ]; then
  uv pip install --python "$FB/.venv/bin/python" g2p-en \
    && "$FB/.venv/bin/python" -c "from g2p_en import G2p; G2p(); print('  g2p_en ok')"
else
  echo "  NOTE: no $FB/.venv -- install the adapter dep yourself:" >&2
  echo "        uv pip install -e '.[maps]'" >&2
fi
