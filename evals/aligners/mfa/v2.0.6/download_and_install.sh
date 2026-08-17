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

# MFA 2.0.6 -- the pre-PostgreSQL 2.x line, for a 2.x vs 3.x comparison.
#
# WHY 2.0.6 AND NOT A LATER 2.x. MFA 2.1 moved the corpus database to
# PostgreSQL: 2.1+ and 2.2+ depend on postgresql, pgvector and psycopg2, and
# `mfa align` initialises and runs a local DB cluster. That is a stateful
# service on a shared box -- it outlives a failed sweep and holds a port and a
# data directory. 2.0.6 is the last 2.x with no database backend, so it is a
# plain env like the 3.4 one. If you specifically need the DB-backed pipeline,
# install 2.2.17 instead and expect to manage a postgres cluster.
#
# SEPARATE PREFIX, NOT A SECOND ENV IN THE 3.4 ROOT: 2.0.6 hard-pins python
# 3.9 (>=3.9,<3.10), while 3.4 is on a newer interpreter. They cannot share.
#
# Models are downloaded INSIDE this env on purpose. MFA ties model format to
# the major version, so the 3.4 english_us_arpa files cannot be reused here --
# which also means a 2.0-vs-3.4 difference is model + code, not code alone.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$HERE/repo
MAMBA_ROOT_PREFIX=$REPO/mamba
export MAMBA_ROOT_PREFIX
BIN=$MAMBA_ROOT_PREFIX/bin/micromamba
ENV_NAME=mfa20
mkdir -p "$MAMBA_ROOT_PREFIX/bin"

if [ ! -x "$BIN" ]; then
  echo "== micromamba =="
  # Fetch to a FILE. `curl -Ls ... | tar -xvj` fails: the endpoint 302s to a
  # signed S3 URL and the pipe dies mid-stream (tar exits 2).
  tmp=$(mktemp /tmp/mm.XXXX.tar.bz2)
  curl -Ls -o "$tmp" https://micro.mamba.pm/api/micromamba/linux-64/latest
  file "$tmp" | grep -q bzip2 || { echo "not bzip2"; exit 1; }
  tar -xjf "$tmp" -C "$MAMBA_ROOT_PREFIX" bin/micromamba && rm -f "$tmp"
  chmod +x "$BIN"
fi
"$BIN" --version

"$BIN" env list | grep -qE "^\s*${ENV_NAME}\s" || \
  "$BIN" create -y -q -n "$ENV_NAME" -c conda-forge \
      montreal-forced-aligner=2.0.6 "python=3.9"

# KALDI/OPENFST ABI. The kaldi that MFA 2.0.6 resolves by default (r7271) was
# built against openfst 1.7 and needs libfst.so.6, but 2.0.6's own dependency
# closure forces openfst >=1.8.2 (libfst.so.25) via pynini/ngram. Every kaldi
# binary then dies with "error while loading shared libraries: libfst.so.6",
# surfacing only as a KaldiProcessingError inside make_mfcc. Pinning openfst
# back to 1.7 is unsolvable; kaldi 5.5.1016 is built against 1.8.2 and fixes it.
"$BIN" install -y -q -n "$ENV_NAME" -c conda-forge "kaldi=5.5.1016=cpu*"

# MODELS. `mfa model download` fetches by NAME from MFA's model server, which
# now serves only the v3 files under `english_us_arpa` -- loading those into
# 2.0.6 yields an empty word-boundary file and zero aligned records, with no
# version-mismatch error. The v2.0.0 files are still archived as GitHub
# releases, so take them from there instead.
#
# MFA_ROOT_DIR is set so these land in a PER-VERSION store: MFA's default
# (~/Documents/MFA) is per USER and is shared with the 3.4 install, where
# whichever version downloaded last would win.
REL=https://github.com/MontrealCorpusTools/mfa-models/releases/download
MFA_ROOT_DIR=$REPO/mfa_root
export MFA_ROOT_DIR
mkdir -p "$MFA_ROOT_DIR/pretrained_models/acoustic" \
         "$MFA_ROOT_DIR/pretrained_models/dictionary"
curl -fsSL -o "$MFA_ROOT_DIR/pretrained_models/acoustic/english_us_arpa.zip" \
  "$REL/acoustic-english_us_arpa-v2.0.0/english_us_arpa.zip"
curl -fsSL -o "$MFA_ROOT_DIR/pretrained_models/dictionary/english_us_arpa.dict" \
  "$REL/dictionary-english_us_arpa-v2.0.0/english_us_arpa.dict"

echo "== installed =="
"$BIN" run -n "$ENV_NAME" mfa version
"$BIN" run -n "$ENV_NAME" env MFA_ROOT_DIR="$MFA_ROOT_DIR" \
    mfa model list acoustic 2>/dev/null | tail -5 || true
echo "models under: $MFA_ROOT_DIR/pretrained_models"
