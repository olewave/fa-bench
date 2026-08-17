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

"""`fabench report` (Plan Section 6): leaderboard + curves + panels -> report.md.

Emits a human-readable ``summary/report.md`` and machine-readable parquet. No
timestamp is embedded so the report is byte-deterministic (Plan gate #6).
"""

from __future__ import annotations

from fabench.config import load_config
from fabench.report import curves, tables

HUMAN_CEILING_NOTE = (
    "> **Human ceiling (v1):** gold is single-annotated; there is **no measured** "
    "inter-annotator agreement. The literature transcriber-agreement band "
    "(~10–20 ms, boundary-type dependent) is **cited context only**, not a "
    "measured ceiling (Plan 5.10). Do not over-interpret sub-15 ms MAE as "
    "'solved' — it may sit at the (uncited-for-this-data) human floor."
)


def build_report(leaderboard: list[dict], per_type: list[dict], cfg) -> str:
    corpora = sorted({r["corpus"] for r in leaderboard})
    md: list[str] = []
    md.append("# fabench v0 — English Forced-Alignment Benchmark\n")
    md.append(
        "Paired additive-noise degradation over hand-corrected English gold. "
        "Boundary metrics use both onset and offset; MAE/TA are on the matched "
        "path only, with insertions/deletions quarantined into ARR/Ins.\n"
    )
    md.append(HUMAN_CEILING_NOTE + "\n")

    if not leaderboard:
        md.append("\n_No scored results yet — stage gold (TIMIT/Buckeye), then "
                  "`fabench run`._\n")
        return "\n".join(md)

    for corpus in corpora:
        reg = next((r["register"] for r in leaderboard if r["corpus"] == corpus), "")
        md.append(f"\n## Corpus: {corpus} ({reg})\n")
        md.append("### Leaderboard (clean condition)\n")
        md.append(tables.leaderboard_table(leaderboard, corpus, "clean"))
        md.append("\n### Degradation: MAE (ms) vs SNR\n")
        dt, flags = curves.degradation_table(leaderboard, corpus, "mae_ms")
        md.append(dt)
        bad = [f for f in flags if not f["monotonic"]]
        if bad:
            md.append(
                "\n⚠ **Monotonicity flag (gate #8):** MAE improved under worse SNR "
                "for: " + ", ".join(f"{f['aligner']}/{f['mode']}/{f['noise']}" for f in bad)
                + " — investigate mixing/transfer.\n"
            )
        md.append("\n### Per-boundary-type MAE/TA20 (clean)\n")
        md.append(tables.per_type_panel(per_type, corpus, "clean"))

    md.append("\n## Confidence calibration (clean)\n")
    md.append(tables.calibration_panel(leaderboard, "clean"))

    md.append("\n## Notes / caveats\n")
    md.append(
        "- WhisperX is word-only by design → present in WBE, absent from phone "
        "tables (Plan 9).\n"
        "- MFA emits log-likelihood, not per-boundary probability → N/A on "
        "calibration (Plan 5.7).\n"
        "- `mae_common_ms` (survivor-bias guard) and speaker-macro MAE are in the "
        "parquet for cross-system fairness (Plan 5.1).\n"
    )
    return "\n".join(md)


def cmd_report(args) -> int:
    cfg = load_config(args.config)
    rd = cfg.results_dir()
    lb_path, pt_path = rd / "leaderboard.parquet", rd / "per_type.parquet"
    if lb_path.exists() and pt_path.exists():
        import pandas as pd

        leaderboard = pd.read_parquet(lb_path).to_dict("records")
        per_type = pd.read_parquet(pt_path).to_dict("records")
    else:
        from fabench.score.runner import score_all, write_results

        leaderboard, per_type = score_all(cfg)
        if leaderboard:
            write_results(cfg, leaderboard, per_type)

    md = build_report(leaderboard, per_type, cfg)
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "report.md").write_text(md)
    print(f"[report] -> {rd / 'report.md'}")
    return 0
