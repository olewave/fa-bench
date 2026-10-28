#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
PY="${FABENCH_PY:-$ROOT/.venv/bin/python}"
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
