#!/usr/bin/env python3
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

"""L2-ARCTIC acquisition notice and layout check.

L2-ARCTIC is free for research but REQUEST-GATED: fill in the form at Texas
A&M's PSI lab page and they send the download link. No fee, no LDC.
"""
import sys
from pathlib import Path

# search upward rather than counting parents -- this tree has moved once already
for _d in Path(__file__).resolve().parents:
    if (_d / 'fabench').is_dir():
        sys.path.insert(0, str(_d)); break
from fabench.dataprep.datasets.acquire import Corpus, Probe, cli

L2ARCTIC = Corpus(
    name="L2-ARCTIC",
    holder="Perception, Sensing and Instrumentation Lab, Texas A&M University",
    url="https://psi.engr.tamu.edu/l2-arctic-corpus/",
    access=("REQUEST FORM. Free for research use; complete the form at the URL "
            "above and the download link is sent to you. No fee."),
    licence=("Research use. Check the terms you accept on the request form "
             "before redistributing anything derived from it."),
    citation=("Zhao, G., Sonsaat, S., Silpachai, A., Lucic, I., "
              "Chukharev-Hudilainen, E., Levis, J. and Gutierrez-Osuna, R. "
              "(2018) L2-ARCTIC: A Non-native English Speech Corpus. "
              "Interspeech 2018."),
    layout="""
<root>/ABA/annotation/arctic_a0001.TextGrid   hand-corrected gold (subset only)
<root>/ABA/wav/arctic_a0001.wav               audio
...                                           one folder per L2 speaker
""",
    probes=(
        Probe("annotation/*.TextGrid", "hand-corrected TextGrids", 10),
        Probe("wav/*.wav", "audio files", 100),
    ),
    roots=("l2arctic", "L2-ARCTIC", "l2arctic_release_v5.0"),
)

if __name__ == "__main__":
    raise SystemExit(cli(L2ARCTIC))
