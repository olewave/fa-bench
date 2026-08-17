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

"""Buckeye acquisition notice and layout check.

THE BUCKEYE CORPUS REQUIRES PERMISSION FROM OHIO STATE UNIVERSITY. It is free
of charge, but not open access: you agree to OSU's terms and they release the
download. There is no fee and no LDC involvement -- the gate is the agreement,
not money.

Research use is permitted under that agreement; redistribution is not.
"""
import sys
from pathlib import Path

# search upward rather than counting parents -- this tree has moved once already
for _d in Path(__file__).resolve().parents:
    if (_d / 'fabench').is_dir():
        sys.path.insert(0, str(_d)); break
from fabench.dataprep.datasets.acquire import Corpus, Probe, cli

BUCKEYE = Corpus(
    name="Buckeye",
    holder="Department of Psychology, Ohio State University",
    url="https://buckeyecorpus.osu.edu/",
    access=("PERMISSION REQUIRED FROM OSU. Free of charge, but you must "
            "register and accept the corpus agreement at the URL above before "
            "OSU releases the download. No fee."),
    licence=("Research use under OSU's agreement. Redistribution prohibited -- "
             "do not commit Buckeye audio or .words/.phones files."),
    citation=("Pitt, M.A., Dilley, L., Johnson, K., Kiesling, S., Raymond, W., "
              "Hume, E. and Fosler-Lussier, E. (2007) Buckeye Corpus of "
              "Conversational Speech (2nd release). Columbus, OH: Department "
              "of Psychology, Ohio State University."),
    layout="""
OSU ships NESTED ZIPS, so there are two roots and they are not the same dir:

  distribution   <dist>/Buckeye/s01.zip ... s40.zip
  EXTRACTED      <root>/s01/s0101a.phones     <- point the config HERE
                 <root>/s01/s0101a.words
                 <root>/s01/s0101a.wav        the ~10 min interview track

Note the extracted depth is sNN/sNNNNx.phones (TWO levels). Some docs show
sNN/sNNNNx/sNNNNx.phones; the processor rglobs, so either works.
""",
    probes=(
        Probe("*.phones", "phone gold files", 200),
        Probe("*.words", "word gold files", 200),
    ),
    roots=("Buckeye", "buckeye"),
)

if __name__ == "__main__":
    raise SystemExit(cli(BUCKEYE))
