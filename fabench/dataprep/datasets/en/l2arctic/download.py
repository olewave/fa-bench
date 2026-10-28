#!/usr/bin/env python3
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
