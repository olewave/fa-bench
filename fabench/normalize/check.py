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

"""`fabench normalize-check` (Plan S2 acceptance).

For each enabled gold corpus, ingest (or load cached) canonical utterances,
collect every phone label, and report the unmapped-label rate. Fails (returns
nonzero) if any corpus exceeds ``normalize.max_unmapped_rate``. Unmapped labels
are listed, never silently dropped.
"""

from __future__ import annotations

import sys

from fabench.config import load_config
from fabench.normalize import unmapped_rate

# corpus name -> normalization source key
_CORPUS_SOURCE = {"timit": "timit", "buckeye": "buckeye", "l2arctic": "l2arctic"}


def cmd_normalize_check(args) -> int:
    cfg = load_config(args.config)
    threshold = float(cfg.normalize.get("max_unmapped_rate", 0.01))
    from fabench.dataprep.datasets import ingest_corpus

    any_fail = False
    print(f"normalize-check (canonical={cfg.normalize.get('canonical')}, "
          f"max_unmapped_rate={threshold:.3%})")
    for corpus, _spec in cfg.enabled_gold():
        source = _CORPUS_SOURCE.get(corpus, corpus)
        try:
            utts = ingest_corpus(corpus, cfg)
        except FileNotFoundError as e:
            print(f"  {corpus:10s}: NOT STAGED — {e}", file=sys.stderr)
            any_fail = True
            continue
        labels = [p.label for u in utts for p in u.phones]
        rate, unmapped = unmapped_rate(labels, source)
        status = "OK " if rate <= threshold else "FAIL"
        if rate > threshold:
            any_fail = True
        print(
            f"  [{status}] {corpus:10s} src={source:9s} "
            f"phones={len(labels):7d} unmapped={sum(unmapped.values()):5d} "
            f"({rate:.3%})"
        )
        if unmapped:
            top = ", ".join(f"{lab}={n}" for lab, n in unmapped.most_common(15))
            print(f"           unmapped labels: {top}")
    return 1 if any_fail else 0
