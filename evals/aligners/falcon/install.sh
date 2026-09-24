#!/usr/bin/env bash
# FALCON (Rousso, Cohen & Keshet 2026) -- its own venv.
#
# python3.10, not the repo default: requirements.txt pins numpy 1.22.4, scipy
# 1.7.3, librosa 0.8.1 and hydra-core 0.11.3, none of which have wheels for
# 3.12. The pins are relaxed to a working set rather than followed literally --
# torch is the one that matters and it is kept at the pinned 2.4.1.
set -euo pipefail
# ~/.config/pip/pip.conf (written by NVIDIA PyIndex) carries an
# extra-index-url at pypi.ngc.nvidia.com that no longer resolves, and pip
# reports the failure against pypi itself as "Name or service not known".
# The other installers here bypass it the same way.
export PIP_CONFIG_FILE=/dev/null
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python3.10 -m venv "$HERE/venv"
"$HERE/venv/bin/pip" -q install --upgrade pip wheel
"$HERE/venv/bin/pip" -q install torch==2.4.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu121
"$HERE/venv/bin/pip" -q install "numpy<2" scipy scikit-learn librosa soundfile \
    "hydra-core==0.11.3" "omegaconf==1.4.1" torch-optimizer panphon dill boltons \
    matplotlib tqdm huggingface_hub TextGrid
"$HERE/venv/bin/python" - <<PY
from huggingface_hub import snapshot_download
p = snapshot_download("MLSpeech/FALCON-weights", local_dir="$HERE/repo/pretrained_models")
print("weights:", p)
PY
echo "install ok"
