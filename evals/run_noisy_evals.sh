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

# Sweep the noise-augmented conditions over the held-out cells.
#
# One fabench run per generated noisy_<cond>_<corpus>_<subset>_<tool>.yaml.
# Same reasoning as run_evals.sh: one invocation per (cell, tool, condition) so
# a dying adapter cannot take the rest down, and a failure is RECORDED rather
# than aborting the sweep.
#
# Results land beside the clean ones, not on top of them:
#   clean  evals/<kind>/<tool>/en/<corpus>/<subset>/hyp.jsonl
#   noisy  evals/<kind>/<tool>/en/<corpus>/<subset>__<cond>/hyp.jsonl
# via `condition_tag:` in each config -- without it every noisy run overwrote
# the clean baseline, since the configs carry the tool's real name.
#
# Usage: ./run_noisy_evals.sh [tool ...]      (default: every generated config)
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")
PY="$ROOT/.venv/bin/python"
cd "$ROOT"
. "$HERE/env.sh"   # GPU + thread knobs, one place (FABENCH_CUDA_DEVICES, FABENCH_THREADS)

# Run STATUS, not a result: which cells ran, how long they took, how many
# records came back. That is orchestration, so it belongs beside its sibling
# from run_evals.sh (evals/log/summary.tsv) rather than in summary/, which
# holds derived MEASUREMENTS. It is also machine-specific -- `seconds` is this
# box's wall clock -- and append-only across runs, so it is gitignored with the
# rest of evals/log/.
SUMMARY="$ROOT/evals/log/noisy_sweep_summary.tsv"
mkdir -p "$(dirname "$SUMMARY")"
[ -f "$SUMMARY" ] || printf 'condition\tcorpus\tsubset\ttool\tstatus\tseconds\trecords\n' > "$SUMMARY"

# Noisy cells live with their tool now (evals/<kind>/<tool>/configs/), including
# nested recipes at <tool>/exps/<name>/ and <tool>/v<version>/, so collect by
# walking rather than listing one flat directory.
#
# Selection reads the tool from EACH CONFIG, the same source of truth the loop
# below uses. Neither the filename nor the directory name is safe: names and
# subsets both contain underscores (parakeet_tdt, core_test), and a nested
# recipe's directory is `olign/exps/noisy` while the name it declares is
# `olign_noisy`.
mapfile -t CFGS < <("$PY" - "$@" <<'EOF'
import sys, yaml
from pathlib import Path
want = set(sys.argv[1:])
out = []
for base in ("evals/aligners", "evals/timestamp_asrs"):
    for p in Path(base).glob("**/configs/noisy_*.yaml"):
        try:
            c = yaml.safe_load(p.read_text()) or {}
            tool = next(a["name"] for a in c.get("aligners", []) if a.get("enabled", True))
        except (yaml.YAMLError, OSError, StopIteration, KeyError):
            continue
        if not want or tool in want:
            out.append(str(p))
print("\n".join(sorted(out)))
EOF
)
echo "== ${#CFGS[@]} noisy cells"

for cfg in "${CFGS[@]}"; do
  base=$(basename "$cfg" .yaml)
  # Read the fields FROM THE CONFIG, not the filename. Splitting
  # noisy_<cond>_<corpus>_<subset>_<tool> on "_" is ambiguous because both
  # tools (parakeet_tdt, crisperwhisper_fa, qwen3_fa) and subsets (core_test,
  # full_test) contain underscores -- it parsed
  # noisy_babble_buckeye_test_parakeet_tdt as tool=tdt, subset=test_parakeet.
  read -r cond corpus subset tool < <("$PY" - "$cfg" <<'EOF'
import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
gold = c["datasets"]["gold"]
corpus = next(k for k, v in gold.items() if isinstance(v, dict) and v.get("enabled"))
tool = next(a["name"] for a in c["aligners"] if a.get("enabled", True))
print(c.get("condition_tag", ""), corpus, gold[corpus].get("subset", ""), tool)
EOF
)
  [ -n "$tool" ] || { echo "[SKIP] $base -- could not read config"; continue; }

  # Resolve the tool's directory from the shared index rather than assuming
  # evals/<kind>/<tool>/: a nested recipe lives at <tool>/exps/<name>/, so the
  # assumed path does not exist and every hyp check silently reported "missing".
  tdir=$("$PY" -c "from fabench.paths import tool_dir; from pathlib import Path; print(tool_dir(Path('$ROOT'), '$tool'))" 2>/dev/null) || tdir=""
  [ -n "$tdir" ] || { echo "[SKIP] $base -- unknown tool $tool"; continue; }
  hyp="$tdir/en/$corpus/${subset}__${cond}/hyp.jsonl"
  if [ -s "$hyp" ]; then
    echo "[SKIP] $base -- already has $(wc -l < "$hyp") records"; continue
  fi

  tlog="$tdir/log"; mkdir -p "$tlog"
  log="$tlog/noisy_${cond}_${corpus}_${subset}.log"
  echo "[RUN ] $base"
  t0=$SECONDS
  # OMP pinned to 1: without it each adapter spreads across all 48 cores and the
  # box thrashes -- measured 40x throughput loss.
  if \
     "$PY" -m fabench run --config "$cfg" > "$log" 2>&1; then
    n=$([ -s "$hyp" ] && wc -l < "$hyp" || echo 0)
    if [ "$n" -eq 0 ]; then
      echo "[EMPTY] $base ($((SECONDS-t0))s) -- ran but 0 records; see $log"
      printf '%s\t%s\t%s\t%s\tEMPTY\t%d\t0\n' "$cond" "$corpus" "$subset" "$tool" $((SECONDS-t0)) >> "$SUMMARY"
    else
      echo "[ OK  ] $base ($((SECONDS-t0))s, $n records)"
      printf '%s\t%s\t%s\t%s\tOK\t%d\t%d\n' "$cond" "$corpus" "$subset" "$tool" $((SECONDS-t0)) "$n" >> "$SUMMARY"
    fi
  else
    echo "[FAIL ] $base ($((SECONDS-t0))s) -- see $log"
    printf '%s\t%s\t%s\t%s\tFAIL\t%d\t0\n' "$cond" "$corpus" "$subset" "$tool" $((SECONDS-t0)) >> "$SUMMARY"
  fi
done
echo "NOISY_SWEEP_DONE -- summary: $SUMMARY"
