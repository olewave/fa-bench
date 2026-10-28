# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""`fabench report` (Plan Section 6): leaderboard -> report.md.

Emits a human-readable ``report.md`` beside the leaderboard. No timestamp is
embedded so the report is byte-deterministic (Plan gate #6).
"""

from __future__ import annotations

import math

from fabench.config import load_config

#: The report's columns, word tier first, as (header, leaderboard column, decimals).
COLUMNS = [
    ("word TS F1", "wts_f1", 3),
    ("word TS MAE ms", "wts_mae_ms", 1),
    ("word MAE ms", "wbe_ms", 1),
    ("word F1", "wbnd_f1_all_20ms", 3),
    ("WER %", "wer", 1),
    ("phone MAE ms", "mae_ms", 1),
    ("phone F1", "bnd_f1_all_20ms", 3),
    ("PER %", "per", 1),
]


def _f(x, nd: int) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{nd}f}"


def build_report(leaderboard: list[dict]) -> str:
    md = ["# FA-Bench report\n",
          ("Word timestamp (TS) F1 and both F1 columns count a hit within 20 ms. "
           "MAE is over matched boundaries. A dash means the system emits no such tier.\n")]
    if not leaderboard:
        md.append("_No scored results yet. Stage gold (TIMIT, Buckeye), then "
                  "`fabench run`._\n")
        return "\n".join(md)
    for corpus, condition in sorted({(r["corpus"], r["condition"]) for r in leaderboard}):
        rows = sorted((r for r in leaderboard
                       if r["corpus"] == corpus and r["condition"] == condition),
                      key=lambda r: (r["aligner"], r["mode"]))
        md.append(f"## {corpus}, {condition}\n")
        header = ["system", "mode", *(h for h, _, _ in COLUMNS), "utts", "absent", "empty"]
        lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
        for r in rows:
            cells = [r["aligner"], r["mode"], *(_f(r.get(c), nd) for _, c, nd in COLUMNS),
                     *(str(r[c]) for c in ("n_utts", "n_absent", "n_empty"))]
            lines.append("| " + " | ".join(cells) + " |")
        md.append("\n".join(lines) + "\n")
    return "\n".join(md)


def cmd_report(args) -> int:
    cfg = load_config(args.config)
    rd = cfg.results_dir()
    lb_path = rd / "leaderboard.parquet"
    if lb_path.exists():
        import pandas as pd

        leaderboard = pd.read_parquet(lb_path).to_dict("records")
    else:
        from fabench.score.runner import score_all, write_results

        leaderboard = score_all(cfg)
        if leaderboard:
            write_results(cfg, leaderboard)

    rd.mkdir(parents=True, exist_ok=True)
    (rd / "report.md").write_text(build_report(leaderboard))
    print(f"[report] -> {rd / 'report.md'}")
    return 0
