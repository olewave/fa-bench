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

"""`fabench score` (Plan S5): gold + hyp records -> aggregated metrics.

Collects UttScores across *all* enabled aligners x corpora, then aggregates once
so the cross-system common-matched set (survivor-bias guard) is available.
"""

from __future__ import annotations

import sys

from fabench.config import load_config
from fabench.normalize import make_canon, manner_of
from fabench.schema import Utterance, load_jsonl
from fabench.score.aggregate import aggregate
from fabench.score.core import score_pair


def _hyp_utt(rec: dict) -> Utterance:
    from fabench.schema import Interval

    return Utterance(
        utt_id=rec["utt_id"],
        source_corpus="hyp",
        register="",
        speaker_id="",
        audio_path="",
        sample_rate=16000,
        duration_s=0.0,
        words=[Interval.from_dict(w) for w in rec.get("words", [])],
        phones=[Interval.from_dict(p) for p in rec.get("phones", [])],
    )


def score_all(cfg):
    """Return (leaderboard_rows, per_type_rows) over all enabled aligners."""
    from fabench.dataprep.datasets import ingest_corpus

    scoring = cfg.scoring
    protocol = str(scoring.get("protocol", "fabench"))
    manner_match = bool(scoring.get("manner_match", False))
    matcher = str(scoring.get("matcher", "levenshtein"))
    matcher_lambda = float(scoring.get("matcher_lambda", 2.0))
    exclude_silence = bool(scoring.get("exclude_silence_boundaries", False))
    boundary_unit = str(scoring.get("boundary_unit", "phone"))  # phone | word
    uttscores = []
    from fabench.paths import hyp_path as _hyp_path
    for corpus, _ in cfg.enabled_gold():
        try:
            gold_by_id = {u.utt_id: u for u in ingest_corpus(corpus, cfg)}
        except (FileNotFoundError, ValueError) as e:
            print(f"  SKIP {corpus}: {e}", file=sys.stderr)
            continue
        gold_canon = make_canon(corpus)
        for spec in cfg.aligners(enabled_only=True):
            # condition= is REQUIRED here, not just on the write side. Without
            # it every noise-augmented rescore silently loaded the CLEAN hyp
            # (dev/hyp.jsonl instead of dev__reverb/hyp.jsonl) and reported
            # numbers identical to clean across all 12 metric columns -- which
            # is what exposed it: real noise cannot leave MAE, CI, median,
            # TA@10/25/50 and ARR unchanged to 4 significant figures.
            hyp_path = _hyp_path(
                cfg.repo_root(), spec.name, corpus, cfg.subset_of(corpus),
                condition=cfg.condition_tag(),
            )
            if not hyp_path.exists():
                continue
            hyp_recs = list(load_jsonl(hyp_path))
            if protocol == "mfa_paper":
                # Bridges to the real kalpy.evaluation.align_phones + the ported
                # data_prep.R manner filter (fabench/score/mfa_paper/) instead of
                # fabench's own general-purpose matcher/manner_match machinery.
                from fabench.score.mfa_paper import score_cell

                cell_scores = score_cell(cfg, corpus, spec.name, gold_by_id, hyp_recs)
                if cell_scores is None:
                    print(
                        f"  SKIP mfa_paper scoring {spec.name}x{corpus}: "
                        "no vendored mapping file for this aligner/corpus",
                        file=sys.stderr,
                    )
                    continue
                uttscores.extend(cell_scores)
                continue
            for rec in hyp_recs:
                gold = gold_by_id.get(rec["utt_id"])
                if gold is None:
                    continue
                us = score_pair(
                    gold,
                    _hyp_utt(rec),
                    condition=rec["condition"],
                    aligner=rec["aligner"],
                    mode=rec["mode"],
                    gold_canon=gold_canon,
                    hyp_canon=make_canon(rec.get("source", "arpabet")),
                    manner_of_canonical=manner_of,
                    score_phones=bool(rec.get("phones")),
                    score_words=bool(rec.get("words")),
                    manner_match=manner_match,
                    matcher=matcher,
                    matcher_lambda=matcher_lambda,
                    exclude_silence_boundaries=exclude_silence,
                    boundary_unit=boundary_unit,
                    rtf=rec.get("rtf"),
                )
                uttscores.append(us)
    return aggregate(
        uttscores,
        ta_thresholds_s=[t / 1000 for t in scoring.get("ta_thresholds_ms", [10, 20, 50])],
        primary_tol_s=scoring.get("primary_tolerance_ms", 25) / 1000,
        bootstrap_iters=int(scoring.get("bootstrap_iters", 1000)),
        ci=float(scoring.get("bootstrap_ci", 0.95)),
        min_matched_per_cell=int(scoring.get("min_matched_per_cell", 30)),
        seed=int(cfg.seeds.get("global", 0)),
    )


def write_results(cfg, leaderboard, per_type):
    import pandas as pd

    rd = cfg.results_dir()
    rd.mkdir(parents=True, exist_ok=True)
    lb = pd.DataFrame(leaderboard)
    pt = pd.DataFrame(per_type)
    lb.to_parquet(rd / "leaderboard.parquet")
    pt.to_parquet(rd / "per_type.parquet")
    lb.to_csv(rd / "leaderboard.csv", index=False)
    return lb, pt


def cmd_score(args) -> int:
    cfg = load_config(args.config)
    leaderboard, per_type = score_all(cfg)
    if not leaderboard:
        print("no scored results (no gold staged / no hyp files). Run ingest+mix+align.",
              file=sys.stderr)
        return 1
    write_results(cfg, leaderboard, per_type)
    print(f"[score] {len(leaderboard)} leaderboard rows, {len(per_type)} per-type rows "
          f"-> {cfg.results_dir()}")
    return 0
