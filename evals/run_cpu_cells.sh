#!/usr/bin/env bash
# Run cells on CPU, one fabench invocation each.
#
# NOT run_cascade_cells.sh: that injects params.device=cuda:N, and unity2 must
# stay on CPU -- fairseq2 0.2.* is built against cu121, which has no kernels for
# this box's Blackwell cards.
set -uo pipefail
exec < /dev/null
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PY="$ROOT/.venv/bin/python"
TAG="$1"; shift
LOG="$ROOT/evals/log/cpu_${TAG}.log"
ok=0; fail=0
for cfg in "$@"; do
  cell=$(echo "$cfg" | sed -E 's|.*/en/||; s|/config.yaml$||')
  tool=$(echo "$cfg" | sed -E 's|.*/(aligners|timestamp_asrs)/([^/]*)/.*|\2|')
  t0=$SECONDS
  if "$PY" -m fabench run --config "$cfg" >> "$LOG" 2>&1; then
    echo "[ ok ] $tool $cell ($((SECONDS-t0))s)"; ok=$((ok+1))
  else
    echo "[fail] $tool $cell ($((SECONDS-t0))s)"; fail=$((fail+1))
  fi
done
echo "== $TAG done: $ok ok, $fail failed"
