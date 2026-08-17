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

"""End-to-end orchestrator: `fabench run` (Plan S6).

Executes S3 (mix) -> S4 (align) -> S5 (score) -> S6 (report) across the matrix
for every enabled gold corpus and aligner, deterministically. Missing gold
corpora are skipped loudly (with acquisition instructions), so the command is
safe to run before data is staged (it will simply report nothing to score).
"""

from __future__ import annotations

import sys

from fabench.config import load_config
from fabench.schema import dump_jsonl


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    limit = getattr(args, "limit", None)

    from fabench.aligners.runner import align_items
    from fabench.dataprep.datasets import ingest_corpus, manifest_path
    from fabench.noise.manifest import build_manifest
    from fabench.noise.provider import NoiseProvider

    work = cfg.work_dir()
    # Raw output goes with the tool (fabench.paths) -- the SAME resolver the
    # scorer reads with. `fabench run` and `fabench align` both write here;
    # patching only one of them leaves the other writing where nothing looks.
    from fabench.paths import hyp_path
    aligners = cfg.aligners(enabled_only=True)

    # Ingest first — do NOT touch the noise provider (which may fetch ~11 GB of
    # MUSAN) until at least one corpus is confirmed staged.
    staged_corpora = []
    for corpus, _ in cfg.enabled_gold():
        try:
            utts = ingest_corpus(corpus, cfg, limit=limit)
        except (FileNotFoundError, ValueError) as e:
            print(f"[run] SKIP {corpus}: {e}", file=sys.stderr)
            continue
        staged_corpora.append((corpus, utts))
        print(f"[run] {corpus}: {len(utts)} utts")

    staged = len(staged_corpora)
    provider = NoiseProvider.from_config(cfg) if staged else None

    for corpus, utts in staged_corpora:
        # S3 mix
        items = build_manifest(utts, cfg, provider, work / "mix")
        dump_jsonl(items, manifest_path(cfg, corpus))
        print(f"[run]   mixed {len(items)} items")

        # S4 align (each enabled aligner)
        gold_by_id = {u.utt_id: u for u in utts}
        for spec in aligners:
            # Broad catch, and deliberately so: adapter.load() imports each
            # tool's own stack (torch, transformers, ...), and a default-enabled
            # aligner with a missing optional dependency must cost its own rows,
            # not the whole run — run_evals.sh already isolates per cell, this
            # is the same contract for the single-command path.
            try:
                recs = list(align_items(cfg, spec, gold_by_id, items, spec.modes))
            except Exception as e:
                print(f"[run]   FAIL {spec.name}: {type(e).__name__}: {e} — "
                      "skipping this aligner, run continues", file=sys.stderr)
                continue
            out = hyp_path(cfg.repo_root(), spec.name, corpus, cfg.subset_of(corpus),
                       condition=cfg.condition_tag())
            out.parent.mkdir(parents=True, exist_ok=True)
            dump_jsonl(recs, out)
            print(f"[run]   aligned {spec.name}: {len(recs)} records")

    # S5 score + S6 report
    from fabench.report.runner import build_report
    from fabench.score.runner import score_all, write_results

    leaderboard, per_type = score_all(cfg)
    if leaderboard:
        write_results(cfg, leaderboard, per_type)
    md = build_report(leaderboard, per_type, cfg)
    rd = cfg.results_dir()
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "report.md").write_text(md)
    print(f"[run] report -> {rd / 'report.md'}")

    if staged == 0:
        print("[run] no gold corpora staged — nothing scored. See acquisition "
              "instructions above.", file=sys.stderr)
        return 1
    return 0
