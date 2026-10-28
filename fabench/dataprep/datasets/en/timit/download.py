#!/usr/bin/env python3
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""TIMIT acquisition notice and layout check.

TIMIT IS NOT FREE AND CANNOT BE DOWNLOADED HERE. It is sold by the Linguistic
Data Consortium as catalog item LDC93S1. Non-members pay a fee; many
universities already hold it under an LDC membership, so check with your
library or lab before buying a second copy.

Copies circulate on public mirrors. Using one does not grant you a licence,
and FA-Bench will not fetch from them.
"""
import sys
from pathlib import Path

# search upward rather than counting parents -- this tree has moved once already
for _d in Path(__file__).resolve().parents:
    if (_d / 'fabench').is_dir():
        sys.path.insert(0, str(_d)); break
from fabench.dataprep.datasets.acquire import Corpus, Probe, cli

TIMIT = Corpus(
    name="TIMIT",
    catalog_id="LDC93S1  (Linguistic Data Consortium)",
    holder="Linguistic Data Consortium, University of Pennsylvania",
    url="https://catalog.ldc.upenn.edu/LDC93S1",
    access=("PAID LICENCE. Order from the LDC catalog page; a fee applies to "
            "non-members and current pricing is on that page. If your "
            "institution is an LDC member you may already have access."),
    licence=("Redistribution prohibited. Do not commit TIMIT audio or its "
             ".PHN/.WRD annotations to this or any repository."),
    citation=("Garofolo, J. et al. (1993) TIMIT Acoustic-Phonetic Continuous "
              "Speech Corpus LDC93S1. Philadelphia: Linguistic Data Consortium."),
    layout="""
<root>/TRAIN/DR1/FCJF0/SA1.PHN     phone gold: start_sample end_sample label
<root>/TRAIN/DR1/FCJF0/SA1.WRD     word gold, same format
<root>/TRAIN/DR1/FCJF0/SA1.WAV     NIST SPHERE (or .wav / .WAV.wav if converted)
<root>/TEST/DR1/...                same, 8 dialect regions DR1-DR8
""",
    # Both case conventions ship in the wild; the processor accepts either.
    probes=(
        Probe("*.[Pp][Hh][Nn]", "phone gold files (.PHN)", 6000),
        Probe("*.[Ww][Rr][Dd]", "word gold files (.WRD)", 6000),
    ),
    roots=("TIMIT", "timit", "data", "TIMIT/TIMIT"),
)

if __name__ == "__main__":
    raise SystemExit(cli(TIMIT))
