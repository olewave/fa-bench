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

import pathlib
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



def _cascade_input(cfg, tool: str, corpus: str, subset: str, cond: str) -> dict[str, str]:
    """The words a cascade was handed for one cell: ``{utt_id: "w1 w2 ..."}``.

    Empty for anything that is not a cascade. The upstream hypothesis is named
    in the cell's own config (``params.transcript_hyp``) rather than inferred
    from the tool name, so a cell scored here is relabelled against exactly the
    file it was aligned against -- including a cascade whose upstream is not the
    one its name suggests.
    """
    import json

    import yaml

    from fabench.paths import tool_index

    ent = tool_index(cfg.repo_root()).get(tool)
    if ent is None:
        return {}
    cell = ent[1] / "en" / corpus / subset / (cond or "origin") / "config.yaml"
    if not cell.is_file():
        return {}
    try:
        spec_cfg = yaml.safe_load(cell.read_text()) or {}
        als = spec_cfg.get("aligners") or []
        rel = (als[0].get("params", {}) or {}).get("transcript_hyp") if als else None
    except (OSError, yaml.YAMLError, AttributeError, IndexError):
        return {}
    if not rel:
        return {}
    hyp = pathlib.Path(rel)
    if not hyp.is_absolute():
        hyp = cfg.repo_root() / hyp
    if not hyp.is_file():
        return {}
    out: dict[str, str] = {}
    with hyp.open() as fh:
        for line in fh:
            r = json.loads(line)
            words = [w["label"] if isinstance(w, dict) else w[0]
                     for w in (r.get("words") or [])]
            if words:
                out[r["utt_id"]] = " ".join(words)
    return out


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
    from fabench.paths import tool_kind
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
            # WHAT THIS TOOL WAS GIVEN, so its output can be mapped back onto
            # it (fabench.aligners.relabel). A cascade was handed the upstream
            # ASR's words -- using gold here would erase exactly the
            # recognition error track 2 exists to measure. A timestamped ASR
            # was handed nothing and chose its own words: no relabelling.
            #
            # Read from the CELL config, not the spec: a pooled rescore builds
            # its aligner list from the recipes, and transcript_hyp is per cell
            # by design, so the spec in hand does not carry it.
            _asr_in = _cascade_input(cfg, spec.name, corpus,
                                     cfg.subset_of(corpus), cfg.condition_tag())
            _is_asr_tool = tool_kind(cfg.repo_root(), spec.name) == "timestamp_asrs"
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
                if _asr_in:
                    _in_tok = _asr_in.get(rec["utt_id"], "").split()
                elif _is_asr_tool:
                    _in_tok = None          # decoded its own words
                else:
                    _in_tok = [w.label for w in gold.words]
                us = score_pair(
                    gold,
                    _hyp_utt(rec),
                    input_tokens=_in_tok,
                    # The run config's tag wins over the hyp record's own
                    # field: hypotheses aligned before the shadow-root labelling
                    # fix all carry "clean" regardless of the audio they saw, so
                    # trusting the record would keep every noisy leaderboard
                    # mislabelled until each cell is re-aligned. This makes it a
                    # rescore instead. Empty tag (a clean cell) keeps the record.
                    condition=cfg.condition_tag() or rec["condition"],
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
                    latency_s=rec.get("latency_s"),
                    audio_s=rec.get("audio_s"),
                    setup_s=rec.get("setup_s"),
                    n_gold_utts=len(gold_by_id),
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
