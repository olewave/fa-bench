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

# Unattended babysitter: finish what is running, sweep what becomes ready,
# refresh the tables, and record everything. Safe to leave alone.
#
# DELIBERATELY EXCLUDED (needs a judgement call, not a retry):
#   * converting bfa/whisperx to isolated venvs -- that INVALIDATES their
#     current numbers and forces a re-sweep, which should not happen while
#     nobody is watching;
#   * anything that rewrites docs/*.md.
#
# Everything here either produces new data or regenerates derived tables, so a
# failure costs time, never results.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$(dirname "$HERE")"
LOG="$HERE/log/overnight.log"; mkdir -p "$HERE/log"
say() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

refresh() { ./evals/rescore_all.sh >>"$LOG" 2>&1; }

say "=== overnight start ==="

# 1. wait out whatever is sweeping now
while pgrep -f "run_evals.sh" >/dev/null; do sleep 120; done
say "running sweeps finished"; refresh; say "tables refreshed"

# 2. retry any cell that ended EMPTY or FAIL, once per tool
for kind in aligners timestamp_asrs; do
  for d in evals/$kind/*/; do
    t=$(basename "$d"); log="$d/log/sweep.log"
    [ -f "$log" ] || continue
    if grep -qE '^\[(FAIL|EMPTY)\]' "$log"; then
      say "retrying $t (had FAIL/EMPTY)"
      mkdir -p "$d/log"
      ./evals/run_evals.sh "$t" > "$d/log/sweep.retry.log" 2>&1
      say "  $t retry: $(grep -cE '^\[ OK \]' "$d/log/sweep.retry.log") ok, $(grep -cE '^\[(FAIL|EMPTY)\]' "$d/log/sweep.retry.log") bad"
    fi
  done
done
refresh; say "tables refreshed after retries"

# 3. parakeet: sweep as soon as its install lands (NeMo resolution is slow)
for _ in $(seq 1 90); do
  grep -q "parakeet_tdt ok" evals/timestamp_asrs/parakeet_tdt/install.log 2>/dev/null && break
  pgrep -f "parakeet_tdt/download_and_install" >/dev/null || break
  sleep 120
done
if grep -q "parakeet_tdt ok" evals/timestamp_asrs/parakeet_tdt/install.log 2>/dev/null; then
  say "parakeet installed; sweeping"
  mkdir -p evals/timestamp_asrs/parakeet_tdt/log
  ./evals/run_evals.sh parakeet_tdt > evals/timestamp_asrs/parakeet_tdt/log/sweep.log 2>&1
  say "  parakeet: $(grep -cE '^\[ OK \]' evals/timestamp_asrs/parakeet_tdt/log/sweep.log) ok"
  refresh
else
  say "parakeet install did NOT complete -- left for morning"
fi

say "=== final state ==="
for kind in aligners timestamp_asrs; do
  for d in evals/$kind/*/; do
    t=$(basename "$d"); log="$d/log/sweep.log"
    [ -f "$log" ] || continue
    say "  $(printf '%-18s' "$t") ok=$(grep -cE '^\[ OK \]' "$log") bad=$(grep -cE '^\[(FAIL|EMPTY)\]' "$log")"
  done
done
say "empty hyp files: $(find evals/*/*/en -name hyp.jsonl -empty 2>/dev/null | wc -l)"
say "=== overnight done ==="

# ---- noise build + model retrain (appended) -------------------------------
# Runs after the sweeps. Both produce NEW data; neither touches existing results.
say "waiting on noise build"
while pgrep -f "make_noisy.sh" >/dev/null; do sleep 300; done
say "noise build finished: $(grep -c 'ok, 0 failed' fabench/dataprep/noisemix/build.log) clean stages, $(grep -c 'failed' fabench/dataprep/noisemix/build.log) lines mentioning failure"
for c in TIMIT Buckeye; do
  for t in reverb noise music babble; do
    say "  $c/$t: $(ls /scratch/data/speech/english/$c/noisy/$t 2>/dev/null | wc -l) files"
  done
done
say "=== overnight (with noise) done ==="
