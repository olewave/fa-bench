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

# Step 1: staged corpus -> canonical gold.
#
# Reads each corpus's raw annotation (NIST SPHERE + .PHN for TIMIT, .words/
# .phones for Buckeye), applies that corpus's options from
# datasets/languages/<lang>/<corpus>/config.yaml, and writes the canonical interval
# records the rest of the pipeline consumes. Runs the gold plausibility gate (#2) on
# the way through, so a mis-staged corpus fails here rather than in a
# leaderboard.
#
# Roots come from .fabench.env (FABENCH_<CORPUS>_ROOT) -- `fabench init` writes
# them. Nothing is downloaded: TIMIT is LDC-licensed and Buckeye is
# registration-gated, so an unset root fails loud with acquisition
# instructions.
#
#   ./datasets/prep/ingest.sh                # every enabled corpus
#   ./datasets/prep/ingest.sh timit          # just one
#   LIMIT=50 ./datasets/prep/ingest.sh timit # a smoke-sized slice
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
PY="$ROOT/.venv/bin/python"
cd "$ROOT"

LIMIT=${LIMIT:-}
CORPORA=("$@")

if [ ${#CORPORA[@]} -eq 0 ]; then
  # No --corpus: ingest whatever the language layer enables
  # (datasets/languages/<lang>/config.yaml).
  "$PY" -m fabench ingest ${LIMIT:+--limit "$LIMIT"}
else
  for corpus in "${CORPORA[@]}"; do
    echo "=== ingest $corpus ==="
    "$PY" -m fabench ingest --corpus "$corpus" ${LIMIT:+--limit "$LIMIT"}
  done
fi
