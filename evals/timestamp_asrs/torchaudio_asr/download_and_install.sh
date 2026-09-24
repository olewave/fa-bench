#!/usr/bin/env bash
# No install of its own: this row reuses evals/aligners/torchaudio_fa/venv,
# which already pins torch/torchaudio and is the environment whose numbers are
# published for the track-1 TorchAudio row. Sharing it keeps the two rows on
# identical software, which is the point of running them as a pair.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SHARED="$HERE/../../aligners/torchaudio_fa"
[ -x "$SHARED/venv/bin/python" ] || { echo "run $SHARED/download_and_install.sh first" >&2; exit 1; }
echo "reusing: $("$SHARED/venv/bin/python" -c 'import torch,torchaudio;print("torch",torch.__version__,"torchaudio",torchaudio.__version__)')"
