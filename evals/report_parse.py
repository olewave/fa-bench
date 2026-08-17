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

"""Collect per-cell FA-Bench reports into the results tables.

Reads every summary/en/<corpus>/<subset>/report.md produced by a sweep and
writes:


Generated, not hand-maintained: a sweep adds cells over hours and the tables
must be re-derivable at any point without anyone remembering which rows are
current. Re-run it as often as you like.

Numbers are copied from the reports, never recomputed here -- this file must
not become a second, disagreeing implementation of the metrics.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fabench.paths import ORIGIN

#: Which results tree to collate. Defaults to the PUBLISHED one, because that
#: is what this script exists to regenerate; point it at your own with
#:
#:     FABENCH_RESULTS_DIR=summary/local python -c 'from evals.report_parse import collect; ...'
#:
#: A run writes summary/local (see fabench/config.yaml), so reading `results`
#: by default keeps a sweep in progress from rewriting the published tables --
#: which is exactly what happened once, collapsing an 18-aligner table to the
#: single row a partial sweep had produced so far.
_BASE = Path(os.environ.get("FABENCH_RESULTS_DIR") or (ROOT / "summary" / "aligners"))
if not _BASE.is_absolute():
    _BASE = ROOT / _BASE
RES = _BASE / "en"

# Subsets in reporting order, with what each one is. Order matters: a reader
# should meet dev before the test sets.
SUBSET_NOTE = {
    "dev": "development",
    "core_test": "TIMIT core test, 24 spk",
    "test": "held-out test",
}
ORDER = ["dev", "core_test", "test"]   # full_test removed: a strict superset of dev+core_test

# The leaderboard's columns are READ FROM ITS HEADER, not hard-coded: the
# report gained boundary-detection columns (B-P/B-R/B-F1/OS/R-val) and a fixed
# list silently dropped every row on a length mismatch instead of failing.
HEADER_KEY = {
    "aligner": "aligner", "mode": "mode",
    "mae ms (mean) [95% ci]": "mae", "median": "median", "signed": "signed",
    # both spellings: reports written before the header rename say "wbe"
    "wbe": "wbe", "word mae": "wbe",
    "arr": "arr", "ins": "ins", "rtf": "rtf", "n_bnd": "n_bnd",
    "b-p": "bnd_p", "b-r": "bnd_r", "b-f1": "bnd_f1",
    "w-p": "wbnd_p", "w-r": "wbnd_r", "w-f1": "wbnd_f1",
    "w-os": "wbnd_os", "w-r-val": "w_r_value",
    "os": "os", "r-val": "r_value",
    "sub%": "sub_pct", "del%": "del_pct", "ins%": "ins_pct", "per%": "per",
    # tail: share of boundaries missed by more than 100 ms
    ">100ms%": "err_gt100_pct",
    # word-level recognition accounting -- only meaningful for track-2 systems
    "wsub%": "w_sub_pct", "wdel%": "w_del_pct", "wins%": "w_ins_pct",
    "wer%": "wer",
}


def _key(h: str) -> str:
    h = h.strip().lower()
    if h in HEADER_KEY:
        return HEADER_KEY[h]
    if h.startswith(("t≤", "t<=")):
        return "ta_" + h.replace("t\u2264", "").replace("t<=", "").strip()
    return h.replace(" ", "_")


def parse_report(p: Path) -> list[dict]:
    """Pull the clean-condition leaderboard rows out of one report."""
    rows: list[dict] = []
    cols: list[str] | None = None
    for line in p.read_text().splitlines():
        if not line.startswith("| "):
            cols = None            # table ended; the next one re-reads its header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower() == "aligner":
            cols = [_key(c) for c in cells]
            continue
        if cols is None or set("".join(cells)) <= {"-", " "}:
            continue
        if len(cells) != len(cols):
            continue
        rows.append(dict(zip(cols, cells)))
    return rows


def _mae_or_inf(r: dict) -> float:
    """Phone MAE as a float; inf for word-only systems that render it as an em dash."""
    try:
        return float(r.get("mae", "").split(" [")[0].split()[0])
    except (ValueError, IndexError):
        return float("inf")


def collect(include_noisy: bool | None = False,
            kind: str = "aligners") -> dict[str, dict[str, list[dict]]]:
    """Parsed leaderboards for one TRACK.

    `kind` selects the tree: `aligners` are handed the reference transcript,
    `timestamp_asrs` decode their own. They are scored into sibling trees and
    must never share a leaderboard, so reading one is the default -- but the
    track-2 table needs the other, and reading only `aligners` was silently
    giving it an empty result set. The page then printed "no timestamped ASR
    produced a word tier", which was a statement about the path being read,
    not about the data on disk.
    """
    base = RES if kind == "aligners" else ROOT / "summary" / kind / "en"
    out: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    # A cell is <corpus>/<subset>/<condition>/, with `origin` for un-augmented.
    for rep in sorted(base.glob("*/*/*/report.md")):
        cond = rep.parent.name
        corpus, subset = rep.parent.parent.parent.name, rep.parent.parent.name
        # Skip noise-augmented cells, or keep only those. Without the filter a
        # running noisy sweep leaks into the CLEAN published tables -- charsiu
        # under babble once appeared as a Buckeye split beside dev and test.
        if include_noisy is False and cond != ORIGIN:
            continue
        if include_noisy is True and cond == ORIGIN:
            continue
        rows = parse_report(rep)
        if not rows:
            continue
        # Noisy cells keep the condition IN THE KEY, as `<subset>__<condition>`.
        # The directory layout separates them (<subset>/<condition>/), but three
        # consumers -- noise_table, the F1 variant, and gen_tex_tables -- look up
        # f"{sub}__{cond}", and a bare subset key silently collapses all four
        # conditions into one. That is not hypothetical: it emptied both noise
        # tables in summary/README.md, 62 lines, with no error.
        out[corpus][subset if cond == ORIGIN else f"{subset}__{cond}"] = rows
    return out


def subsets_of(d: dict) -> list[str]:
    return sorted(d, key=lambda s: (ORDER.index(s) if s in ORDER else 99, s))
