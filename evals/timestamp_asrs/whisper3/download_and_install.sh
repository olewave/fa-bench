#!/usr/bin/env bash
# Whisper large-v3 in its own venv, via HF transformers.
# PIP_CONFIG_FILE is neutralised: see the note in qwen3_asr's installer.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV="$HERE/venv"
export PIP_CONFIG_FILE=/dev/null
PIPI="--index-url https://pypi.org/simple"
rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q $PIPI --upgrade pip
"$VENV/bin/pip" install -q $PIPI transformers torch accelerate soundfile librosa
"$VENV/bin/pip" freeze > "$HERE/requirements.observed"
echo "installed: $("$VENV/bin/python" -c 'import transformers,torch;print("transformers",transformers.__version__,"torch",torch.__version__)')"
