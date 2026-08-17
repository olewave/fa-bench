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

# Evaluate every installed aligner over every held-out split.
#
# One FA-Bench run per (corpus, subset, tool) rather than one run per cell with
# every aligner enabled: an adapter that dies -- a missing model, a CUDA OOM --
# would otherwise take the whole cell's results with it. Ingest is cached, so
# the extra runs cost little. A failing cell is RECORDED and the sweep carries
# on; nothing here aborts the sweep.
#
# Splits come from datasets/languages/en/{timit,buckeye}/split/*.list. train is not
# evaluated: it is the training split, so a number there measures
# nothing about generalisation.
#
# THREE STAGES, each re-runnable and selectable:
#
#   stage 1  ALIGN clean   -> <recipe>/en/<corpus>/<subset>/hyp.jsonl
#   stage 2  ALIGN noisy   -> <recipe>/en/<corpus>/<subset>__<cond>/hyp.jsonl
#                             (skipped unless --use-noisy-dataset)
#   stage 3  SCORE         -> <recipe>/exp/<config>/summary/
#
# Stage 3 scores from the SAVED hypotheses, so it is cheap and can be re-run
# after any metric change without re-aligning. It writes a recipe-LOCAL result
# (beside the recipe that produced it) rather than the cross-tool tables in
# summary/ -- those come from rescore_all.sh, which pools every tool.
#
# Clean and noisy are stages rather than separate scripts because they are the
# same work over different audio: same recipes, same cells, same scoring. The
# noisy hypotheses land under <subset>__<condition> so they never overwrite the
# clean baseline they are compared against.
#
# Usage:  ./run_evals.sh [--stage N] [--stop-stage N] [--use-noisy-dataset] [tool ...]
#   ./run_evals.sh                          # clean + score
#   ./run_evals.sh --use-noisy-dataset      # clean + noisy + score
#   ./run_evals.sh --stage 3 mfa            # rescore mfa from saved hyp only
#   ./run_evals.sh --use-noisy-dataset true --stop-stage 2   # explicit Kaldi form
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")
PY="$ROOT/.venv/bin/python"
# Per-tool logs live with the tool (evals/<tool>/log/), not in one flat pile at
# evals/ root -- a sweep produces one file per cell and they became unreadable.
# The cross-tool summary stays at evals/log/ since it spans tools by definition.
# Per-cell configs live WITH their tool (evals/<kind>/<tool>/configs/), for the
# same reason the logs do: one flat directory accumulated 443 files across every
# corpus x subset x condition x tool and stopped being readable. evals/configs/
# now holds only the CROSS-tool scoring configs, which name every system by
# definition and so belong to no single one.
CFGS="$HERE/configs"; mkdir -p "$CFGS"
RUNLOG="$HERE/log"; mkdir -p "$RUNLOG"
SUMMARY="$RUNLOG/summary.tsv"

# Kaldi-style knobs: declared with defaults, then set by --option value.
stage=1
stop_stage=3
use_noisy_dataset=false
. "$HERE/parse_options.sh" || exit 1

