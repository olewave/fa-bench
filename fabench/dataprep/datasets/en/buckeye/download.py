#!/usr/bin/env python3
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
