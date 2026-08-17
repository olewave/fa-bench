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

# Sweep several aligners CONCURRENTLY, one GPU each.
#
#   run_evals_parallel.sh <tool>:<gpu> [<tool>:<gpu> ...]
#   e.g.  run_evals_parallel.sh whisperx:1 bfa:2 charsiu:3
#
# The tools are independent -- separate processes, separate models, separate
# result cells -- so sweeping them one after another only ever wasted wall
# clock. They were serialised earlier because every sweep was pinned to GPU 0
# while the other cards were doing training; that reason is gone.
#
# MEMORY. A tool eval needs ~1 GB (measured: BFA 866 MiB). A kaldi
# nnet3-compute scoring job on the same card takes ~21.7 GB and has no
# memory-cap flag, leaving ~2.8 GB -- enough for one tool alongside it. Kaldi
# allocates up front, so a tool that wants more than the remainder fails
# ITSELF rather than disturbing the scoring job. That makes this safe to run
# while the scoring matrix is going; a failed cell is recorded and retried.
#
# Each tool's sweep is the existing run_evals.sh, so per-cell isolation and the
# summary.tsv accounting are unchanged. Run evals/rescore_all.sh afterwards --
# per-tool runs each rewrite a cell's report.md with only their own row.
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")
cd "$ROOT"

[ $# -gt 0 ] || { echo "usage: $0 <tool>:<gpu> [...]" >&2; exit 1; }

pids=()
for spec in "$@"; do
  tool=${spec%%:*}; gpu=${spec##*:}
  [ -f "$HERE/aligners/$tool/config.yaml" ] || { echo "[skip] $tool -- no evals/aligners/$tool/config.yaml"; continue; }
  mkdir -p "$HERE/aligners/$tool/log"
  echo "[start] $tool on cuda:$gpu"
  # All four cards stay VISIBLE; the tool is bound to one by index. Hiding the
  # others would also renumber them, so a config saying cuda:2 would silently
  # mean a different physical card depending on who launched it.
  FABENCH_DEVICE="cuda:$gpu" \
      "$HERE/run_evals.sh" "$tool" > "$HERE/aligners/$tool/log/sweep.log" 2>&1 &
  pids+=($!)
done

rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done

echo
for spec in "$@"; do
  tool=${spec%%:*}
  log="$HERE/aligners/$tool/log/sweep.log"
  [ -f "$log" ] && echo "  $tool: $(grep -cE '^\[ OK \]' "$log") ok, $(grep -cE '^\[FAIL\]' "$log") failed"
done
echo PARALLEL_SWEEPS_DONE
exit $rc