TOOLS=("$@")
[ ${#TOOLS[@]} -eq 0 ] && TOOLS=(mfa charsiu maps bfa)

# How the sweep uses the box (GPUs, threads) lives in ONE place, not inline in
# each driver: see evals/env.sh and the FABENCH_* knobs it documents.
. "$HERE/env.sh"

CELLS=(
  "timit dev"
  "timit core_test"
  "buckeye dev"
  "buckeye test"
)

[ -f "$SUMMARY" ] || printf 'corpus\tsubset\ttool\tstatus\tseconds\n' > "$SUMMARY"

if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then
echo "=== stage 1: align, clean ==="
for cell in "${CELLS[@]}"; do
  set -- $cell; corpus=$1; subset=$2
  for tool in "${TOOLS[@]}"; do
    tag="${corpus}_${subset}_${tool}"
    # Resolve the tool's KIND instead of assuming aligners/.
    #
    # This mattered far more than a tidy log path. fabench.paths.tool_kind()
    # infers a tool's contract from WHICH evals/<kind>/ dir it lives in -- first
    # match wins, aligners/ first. The old hardcoded
    # `mkdir -p $HERE/aligners/$tool/log` CREATED that directory, so after one
    # sweep parakeet_tdt (a timestamp_asr) was classified as an aligner and
    # every hyp.jsonl was written under evals/aligners/. The check below looked in
    # the same wrong place and reported OK, so nothing ever surfaced.
    kind=aligners
    [ -d "$HERE/timestamp_asrs/$tool" ] && kind=timestamp_asrs
    tdir=$("$PY" -c "from fabench.paths import tool_dir; from pathlib import Path; print(tool_dir(Path('$ROOT'), '$tool'))" 2>/dev/null) \
      || tdir="$HERE/$kind/$tool"
    tlog="$tdir/log"; mkdir -p "$tlog"
    log="$tlog/${corpus}_${subset}.log"
    # The config lives IN the cell it describes, beside the hyp it produces
    # and the scores of that hyp; gen_config.py picks the path itself.
    cfg="$tdir/en/$corpus/$subset/origin/config.yaml"

    if ! "$PY" "$HERE/gen_config.py" --corpus "$corpus" --subset "$subset" \
         --tools "$tool" ${FABENCH_DEVICE:+--device "$FABENCH_DEVICE"} \
         > "$log" 2>&1; then
      echo "[SKIP] $tag -- config generation failed (see $log)"
      printf '%s\t%s\t%s\tCONFIG_FAIL\t0\n' "$corpus" "$subset" "$tool" >> "$SUMMARY"
      continue
    fi

    echo "[RUN ] $tag"
    t0=$SECONDS
    # Thread pinning comes from env.sh (FABENCH_THREADS), exported above.
    if "$PY" -m fabench run --config "$cfg" >> "$log" 2>&1; then
      # Exit 0 is NOT sufficient. Per-item aligner failures are caught and
      # logged, so a tool that fails on every single utterance still exits 0
      # and writes an EMPTY hypothesis file -- whisperx did exactly this
      # across all five cells (a float64/float32 mismatch) and was recorded as
      # OK. Check the run actually produced records.
      hyp="$HERE/$kind/$tool/en/$corpus/$subset/hyp.jsonl"
      if [ ! -s "$hyp" ]; then
        echo "[EMPTY] $tag  ($((SECONDS - t0))s) -- ran, but produced 0 records; see $log"
        printf '%s\t%s\t%s\tEMPTY\t%d\n' "$corpus" "$subset" "$tool" $((SECONDS - t0)) >> "$SUMMARY"
        continue
      fi
      echo "[ OK ] $tag  ($((SECONDS - t0))s, $(wc -l < "$hyp") records)"
      printf '%s\t%s\t%s\tOK\t%d\n' "$corpus" "$subset" "$tool" $((SECONDS - t0)) >> "$SUMMARY"
    else
      echo "[FAIL] $tag  ($((SECONDS - t0))s) -- see $log"
      printf '%s\t%s\t%s\tFAIL\t%d\n' "$corpus" "$subset" "$tool" $((SECONDS - t0)) >> "$SUMMARY"
    fi
  done
done
fi   # stage 1

# --- stage 2: the same cells over noise-augmented audio ---------------------
if [ ${stage} -le 2 ] && [ ${stop_stage} -ge 2 ] && [ "${use_noisy_dataset}" = true ]; then
  echo "=== stage 2: align, noisy ==="
  "$PY" "$HERE/gen_noisy_configs.py" --tools "${TOOLS[@]}" || \
    echo "[SKIP] stage 2 -- no noisy configs generated"
  "$HERE/run_noisy_evals.sh" "${TOOLS[@]}"
elif [ ${stage} -le 2 ] && [ ${stop_stage} -ge 2 ]; then
  echo "=== stage 2: skipped (pass --use-noisy-dataset to include noisy audio) ==="
fi

# --- stage 3: score from the saved hypotheses ------------------------------
if [ ${stage} -le 3 ] && [ ${stop_stage} -ge 3 ]; then
  echo "=== stage 3: score -> summary/<kind>/<tool>/<lang>/<corpus>/<cell> ==="
  # Walk each tool's cells. A cell config already names its own directory as
  # results_dir, so scoring writes beside the hyp it scored and there is no
  # rewritten `.stage3.yaml` copy to build first -- that file existed only
  # because the config used to point at the cross-tool tree.
  for tool in "${TOOLS[@]}"; do
   tdir=$("$PY" -c "from fabench.paths import tool_dir; from pathlib import Path; print(tool_dir(Path('$ROOT'), '$tool'))" 2>/dev/null) || continue
   for cfg in "$tdir"/en/*/*/*/config.yaml; do
    [ -f "$cfg" ] || continue
    cell=$(dirname "$cfg"); cell=${cell#"$tdir/en/"}
    if "$PY" -m fabench score --config "$cfg" >> "$RUNLOG/score.log" 2>&1; then
      echo "[ OK ] scored $tool/$cell"
    else
      echo "[FAIL] score $tool/$cell -- see $RUNLOG/score.log"
    fi
   done
  done
fi

echo
echo "=== sweep complete ==="
column -t "$SUMMARY" 2>/dev/null || cat "$SUMMARY"
