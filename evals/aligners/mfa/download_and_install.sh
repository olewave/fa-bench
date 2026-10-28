#!/bin/bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

# MFA 3.4 -- self-contained under evals/mfa/repo/
#   repo/mamba/            micromamba root + the `mfa` env
# Reproduces the original run's env (micromamba, conda-forge, montreal-forced-aligner 3.4).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$HERE/repo
MAMBA_ROOT_PREFIX=$REPO/mamba
export MAMBA_ROOT_PREFIX
BIN=$MAMBA_ROOT_PREFIX/bin/micromamba
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
"$BIN" env list | grep -qE "^\s*mfa\s" || \
  "$BIN" create -y -q -n mfa -c conda-forge montreal-forced-aligner=3.4.1
# MODEL VERSION PINNED, and this matters more than the CLI version: the
# acoustic model places the boundaries. `english_us_arpa` by name alone
# resolves to whatever the model server currently serves. v3.0.0 is the build
# the published numbers were produced with, and the one the MFA-2026 paper
# used. `--version` is supported by the pinned MFA CLI (verified against
# 3.4.1's own --help).
"$BIN" run -n mfa mfa model download acoustic   english_us_arpa --version v3.0.0 || true
"$BIN" run -n mfa mfa model download dictionary english_us_arpa || true
"$BIN" run -n mfa mfa version
