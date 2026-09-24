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

# CrisperWhisper (Interspeech 2024) -- ASR WITH WORD TIMESTAMPS.
#   Zusag, Wagner & Thallinger, DOI 10.21437/Interspeech.2024-731, arXiv:2408.16589
#   https://github.com/nyrahealth/CrisperWhisper
#
# Lives in timestamp_asrs, NOT aligners: it takes audio only and decodes its own
# transcript, so its rows mix recognition error with timing error.
#
# Own venv + its own interpreter at run time. Mixing two site-packages in one
# process fails on native extensions -- qwen3_fa proved that (cffi 2.1.1 python
# vs _cffi_backend 2.1.0 .so). torch pinned to cu128: the host driver is 12.9, and
# a cu130 wheel loads but reports cuda.is_available() == False.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODEL=${MODEL:-nyrahealth/CrisperWhisper}
# Re-runnable: a failed or partial install leaves the venv behind, and
# `uv venv` then refuses to touch it -- so the recipe could not be retried
# without deleting a directory the error never names. Reuse a venv that
# already has an interpreter; the pip installs below are idempotent.
[ -x "$HERE/venv/bin/python" ] || uv venv "$HERE/venv" --python 3.12
uv pip install --python "$HERE/venv/bin/python" torch==2.8.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple
# transformers VERSION PINNED: CrisperWhisper's timestamps come out of the
# model's attention, so the transformers release is part of the measurement,
# not an implementation detail. >=4.40 floated and would drift. This is the
# version in requirements.lock, i.e. what produced the published numbers.
uv pip install --python "$HERE/venv/bin/python" "transformers==4.57.6" accelerate soundfile librosa
# INSTALL FROM THE LOCK, not from a hand-kept list. The two had drifted: the
# lock pinned 75 packages and the explicit installs produced 62, so a fresh
# checkout was missing crisperwhisper itself and ctranslate2, and died at
# `from crisperwhisper import CrisperWhisperModel` and then inside it. The
# machine that produced the published numbers had them from manual installs
# that the recipe never captured. The lock is the record of that environment;
# installing anything else guarantees the drift returns.
uv pip install --python "$HERE/venv/bin/python" -r "$HERE/requirements.lock"
"$HERE/venv/bin/python" - <<PY
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
# Import what the WORKER imports. Checking torch and transformers said "ok"
# while the module the worker needs was missing entirely.
from crisperwhisper import CrisperWhisperModel  # noqa: F401
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
m="$MODEL"; AutoProcessor.from_pretrained(m); AutoModelForSpeechSeq2Seq.from_pretrained(m, low_cpu_mem_usage=True)
print("crisperwhisper ok")
PY
