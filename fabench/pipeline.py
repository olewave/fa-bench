# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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

    from fabench.dataprep.datasets import ingest_corpus, manifest_path
    from fabench.noise.manifest import build_manifest
    from fabench.noise.provider import NoiseProvider

    work = cfg.work_dir()
    # Raw output goes with the tool (fabench.paths) -- the SAME resolver the
    # scorer reads with. `fabench run` and `fabench align` both write here;
    # patching only one of them leaves the other writing where nothing looks.
    from fabench.paths import hyp_path
    aligners = cfg.aligners(enabled_only=True)
    #: Aligner cells that failed or produced nothing. The run deliberately
    #: continues past them, but the EXIT CODE must still say so -- a sweep that
    #: lost every aligner used to finish green, which is how a broken tool
    #: survives an unattended overnight run.
    failures: list[str] = []

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
            recs, err = _align_one(cfg, spec, gold_by_id, items)
            if err is not None:
                print(f"[run]   FAIL {spec.name} x {corpus}: {type(err).__name__}: {err}. "
                      "This aligner is skipped and the run goes on.", file=sys.stderr)
                failures.append(f"{spec.name}x{corpus} ({type(err).__name__})")
                continue
            if not recs:
                # "Ran but wrote nothing" is the failure that looks like success:
                # an empty hyp scores as an absent cell, and without this the
                # command still exits 0. Recorded, not raised -- the surrounding
                # contract is that one bad aligner costs its own rows only.
                print(f"[run]   EMPTY {spec.name} x {corpus}: produced no records",
                      file=sys.stderr)
                failures.append(f"{spec.name}x{corpus} (no records)")
            out = hyp_path(cfg.repo_root(), spec.name, corpus, cfg.subset_of(corpus),
                       condition=cfg.condition_tag())
            out.parent.mkdir(parents=True, exist_ok=True)
            dump_jsonl(recs, out)
            print(f"[run]   aligned {spec.name}: {len(recs)} records")

    # S5 score + S6 report
    from fabench.report.runner import build_report
    from fabench.score.runner import score_all, write_results

    leaderboard = score_all(cfg)
    if leaderboard:
        write_results(cfg, leaderboard)
    md = build_report(leaderboard)
    rd = cfg.results_dir()
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "report.md").write_text(md)
    print(f"[run] report -> {rd / 'report.md'}")

    if staged == 0:
        print("[run] no gold corpora staged — nothing scored. See acquisition "
              "instructions above.", file=sys.stderr)
        return 1
    if failures:
        print(f"[run] {len(failures)} aligner cell(s) failed: " + "; ".join(failures),
              file=sys.stderr)
        return 1
    return 0


def _align_one(cfg, spec, gold_by_id, items):
    """Run one aligner over the mixed items. Returns ``(records, None)``, or
    ``(None, exc)`` when the tool raised.

    Loading an adapter imports that tool's own stack, so a tool whose optional
    dependencies are absent fails right here. One tool's failure must cost only
    its own rows, the promise run_evals.sh keeps by running each cell apart.
    """
    from fabench.aligners.runner import align_items

    try:
        return list(align_items(cfg, spec, gold_by_id, items, spec.modes)), None
    except Exception as exc:
        return None, exc
