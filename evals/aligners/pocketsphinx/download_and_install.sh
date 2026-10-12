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

# PocketSphinx for FA-Bench -- PRIVATE venv, built from the GitHub source.
#
# FROM GITHUB, NOT PYPI. The last release, v5.1.1 (2026-06-06), predates the
# alignment fixes on the main branch: a two-pass phone alignment, the end-frame
# boundary in the state alignment search, the frame a successor phone starts
# on, and bestpath turned off for the alignment search. Those move boundaries,
# which is what this benchmark measures, so the row is built from a pinned
# commit of github.com/cmusphinx/pocketsphinx rather than the wheel.
#
# The checkout also carries the default US English model and CMUdict, so the
# acoustic model and dictionary are the ones that commit ships.
#
# g2p_en supplies pronunciations for words CMUdict lacks, the same G2P and
# version the MAPS adapter uses. Pinned to what the shared .venv carries.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REV=${REV:-f20ff1b7a5db64c5e892a798479e20df86e79a35}
SRC="$HERE/repo/pocketsphinx"
VENV="$HERE/venv"

[ -d "$SRC/.git" ] || git clone https://github.com/cmusphinx/pocketsphinx.git "$SRC"
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet "$REV"

uv venv "$VENV" --python 3.12
# Builds the C library and the Cython module from the checkout.
uv pip install --python "$VENV/bin/python" "$SRC"
uv pip install --python "$VENV/bin/python" \
    g2p-en==2.1.0 nltk==3.10.3 inflect==7.5.0 distance==0.1.3 \
    numpy==2.5.1 soundfile==0.14.0 scipy==1.18.0

"$VENV/bin/python" - <<PY
import pocketsphinx
from pocketsphinx import Decoder
print("pocketsphinx", pocketsphinx.__file__)
print("model", pocketsphinx.get_model_path())
d = Decoder(bestpath=False, lm=None)
print("cmudict 'the':", d.lookup_word("the"))
from g2p_en import G2p
print("g2p_en 'yknow':", G2p()("yknow"))
print("pocketsphinx ok")
PY
# The source build freezes as a local file:// path. Name the commit instead.
uv pip freeze --python "$VENV/bin/python" \
    | sed "s|^pocketsphinx @ .*|pocketsphinx @ git+https://github.com/cmusphinx/pocketsphinx@$REV|" \
    > "$HERE/requirements.lock"
