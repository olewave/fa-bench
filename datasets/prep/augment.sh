#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

# Steps 2-3: canonical gold -> four Kaldi noise conditions -> shadow roots.
#
# WHAT THIS PRODUCES
#   <OUT>/{TIMIT,Buckeye}/noisy/<type>/<utt_id>.wav   real audio (step 2)
#   <SHADOW>/<corpus>_<type>/                         symlink tree (step 3)
#
# The shadow root is the trick that makes the noisy sweep cheap: it looks
# exactly like a clean corpus root -- same layout, same names, gold symlinked
# through -- with only the audio pointing at the noisy copy. So every
# processor, split list and scorer works unmodified, and a noisy eval config
# differs from its clean twin by ONE key (see evals/gen_noisy_configs.py).
#
# The parameters are NOT tunable knobs: they follow Kaldi's egs/voxceleb/v2/
# run.sh exactly, so the conditions match what the field trains on:
#   https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh
# See
# README.md in this folder for the table and the reasoning.
#
# Machine paths come from the environment (.fabench.env), never from here:
#   MUSAN   MUSAN corpus root          RIRS    RIRS_NOISES root
#   OUT     where noisy audio is written        WORK  kaldi scratch
#   REF     holds data/golden/<split>/          NJ    parallel jobs
#
# `fabench prepare` runs these steps from the staged corpora instead, writing
# the REF data dirs itself and a sha256 manifest of the result.
#
#   ./datasets/prep/augment.sh                    # all types, both corpora
#   TYPES="babble noise" ./datasets/prep/augment.sh
#   ./datasets/prep/augment.sh --shadow-only      # rebuild symlink trees only
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
PY="${FABENCH_PY:-$ROOT/.venv/bin/python}"
cd "$ROOT"

# The machine's settings, through the shared loader rather than a second copy
# of the parsing: it walks up for .fabench.env, honours $FABENCH_ENV_FILE, and
# leaves any already-exported variable alone -- so
# `MUSAN=/other ./augment.sh` overrides without an edit.
. "$ROOT/evals/env.sh"

TYPES=${TYPES:-"reverb noise music babble"}
SHADOW=${FABENCH_SHADOW:-data/shadow}
# ONE place for the raw noisy audio, written by step 2 and read by step 3. They
# used to take it from different variables (OUT and FABENCH_NOISY_ROOT), so
# setting only the one the template documents sent step 3 to an empty folder.
NOISY=${OUT:-${FABENCH_NOISY_ROOT:-data/noisy}}
shadow_only=false
[ "${1:-}" = "--shadow-only" ] && shadow_only=true

# --- step 2: materialise the noisy audio ----------------------------------
# make_noisy.py is a port of make_noisy.sh (kept beside it as the reference);
# both are seeded, so a re-run is byte-identical rather than a new draw.
if [ "$shadow_only" = false ]; then
  echo "=== step 2: build noisy audio ($TYPES) ==="
  "$PY" -m fabench.dataprep.noisemix.make_noisy --types "$TYPES" --out "$NOISY" || exit 1
fi

# --- step 3: shadow roots, one per (corpus, type) -------------------------
# Corpora come from the tree, not a hardcoded pair, so adding one under
# datasets/languages/<lang>/ is picked up here with no edit. (The Python
# underneath is not language-agnostic yet -- see README.md -- so a corpus it
# does not know is reported and skipped rather than aborting the sweep.)
CORPORA=${CORPORA:-$("$PY" - <<'EOF'
from pathlib import Path
from fabench.paths import languages_dir
print(" ".join(sorted({p.parent.name
                       for p in languages_dir(Path(".")).glob("*/*/config.yaml")})))
EOF
)}

echo "=== step 3: shadow roots -> $SHADOW ==="
for corpus in $CORPORA; do
  for type in $TYPES; do
    out="$SHADOW/${corpus}_${type}"
    if "$PY" -m fabench.dataprep.noisemix.shadow_root \
         --corpus "$corpus" --type "$type" --out "$out" --noisy-root "$NOISY"; then
      echo "  $corpus/$type -> $out"
    else
      echo "  [SKIP] $corpus/$type -- shadow_root.py does not handle $corpus"
    fi
  done
done

echo
echo "next: evals/gen_noisy_configs.py --tools ALL --subsets ALL"
echo "      (writes evals/<kind>/<tool>/configs/noisy_<type>_<corpus>_<subset>.yaml)"
