#!/bin/bash
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

# BFA -- self-contained under evals/bfa/repo/
#   repo/env/   venv; pip package `bournemouth-forced-aligner`,
#               imports as `bournemouth_aligner`. Models auto-download from HF.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$HERE/repo; mkdir -p "$REPO"
[ -d "$REPO/env" ] || python3 -m venv "$REPO/env"
"$REPO/env/bin/pip" install -q --upgrade pip
# VERSION PINNED to what produced the published numbers (see the provenance
# table in results/README.md). Bumping it is a deliberate act: change the
# pin, re-run the sweep, regenerate provenance -- never let a fresh install
# silently measure a different release.
"$REPO/env/bin/pip" install -q bournemouth-forced-aligner==1.1.5
# torch arrives TRANSITIVELY here and resolves to 2.13.0+cu130 from PyPI,
# which does not work against this box's CUDA 12.9 driver --
# torch.cuda.is_available() returns False and the aligner silently runs on
# CPU. Re-pin it to the cu128 index afterwards; measured 2.8.0+cu128 gives
# cuda True. This is a reinstall-time regression, not a code change: the
#
# --force-reinstall AND an exact version are both required. Without them
# `pip install --index-url <cu128> torch` is a NO-OP when torch is already
# present: pip checks whether the requirement is satisfied, not which index
# it came from, so a cu130 build stays put and cuda stays False. Verified
# the hard way -- the un-forced form reported success and changed nothing.
# env worked until it was rebuilt.
"$REPO/env/bin/pip" install -q --force-reinstall --index-url https://download.pytorch.org/whl/cu128 \
    torch==2.8.0 torchaudio==2.8.0
"$REPO/env/bin/python" -c "
from bournemouth_aligner import PhonemeTimestampAligner
import bournemouth_aligner as m; print('  bournemouth_aligner', getattr(m,'__version__','?'))"
