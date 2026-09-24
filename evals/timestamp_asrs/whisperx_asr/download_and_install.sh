#!/usr/bin/env bash
# whisperx_asr reuses the track-1 whisperx environment: it is the same package,
# run in a different configuration, and a second copy would cost 7.2 GB to hold
# byte-identical wheels. Nothing to install here -- but say so explicitly rather
# than exiting 0 silently, because "no output" and "already done" look alike.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV=$(cd "$HERE/../../aligners/whisperx" && pwd)/venv
if [ ! -x "$VENV/bin/python" ]; then
  echo "whisperx_asr needs the track-1 whisperx environment, which is missing." >&2
  echo "Install it first:  evals/aligners/whisperx/download_and_install.sh" >&2
  exit 1
fi
"$VENV/bin/python" - <<'PY'
import torch, whisperx
print("whisperx_asr ok | whisperx", getattr(whisperx, "__version__", "?"),
      "| torch", torch.__version__, "| cuda", torch.cuda.is_available())
PY
