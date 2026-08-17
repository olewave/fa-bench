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
# the published numbers were produced with -- and the one the MFA-2026 paper
# used, which is why its Table 5 reproduces (results/). `--version` is
# supported by the pinned MFA CLI (verified against 3.4.1's own --help).
"$BIN" run -n mfa mfa model download acoustic   english_us_arpa --version v3.0.0 || true
"$BIN" run -n mfa mfa model download dictionary english_us_arpa || true
"$BIN" run -n mfa mfa version
