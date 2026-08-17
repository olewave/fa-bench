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

"""Orchestration shared by the analysis scripts (silence_edge_split.py,
tail_stats.py): the aligner-run registry, the gold loader, and file-level error
extraction that loops the library extractors in :mod:`fabench.analyze.errors`
over a hyp JSONL.

The pure compute (splits, percentiles, decomposition) lives in
:mod:`fabench.analyze`; this module + the scripts are only orchestration and
CSV I/O. Run from the repo root (the system python's entry is broken — use the
project venv):
    .venv/bin/python -m fabench.analyze.silence_edge_split
    .venv/bin/python -m fabench.analyze.tail_stats_report
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from fabench.analyze.errors import (
    hyp_utt_from_record,
    phone_boundary_errors,
    word_boundary_errors,
)
from fabench.config import load_config
from fabench.dataprep.datasets import ingest_corpus
from fabench.normalize import make_canon
from fabench.schema import load_jsonl


def systems(corpus: str):
    """(name, hyp_path, has_phones) for every aligner run present for `corpus`.
    olign = post-edge-snap; qwen3 = word-only. Missing runs are skipped."""
    R = REPO / "summary"
    base = {"timit": "timit_full", "buckeye": "buckeye_paper"}[corpus]
    cand = [(a, R / base / "hyp" / f"{a}__{corpus}.jsonl", True)
            for a in ("mfa", "charsiu", "maps", "bfa")]
    cand.append(("olign", R / f"olign_probe_{corpus}" / "hyp" / f"olign__{corpus}.jsonl", True))
    cand.append(("qwen3", R / f"qwen3_{corpus}" / "hyp" / f"qwen3__{corpus}.jsonl", False))
    return [(n, p, ph) for n, p, ph in cand if p.exists()]


def load_gold(corpus: str):
    cfg = load_config(str(REPO / "configs" / f"local_olign_{corpus}.yaml"))
    gold = {u.utt_id: u for u in ingest_corpus(corpus, cfg)}
    return gold, make_canon(corpus)


def phone_errors(gold, gold_canon, path) -> list[tuple[float, float, bool]]:
    """(abs_ms, signed_ms, silence_adjacent) over all matched phone boundaries in a hyp file."""
    out: list[tuple[float, float, bool]] = []
    for rec in load_jsonl(path):
        g = gold.get(rec["utt_id"])
        if not g or not rec.get("phones"):
            continue
        out.extend(phone_boundary_errors(g, hyp_utt_from_record(rec), gold_canon))
    return out


def word_errors(gold, path) -> list[tuple[float, bool]]:
    """(abs_ms, silence_adjacent) over all matched word boundaries in a hyp file."""
    out: list[tuple[float, bool]] = []
    for rec in load_jsonl(path):
        g = gold.get(rec["utt_id"])
        if not g or not rec.get("words"):
            continue
        out.extend(word_boundary_errors(g, hyp_utt_from_record(rec)))
    return out
