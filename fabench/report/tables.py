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

"""Markdown table builders for the leaderboard + panels (Plan Section 6)."""

from __future__ import annotations

import math
from collections.abc import Iterable


def _f(x, nd=1, dash="—"):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return dash
    return f"{x:.{nd}f}"


def _pct(x, nd=1, dash="—"):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return dash
    return f"{100*x:.{nd}f}"


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def leaderboard_table(rows: Iterable[dict], corpus: str, condition: str = "clean") -> str:
    """rows = aligner x mode; columns per Plan 6. Filtered to one corpus/condition."""
    sel = [r for r in rows if r["corpus"] == corpus and r["condition"] == condition]
    sel.sort(key=lambda r: (r["aligner"], r["mode"]))
    if not sel:
        return f"_(no rows for {corpus} / {condition})_"
    ta_ms = _ta_thresholds(sel[0])  # e.g. [10, 25, 50]
    header = (
        ["aligner", "mode", "MAE ms (mean) [95% CI]", "median", "signed"]
        + [f"t≤{t}" for t in ta_ms]
        # "word MAE", not "WBE": same measure as the phone MAE, on the word
        # tier -- the benchmark coins no terms. Internal key stays `wbe`.
        + ["word MAE", "ARR",
           # Why a gold phone left the matched path. ARR + Sub% + Del% = 100%.
           "Sub%", "Del%", "Ins%", "PER%", "Ins",
           # Boundary DETECTION, paired by time and label-agnostic -- these
           # charge for over/under-segmentation, which a matched-path MAE
           # cannot. R-value separates the two failure modes F1 conflates.
           "B-P", "B-R", "B-F1", "OS", "R-val",
           # WORD-level boundary detection. Computed all along (aggregate.py
           # emits wbnd_precision/recall/f1 from score.core's n_*_wbnd counts)
           # but never surfaced, so the public word table fell back to the
           # PHONE B-F1 -- mislabelled for phone tools and empty for word-only
           # ones. It is the only boundary metric whisperx, qwen3_fa,
           # parakeet_tdt and crisperwhisper can have at all.
           # W-OS / W-R-val were the SAME omission one tier down: aggregate.py
           # has written wbnd_os and w_r_value all along and neither reached a
           # report, so the word tier looked like it had no segmentation
           # balance at all rather than an unsurfaced one.
           "W-P", "W-R", "W-F1", "W-OS", "W-R-val",
           # WER and its decomposition. Near-zero for a forced aligner,
           # which is handed the reference; the number that matters for a
           # timestamped ASR, where a bad word MAE is otherwise
           # unattributable between recognition and timing failure.
           # Share of boundaries missed by MORE THAN 100 ms -- the tail a
           # mean hides. Not merely bad, wrong.
           ">100ms%",
           "WSub%", "WDel%", "WIns%", "WER%",
           "RTF", "n_bnd"]
    )
    table_rows = []
    for r in sel:
        mae = _f(r.get("mae_ms"))
        ci = ""
        if not (math.isnan(r.get("mae_ci_lo_ms", float("nan")))):
            ci = f" [{_f(r['mae_ci_lo_ms'])},{_f(r['mae_ci_hi_ms'])}]"
        table_rows.append(
            [r["aligner"], r["mode"], mae + ci,
             _f(r.get("median_ms")), _f(r.get("signed_ms"))]
            + [_pct(r.get(f"ta_{t}ms")) for t in ta_ms]
            + [_f(r.get("wbe_ms")),
               _pct(r.get("arr")),
               _f(r.get("sub_pct"), 1), _f(r.get("del_pct"), 1),
               _f(r.get("ins_pct"), 1), _f(r.get("per"), 1),
               _pct(r.get("insert_rate")),
               _f(r.get("bnd_precision"), 3), _f(r.get("bnd_recall"), 3),
               _f(r.get("bnd_f1"), 3), _f(r.get("bnd_os"), 3),
               _f(r.get("r_value"), 3),
               _f(r.get("wbnd_precision"), 3), _f(r.get("wbnd_recall"), 3),
               _f(r.get("wbnd_f1"), 3), _f(r.get("wbnd_os"), 3),
               _f(r.get("w_r_value"), 3),
               _f(r.get("err_gt100_pct"), 1),
               _f(r.get("w_sub_pct"), 1), _f(r.get("w_del_pct"), 1),
               _f(r.get("w_ins_pct"), 1), _f(r.get("wer"), 1),
               _f(r.get("rtf_mean"), 3), str(r.get("n_boundaries", 0))]
        )
    return _md_table(header, table_rows)


def _ta_thresholds(row: dict) -> list[int]:
    import re

    ts = sorted(
        int(m.group(1))
        for k in row
        if (m := re.fullmatch(r"ta_(\d+)ms", k))
    )
    return ts or [10, 25, 50]


def per_type_panel(per_type_rows: Iterable[dict], corpus: str, condition: str = "clean") -> str:
    """MAE (ms) / TA20 per (left->right manner) x aligner at a fixed condition."""
    sel = [r for r in per_type_rows if r["corpus"] == corpus and r["condition"] == condition]
    if not sel:
        return f"_(no per-type rows for {corpus} / {condition})_"
    aligners = sorted({r["aligner"] + ":" + r["mode"] for r in sel})
    types = sorted({(r["left_manner"], r["right_manner"]) for r in sel})
    header = ["boundary (L→R)"] + aligners
    rows = []
    for (lm, rm) in types:
        cells = [f"{lm}→{rm}"]
        for a in aligners:
            an, mode = a.split(":")
            match = [
                r for r in sel
                if r["aligner"] == an and r["mode"] == mode
                and r["left_manner"] == lm and r["right_manner"] == rm
            ]
            if match:
                m = match[0]
                flag = "*" if m.get("underpowered") else ""
                cells.append(f"{_f(m['mae_ms'])}/{_pct(m.get('ta'),0)}{flag}")
            else:
                cells.append("—")
        rows.append(cells)
    note = "\nCells: `MAE_ms / t≤primary_%`; `*` = underpowered (below min matched count)."
    return _md_table(header, rows) + note


def calibration_panel(rows: Iterable[dict], condition: str = "clean") -> str:
    """Spearman / AUROC / ECE per emitting system (Plan 5.7)."""
    sel = [r for r in rows if r["condition"] == condition and r.get("n_conf", 0) > 0]
    sel.sort(key=lambda r: (r["corpus"], r["aligner"], r["mode"]))
    if not sel:
        return "_(no confidence-emitting systems)_"
    header = ["corpus", "aligner", "mode", "Spearman(conf,-|err|)", "AUROC@20ms", "ECE", "n_conf"]
    rows_out = [[
        r["corpus"], r["aligner"], r["mode"],
        _f(r.get("cal_spearman"), 3), _f(r.get("cal_auroc"), 3),
        _f(r.get("cal_ece"), 3), str(r.get("n_conf", 0)),
    ] for r in sel]
    return _md_table(header, rows_out)
