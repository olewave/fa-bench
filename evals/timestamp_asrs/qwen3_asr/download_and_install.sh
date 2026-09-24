#!/usr/bin/env bash
# Qwen3-ASR-1.7B in its own venv.
#
# The `qwen-asr` package pulls its own torch. It is kept out of the shared
# .venv for the reason every other tool here is: one tool's install must not
# move another tool's already-measured numbers.
#
# `return_time_stamps=True` also downloads Qwen3-ForcedAligner-0.6B, so the
# first run fetches two checkpoints, not one.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV="$HERE/venv"

# Ignore any machine-level pip.conf. On at least one host here NVIDIA PyIndex
# had written an extra-index-url pointing at pypi.ngc.nvidia.com, which no
# longer resolves, so every install burned five DNS retries per package before
# falling back. Pinning the index makes the recipe reproducible across machines
# instead of inheriting whatever a host happens to be configured with.
export PIP_CONFIG_FILE=/dev/null
PIPI="--index-url https://pypi.org/simple"

rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q $PIPI --upgrade pip
"$VENV/bin/pip" install -q $PIPI "qwen-asr" soundfile
"$VENV/bin/pip" freeze > "$HERE/requirements.observed"
echo "installed: $("$VENV/bin/python" -c 'import qwen_asr,torch;print("qwen-asr",getattr(qwen_asr,"__version__","?"),"torch",torch.__version__)')"
