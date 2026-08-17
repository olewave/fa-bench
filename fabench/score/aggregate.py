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

"""Corpus-level aggregation (Plan 5.9 / Section 6).

Rolls a stream of per-utterance :class:`UttScore` up into leaderboard rows and a
per-boundary-type long table, with bootstrap 95% CIs (resampled over utterances)
and the cross-system *common-matched* MAE that kills survivor bias (Plan 5.1).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

import numpy as np

from fabench import metrics as M
from fabench.score import boundary as B
from fabench.score import calibration, word
from fabench.score.core import UttScore

MS = 1000.0  # seconds -> milliseconds


# --------------------------------------------------------------------------
# Bootstrap (mean statistics: MAE and TA are both means over boundaries)
# --------------------------------------------------------------------------
def bootstrap_mean_ci(
    per_utt_sum: np.ndarray,
    per_utt_count: np.ndarray,
    n_iters: int,
    ci: float,
    seed: int,
) -> tuple[float, float]:
    """CI for a pooled mean = sum(values)/count, resampling *utterances*.

    Each utterance contributes (sum_of_values, n_values); a bootstrap replicate
    resamples utterances with replacement and recomputes the ratio. This is the
    exact bootstrap of the pooled mean and is O(iters*n_utts).
    """
    n = len(per_utt_sum)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n, size=(n_iters, n))
    s = per_utt_sum[draws].sum(axis=1)
    c = per_utt_count[draws].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        stats = np.where(c > 0, s / c, np.nan)
    lo = float(np.nanpercentile(stats, (1 - ci) / 2 * 100))
    hi = float(np.nanpercentile(stats, (1 + ci) / 2 * 100))
    return lo, hi


# --------------------------------------------------------------------------
# Grouping helpers
# --------------------------------------------------------------------------
def _group_key(us: UttScore) -> tuple:
    # protocol is included so running both "fabench" and "mfa_paper" over the
    # same (corpus, aligner) never silently merges two different MAE
    # definitions into one leaderboard row.
    return (us.corpus, us.register, us.aligner, us.mode, us.condition, us.protocol)


def _common_matched_sets(
    scores: Sequence[UttScore],
) -> dict[tuple, set[int]]:
    """For each (corpus, register, mode, condition, utt_id), the set of gold
    phone indices matched by *every* phone-scoring aligner present (Plan 5.1).
    Word-only systems (no matched phones) do not participate.
    """
    by_utt: dict[tuple, list[set[int]]] = defaultdict(list)
    for us in scores:
        if us.matched_gold_phone_idx:
            # protocol included defensively: gold_phone_idx indexes a different
            # underlying list per protocol (fabench: post-canonicalization,
            # DELETE-filtered; mfa_paper: raw gold.phones), so a same-utterance
            # entry from a different protocol must never be treated as "common".
            k = (us.corpus, us.register, us.mode, us.condition, us.utt_id, us.protocol)
            by_utt[k].append(set(us.matched_gold_phone_idx))
    common: dict[tuple, set[int]] = {}
    for k, sets in by_utt.items():
        inter = set.intersection(*sets) if sets else set()
        common[k] = inter
    return common


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def aggregate(
    scores: Iterable[UttScore],
    *,
    ta_thresholds_s: Sequence[float] = (0.010, 0.020, 0.050),
    primary_tol_s: float = 0.020,
    bootstrap_iters: int = 1000,
    ci: float = 0.95,
    min_matched_per_cell: int = 30,
    seed: int = 20240607,
) -> tuple[list[dict], list[dict]]:
    """Return (leaderboard_rows, per_type_rows)."""
    scores = list(scores)
    common = _common_matched_sets(scores)

    # Common-matched MAE is a property of an aligner WITHIN a comparison set,
    # not of the aligner. With one phone-scoring system the intersection is that
    # system's own matched set, so the column equals mae_ms exactly -- and a
    # duplicate that looks like an independent corroborating measurement is
    # worse than an absent one: it reads as "mae and mae_common agree, so no
    # survivor bias", which is not what it says. Suppressed to NaN below two
    # systems, the same way every other column that cannot mean anything for a
    # row is suppressed.
    _phone_systems = {us.aligner for us in scores if us.matched_gold_phone_idx}
    _comparable = len(_phone_systems) >= 2

    groups: dict[tuple, list[UttScore]] = defaultdict(list)
    for us in scores:
        groups[_group_key(us)].append(us)

    leaderboard: list[dict] = []
    per_type_rows: list[dict] = []

    for key, group in sorted(groups.items()):
        corpus, register, aligner, mode, condition, protocol = key
        row = {
            "corpus": corpus,
            "register": register,
            "aligner": aligner,
            "mode": mode,
            "condition": condition,
            "scoring_protocol": protocol,
            "n_utts": len(group),
            "n_speakers": len({g.speaker_id for g in group}),
        }

        # ---- phone boundary metrics ----
        pooled: list[B.BoundaryError] = [e for g in group for e in g.boundary_errors]
        row["n_boundaries"] = len(pooled)
        # Scalar boundary metrics (mae_ms/median_ms/signed_ms) come from the
        # fabench.metrics registry — the single definition of these metrics; each
        # returns nan on an empty pool. TA is computed below instead because it is
        # config-thresholded (ta_thresholds_s), unlike the registry's fixed TA.
        for _key, _metric in M.all_metrics().items():
            if _metric.unit == "ms":
                row[_key] = _metric.compute(pooled)
        if pooled:
            abs_all = np.array([e.abs for e in pooled])
            for tau in ta_thresholds_s:
                row[f"ta_{round(tau*MS)}ms"] = float(
                    (abs_all <= tau + B.TA_TOL_S).mean()
                )
            # Share of boundaries missed by MORE THAN 100 ms -- the tail MAE
            # hides. A mean can be pulled up by a few catastrophic placements
            # while the typical boundary is fine (CrisperWhisper's Buckeye mean
            # was 223.9 ms against a 30.3 ms median, entirely a 5.7% failure
            # rate), and it can equally look calm while a system is uniformly
            # mediocre. TA@50 says how often a system is good; this says how
            # often it is not merely bad but wrong.
            row["err_gt100_pct"] = float((abs_all > 0.100).mean()) * 100.0

            # onset/offset component MAE
            on = [e.abs for e in pooled if e.edge == "onset"]
            off = [e.abs for e in pooled if e.edge == "offset"]
            row["onset_mae_ms"] = float(np.mean(on)) * MS if on else float("nan")
            row["offset_mae_ms"] = float(np.mean(off)) * MS if off else float("nan")

            # bootstrap CI over utterances (MAE and TA20)
            per_sum = np.array([sum(e.abs for e in g.boundary_errors) for g in group])
            per_cnt = np.array([len(g.boundary_errors) for g in group], float)
            lo, hi = bootstrap_mean_ci(per_sum, per_cnt, bootstrap_iters, ci, seed)
            row["mae_ci_lo_ms"], row["mae_ci_hi_ms"] = lo * MS, hi * MS
            row["primary_tol_ms"] = round(primary_tol_s * MS)
            tau_p = primary_tol_s + B.TA_TOL_S
            per_sump = np.array(
                [sum(1 for e in g.boundary_errors if e.abs <= tau_p) for g in group],
                float,
            )
            lop, hip = bootstrap_mean_ci(per_sump, per_cnt, bootstrap_iters, ci, seed)
            row["ta_primary_ci_lo"], row["ta_primary_ci_hi"] = lop, hip

            # common-matched MAE (survivor-bias guard) -- only across systems
            row["mae_common_ms"] = (_common_mae(group, common) * MS
                                    if _comparable else float("nan"))
        else:
            for col in (
                "onset_mae_ms", "offset_mae_ms",
                "mae_ci_lo_ms", "mae_ci_hi_ms", "mae_common_ms",
            ):
                row[col] = float("nan")
            for tau in ta_thresholds_s:
                row[f"ta_{round(tau*MS)}ms"] = float("nan")
            row["primary_tol_ms"] = round(primary_tol_s * MS)
            row["ta_primary_ci_lo"] = row["ta_primary_ci_hi"] = float("nan")

        # ---- recall / insertion (phones) ----
        n_m = sum(g.n_matched_phone for g in group)
        n_g = sum(g.n_gold_phone for g in group)
        n_h = sum(g.n_hyp_phone for g in group)
        row["arr"] = n_m / n_g if n_g else float("nan")
        row["insert_rate"] = (n_h - n_m) / n_h if n_h else float("nan")

        # ---- SUB / DEL / INS as % of gold phones ----
        # match% + sub% + del% == 100% exactly (every gold phone is one of the
        # three), and match% IS arr. Insertions have no gold counterpart and are
        # normalised by the gold count per the PER/WER convention, so they sit
        # outside that identity. Reported because ARR alone cannot say whether a
        # missing gold phone was relabelled or never emitted.
        n_s = sum(g.n_sub_phone for g in group)
        n_d = sum(g.n_del_phone for g in group)
        n_i = sum(g.n_ins_phone for g in group)
        row["sub_pct"] = 100.0 * n_s / n_g if n_g else float("nan")
        row["del_pct"] = 100.0 * n_d / n_g if n_g else float("nan")
        row["ins_pct"] = 100.0 * n_i / n_g if n_g else float("nan")
        row["per"] = 100.0 * (n_s + n_d + n_i) / n_g if n_g else float("nan")

        # ---- boundary detection: P/R/F1 @ 20 ms, OS, R-value ----
        # Pooled over the corpus, not averaged per utterance: these are ratios
        # of counts, and a per-utterance mean would weight a 3-boundary
        # utterance the same as a 300-boundary one.
        from fabench.score.segmentation import SegmentationScore

        seg = SegmentationScore(
            n_gold=sum(g.n_gold_bnd for g in group),
            n_hyp=sum(g.n_hyp_bnd for g in group),
            hits=sum(g.n_bnd_hits for g in group),
            tol_s=0.020,
        )
        row["bnd_precision"] = seg.precision
        row["bnd_recall"] = seg.recall
        row["bnd_f1"] = seg.f1
        row["bnd_os"] = seg.os
        row["r_value"] = seg.r_value
        row["n_bnd_gold"] = seg.n_gold
        row["n_bnd_hyp"] = seg.n_hyp

        # ---- word metrics (WBE micro/macro) ----
        wm = word.word_boundary_error([g.word_abs_errors for g in group])
        row["wbe_ms"] = wm["wbe_s"] * MS
        row["n_word_boundaries"] = wm["n_word_boundaries"]

        # ---- word-boundary detection: P/R/F1 @ 20 ms ----
        wseg = SegmentationScore(
            n_gold=sum(g.n_gold_wbnd for g in group),
            n_hyp=sum(g.n_hyp_wbnd for g in group),
            hits=sum(g.n_wbnd_hits for g in group),
            tol_s=0.020,
        )
        row["wbnd_precision"] = wseg.precision
        row["wbnd_recall"] = wseg.recall
        row["wbnd_f1"] = wseg.f1
        row["wbnd_os"] = wseg.os
        row["w_r_value"] = wseg.r_value

        # ---- WER and its decomposition ----
        # Only meaningful for a system that DECODES its own transcript. A
        # forced aligner is handed the reference, so its WER is ~0 by
        # construction and says nothing; it is emitted anyway rather than
        # special-cased, because which tools are track 2 is a property of the
        # recipe layout, not of the scorer, and a near-zero column is honest
        # where a blank one invites "did it fail?".
        n_gw = sum(g.n_gold_word for g in group)
        n_ws = sum(g.n_sub_word for g in group)
        n_wd = sum(g.n_del_word for g in group)
        n_wi = sum(g.n_ins_word for g in group)
        row["w_sub_pct"] = 100.0 * n_ws / n_gw if n_gw else float("nan")
        row["w_del_pct"] = 100.0 * n_wd / n_gw if n_gw else float("nan")
        row["w_ins_pct"] = 100.0 * n_wi / n_gw if n_gw else float("nan")
        row["wer"] = 100.0 * (n_ws + n_wd + n_wi) / n_gw if n_gw else float("nan")

        # ---- calibration ----
        conf = [e.conf for e in pooled]
        aerr = [e.abs for e in pooled]
        cal = calibration.calibration_metrics(conf, aerr, within_tau_s=primary_tol_s)
        row["cal_spearman"] = cal["spearman"]
        row["cal_auroc"] = cal["auroc"]
        row["cal_ece"] = cal["ece"]
        row["n_conf"] = cal["n_conf"]

        # ---- efficiency ----
        rtfs = [g.rtf for g in group if g.rtf is not None]
        row["rtf_mean"] = float(np.mean(rtfs)) if rtfs else float("nan")

        # ---- power flag ----
        row["underpowered"] = n_m < min_matched_per_cell

        leaderboard.append(row)

        # ---- per-type long table ----
        pt = B.per_type(pooled, ta20_s=primary_tol_s, min_n=min_matched_per_cell)
        for (lman, rman), cell in pt.items():
            per_type_rows.append(
                {
                    "corpus": corpus,
                    "register": register,
                    "aligner": aligner,
                    "mode": mode,
                    "condition": condition,
                    "left_manner": lman,
                    "right_manner": rman,
                    "n": cell["n"],
                    "mae_ms": cell["mae_s"] * MS,
                    "ta": cell["ta"],
                    "underpowered": cell["underpowered"],
                }
            )

    return leaderboard, per_type_rows


def _common_mae(group: Sequence[UttScore], common: dict[tuple, set[int]]) -> float:
    vals: list[float] = []
    for g in group:
        k = (g.corpus, g.register, g.mode, g.condition, g.utt_id, g.protocol)
        cset = common.get(k)
        if not cset:
            continue
        for e in g.boundary_errors:
            if e.gold_phone_idx in cset:
                vals.append(e.abs)
    return float(np.mean(vals)) if vals else float("nan")
