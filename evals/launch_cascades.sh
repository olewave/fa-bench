#!/usr/bin/env bash
# Launch the two qwen3 cascades from their per-cell configs.
#
# ONLY the 96 GB cards. CrisperWhisper aligns a Buckeye cell as one 4,456-item
# corpus call, which a 24 GB 4090 cannot hold -- every cell sent to cuda:1 or
# cuda:5 died with CUDA OOM. Cards 0 and 2 carry other users' jobs but have
# 58 GB and 87 GB free respectively; 3 and 4 are idle.
#
# A cell already holding a non-empty hyp.jsonl is skipped, so this is safe to
# re-run after an interruption.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p evals/log
D=evals/run_cascade_cells.sh
CW=evals/timestamp_asrs/crisperwhisper_fa_on_qwen3asr
TA=evals/timestamp_asrs/torchaudio_fa_on_qwen3asr

todo () {  # print the configs of cells not yet done
  for c in $1; do
    [ -s "$(dirname "$c")/hyp.jsonl" ] || echo "$c"
  done
}
mapfile -t BUCK  < <(todo "$(ls -1 $CW/en/buckeye/*/*/config.yaml | sort)")
mapfile -t CWTIM < <(todo "$(ls -1 $CW/en/timit/*/*/config.yaml   | sort)")
mapfile -t TACEL < <(todo "$(ls -1 $TA/en/*/*/*/config.yaml       | sort)")
echo "  to run: ${#BUCK[@]} CW-buckeye, ${#CWTIM[@]} CW-timit, ${#TACEL[@]} torchaudio"

launch () { local n=$1 dev=$2; shift 2
  [ $# -eq 0 ] && { echo "  $n -> nothing to do"; return; }
  setsid nohup "$D" "$dev" "$@" > "evals/log/launch_${n}.log" 2>&1 < /dev/null &
  echo "  $n -> $dev, $# cells, pid $!"
}
launch cw_a cuda:3 "${BUCK[@]:0:4}"
launch cw_b cuda:4 "${BUCK[@]:4:3}" "${CWTIM[@]:0:5}"
launch cw_c cuda:2 "${BUCK[@]:7:3}" "${CWTIM[@]:5:5}"
launch ta   cuda:0 "${TACEL[@]}"
sleep 10
echo "=== alive ==="
pgrep -af run_cascade_cells.sh | grep -v pgrep | sed 's/\(.\{50\}\).*/  \1/'
