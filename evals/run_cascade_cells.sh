#!/usr/bin/env bash
# Run cascade cells from their PER-CELL configs, pinned to one GPU.
#
# TWO THINGS THIS GETS RIGHT that run_evals.sh did not, for a cascade:
#
# 1. run_evals.sh stage 1 builds its config from the tool's TOP-LEVEL recipe,
#    which carries no params.transcript_hyp; the aligner refuses it by design and
#    every clean cell failed in under 4s. The per-cell configs that
#    gen_cascade_configs.py writes are the only correct input.
#
# 2. FABENCH_DEVICE is NOT read at runtime. run_evals.sh passes it as
#    `gen_config.py --device`, which writes params.device into the config it
#    generates -- and gen_cascade_configs.py writes no device key at all. Set as
#    an environment variable it does nothing, so every worker fell back to the
#    same default card and they OOMed fighting over it while the cards they were
#    supposed to be on sat at 20 MiB. The device is therefore injected into a
#    temp copy of each config here, which is the only thing the runtime reads.
#
#   run_cascade_cells.sh <cuda:N> <config> [config ...]
set -uo pipefail
exec < /dev/null
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PY="$ROOT/.venv/bin/python"
DEV="$1"; shift
LOG="$ROOT/evals/log/casc_${DEV//:/}.log"
ok=0; fail=0
for cfg in "$@"; do
  cell=$(echo "$cfg" | sed -E 's|.*/en/||; s|/config.yaml$||')
  tool=$(echo "$cfg" | sed -E 's|.*/timestamp_asrs/([^/]*)/.*|\1|')
  # BESIDE the original, not in /tmp: the runtime resolves the config's
  # repo-relative paths (params.transcript_hyp, the aligner recipes) against the
  # config's own location, so a copy in /tmp turns "evals/aligners" into
  # "/evals/aligners" and the cell dies with PermissionError on /evals.
  tmp="${cfg%.yaml}.dev_${DEV//:/}.yaml"
  "$PY" - "$ROOT/$cfg" "$DEV" "$tmp" <<'PYEOF'
import sys, yaml
src, dev, out = sys.argv[1:4]
idx = dev.split(":")[-1]
c = yaml.safe_load(open(src))
for e in c.get("aligners", []):
    p = e.setdefault("params", {})
    # 3. params.device is not enough either. CrisperWhisper builds its model
    #    with device="auto" and never reads it, so accelerate chose the card:
    #    a 24 GB 4090 already holding two ollama servers. Every item came back
    #    "CUDA out of memory" -- 400/400 -- while the Blackwell the worker was
    #    assigned sat idle. Pin the card in the environment, which no worker
    #    can override, and then cuda:0 is the only device there is.
    p["device"] = "cuda:0"
    p.setdefault("env", {})["CUDA_VISIBLE_DEVICES"] = idx
yaml.safe_dump(c, open(out, "w"), sort_keys=False)
PYEOF
  t0=$SECONDS
  if "$PY" -m fabench run --config "$tmp" >> "$LOG" 2>&1; then
    echo "[ ok ] $tool $cell ($((SECONDS-t0))s)"; ok=$((ok+1))
  else
    echo "[fail] $tool $cell ($((SECONDS-t0))s)"; fail=$((fail+1))
  fi
  rm -f "$tmp"
done
echo "== $DEV done: $ok ok, $fail failed"
