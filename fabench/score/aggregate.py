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
from fabench.score import calibration, latency, word
from fabench.score.core import UttScore

MS = 1000.0  # seconds -> milliseconds

#: The tolerance the BOUNDARY-DETECTION family is summarised at, in ms, and it
#: is not `primary_tol_s`. That one is tolerance accuracy's primary and the
#: configs set it to 25; F1/P/R are fixed at 20, which is what the
#: segmentation literature reports and what Table 1 prints. Keying the
#: label-checked aliases off primary_tol_s silently published a 25 ms score
#: under a 20 ms caption, so the two are kept apart by name.
F1_TOL_MS = 20


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
            # Units, not boundaries. A unit's start and its end are two
            # different placements even where two units share a time, so
            # this split keeps its own pool.
            _ue = [e for g in group for e in g.unit_edge_errors]
            on = [e.abs for e in _ue if e.edge == "onset"]
            off = [e.abs for e in _ue if e.edge == "offset"]
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

        # The same detection metrics at every swept width. Only the hit count
        # moves, so the gold and hyp totals above are reused. This is what lets
        # F1 be read against tolerance accuracy at one width; before it, F1
        # existed at 20 ms and nowhere else.
        for _ms in sorted({m for g in group for m in g.n_bnd_hits_by_tol}):
            _s = SegmentationScore(
                n_gold=seg.n_gold, n_hyp=seg.n_hyp,
                hits=sum(g.n_bnd_hits_by_tol.get(_ms, 0) for g in group),
                tol_s=_ms / MS)
            row[f"bnd_p_{_ms}ms"] = _s.precision
            row[f"bnd_r_{_ms}ms"] = _s.recall
            row[f"bnd_f1_{_ms}ms"] = _s.f1
        # ---- label-checked boundary detection ----
        # Same boundaries, same denominators, same widths. A hit must also agree
        # about WHICH boundary it is: the units on both sides are the aligned,
        # same-labelled units. `pos` relaxes that to "the units correspond",
        # so the lbl-to-pos gap is what substitutions cost and the lbl-to-plain
        # gap is what pairing across ranks was worth.
        for _tag, _fld in (("lbl", "n_bnd_hits_lbl_by_tol"),
                           ("pos", "n_bnd_hits_pos_by_tol")):
            for _ms in sorted({m for g in group for m in getattr(g, _fld)}):
                _s = SegmentationScore(
                    n_gold=seg.n_gold, n_hyp=seg.n_hyp,
                    hits=sum(getattr(g, _fld).get(_ms, 0) for g in group),
                    tol_s=_ms / MS)
                row[f"bnd_p_{_tag}_{_ms}ms"] = _s.precision
                row[f"bnd_r_{_tag}_{_ms}ms"] = _s.recall
                row[f"bnd_f1_{_tag}_{_ms}ms"] = _s.f1
        _pt = F1_TOL_MS
        row["bnd_precision_lbl"] = row.get(f"bnd_p_lbl_{_pt}ms", float("nan"))
        row["bnd_recall_lbl"] = row.get(f"bnd_r_lbl_{_pt}ms", float("nan"))
        row["bnd_f1_lbl"] = row.get(f"bnd_f1_lbl_{_pt}ms", float("nan"))
        row["bnd_f1_pos"] = row.get(f"bnd_f1_pos_{_pt}ms", float("nan"))
        # Share of time-only hits that credited a neighbouring boundary.
        _h = sum(g.n_bnd_hits_by_tol.get(_pt, 0) for g in group)
        _hl = sum(g.n_bnd_hits_lbl_by_tol.get(_pt, 0) for g in group)
        row["bnd_wrong_hit_pct"] = 100.0 * (1 - _hl / _h) if _h else float("nan")
        _ctx_columns(row, group, "bnd", "bnd_ctx", "bnd_ctx_mae")

        # ---- word metrics (WBE micro/macro) ----
        wm = word.word_boundary_error([g.word_abs_errors for g in group])
        row["wbe_ms"] = wm["wbe_s"] * MS
        row["n_word_boundaries"] = wm["n_word_boundaries"]
        # The same tolerances the phone tier reports, on the word tier. Without
        # these a word-only system had no tolerance accuracy at any width.
        for _ms, _v in word.word_tolerance_accuracy(
                [g.word_abs_errors for g in group], ta_thresholds_s).items():
            row[f"wta_{_ms}ms"] = _v

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
        for _ms in sorted({m for g in group for m in g.n_wbnd_hits_by_tol}):
            _s = SegmentationScore(
                n_gold=wseg.n_gold, n_hyp=wseg.n_hyp,
                hits=sum(g.n_wbnd_hits_by_tol.get(_ms, 0) for g in group),
                tol_s=_ms / MS)
            row[f"wbnd_p_{_ms}ms"] = _s.precision
            row[f"wbnd_r_{_ms}ms"] = _s.recall
            row[f"wbnd_f1_{_ms}ms"] = _s.f1
        # ---- label-checked word-boundary detection ----
        # On the silence-filtered word sequences, so "[sil]" from Charsiu and
        # MAPS is not a boundary. Its own denominators go with it, and `nosil`
        # is the time-only score over exactly those sequences -- the only
        # baseline the label-checked number can be differenced against. For
        # every system that emits no pseudo-words, nosil equals the plain score.
        _wg = sum(g.n_gold_wbnd_lbl for g in group)
        _wh = sum(g.n_hyp_wbnd_lbl for g in group)
        row["n_wbnd_gold_lbl"], row["n_wbnd_hyp_lbl"] = _wg, _wh
        for _tag, _fld in (("lbl", "n_wbnd_hits_lbl_by_tol"),
                           ("pos", "n_wbnd_hits_pos_by_tol"),
                           ("nosil", "n_wbnd_hits_nosil_by_tol")):
            for _ms in sorted({m for g in group for m in getattr(g, _fld)}):
                _s = SegmentationScore(
                    n_gold=_wg, n_hyp=_wh,
                    hits=sum(getattr(g, _fld).get(_ms, 0) for g in group),
                    tol_s=_ms / MS)
                row[f"wbnd_p_{_tag}_{_ms}ms"] = _s.precision
                row[f"wbnd_r_{_tag}_{_ms}ms"] = _s.recall
                row[f"wbnd_f1_{_tag}_{_ms}ms"] = _s.f1
        row["wbnd_precision_lbl"] = row.get(f"wbnd_p_lbl_{_pt}ms", float("nan"))
        row["wbnd_recall_lbl"] = row.get(f"wbnd_r_lbl_{_pt}ms", float("nan"))
        row["wbnd_f1_lbl"] = row.get(f"wbnd_f1_lbl_{_pt}ms", float("nan"))
        row["wbnd_f1_pos"] = row.get(f"wbnd_f1_pos_{_pt}ms", float("nan"))
        row["wbnd_f1_nosil"] = row.get(f"wbnd_f1_nosil_{_pt}ms", float("nan"))
        _wh0 = sum(g.n_wbnd_hits_nosil_by_tol.get(_pt, 0) for g in group)
        _whl = sum(g.n_wbnd_hits_lbl_by_tol.get(_pt, 0) for g in group)
        row["wbnd_wrong_hit_pct"] = (100.0 * (1 - _whl / _wh0) if _wh0
                                     else float("nan"))
        _ctx_columns(row, group, "wbnd", "wbnd_ctx", "wbnd_ctx_mae")

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

        # ---- coverage ----
        # Scored utterances against the size of the split. Reported always,
        # because a shortfall is normal for some tools and fatal for others: a
        # cascade drops what its upstream heard as nothing and NeMo-FA 80 ms
        # drops 32 short Buckeye utterances by design, both landing at 93-100%,
        # while a cell cut off by an expired token sat at 19% and scored as a
        # clean row. `incomplete` fires only on the second kind.
        golds = [g.n_gold_utts for g in group if g.n_gold_utts]
        n_gold_utts = max(golds) if golds else 0
        row["n_gold_utts"] = n_gold_utts
        row["coverage"] = (len(group) / n_gold_utts) if n_gold_utts else float("nan")
        row["incomplete"] = bool(n_gold_utts and len(group) < 0.90 * n_gold_utts)

        # ---- efficiency ----
        rtfs = [g.rtf for g in group if g.rtf is not None]
        row["rtf_mean"] = float(np.mean(rtfs)) if rtfs else float("nan")
        # Per-request latency, for systems where a request is a unit of work.
        # Empty for everything that reports none, which is every local tool
        # today -- nan rather than 0, so an absent measurement cannot be read
        # as a fast one.
        row.update(latency.latency_metrics([g.latency_s for g in group],
                                           [g.audio_s for g in group],
                                           [g.setup_s for g in group]))

        # ---- power flag ----
        # Keyed on the tier the row ACTUALLY REPORTS, not on phones. The flag
        # was `n_matched_phone < min`, which is 0 for every word-only tool --
        # WhisperX, UnitY2, MMS-FA, NeMo-FA, whisper-timestamped, every
        # timestamped ASR -- so all of them carried a "too few matched units to
        # trust" star on cells with thousands of matched WORDS. The star then
        # meant "word tier" rather than "small sample", which is the opposite
        # of what a reader takes from it.
        #
        # A row with neither tier matched is still flagged: nothing matched is
        # the strongest form of underpowered there is.
        n_mw = sum(g.n_matched_word for g in group)
        row["underpowered"] = max(n_m, n_mw) < min_matched_per_cell

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


def _ctx_columns(row, group, prefix, f1_field, mae_field):
    """Boundary F1, MAE and denominators by recognition context, one set of
    columns per class.

    The classes come from `fabench.score.segmentation.f1_by_word_context`, the
    interior boundaries split by how many of their two words the system got
    right and the two utterance edges kept apart from each other. Counts add
    across utterances, so the cell's figure is over its pooled boundaries
    rather than an average of per-utterance rates.

    ``{prefix}_f1_all_20ms`` is the one to read against the rest of the
    leaderboard. Its denominator is every boundary of the cell, the two
    utterance edges included, and only a boundary with a matched word on each
    side can score. The label-checked columns above already hold every
    INTERIOR boundary in their denominator, so the difference is the edges,
    which they drop from numerator and denominator alike.
    """
    from fabench.score.segmentation import CTX_CLASSES, CTX_VIEWS

    keys = tuple(CTX_CLASSES) + tuple(CTX_VIEWS) + ("pool", "all")
    dicts = [getattr(g, f1_field) for g in group if getattr(g, f1_field)]
    if dicts:
        tols = sorted({m for d in dicts for k in d for m in d[k]["hits"]})
        for k in keys:
            ng = sum(d[k]["n_gold"] for d in dicts if k in d)
            nh = sum(d[k]["n_hyp"] for d in dicts if k in d)
            row[f"n_{prefix}_gold_{k}"] = ng
            row[f"n_{prefix}_hyp_{k}"] = nh
            for ms in tols:
                hits = sum(d[k]["hits"].get(ms, 0) for d in dicts if k in d)
                den = ng + nh
                row[f"{prefix}_f1_{k}_{ms}ms"] = (2.0 * hits / den) if den else float("nan")
    mdicts = [getattr(g, mae_field) for g in group if getattr(g, mae_field)]
    if mdicts:
        for k in tuple(CTX_CLASSES) + tuple(CTX_VIEWS) + ("all",):
            n = sum(d[k]["n"] for d in mdicts if k in d)
            sa = sum(d[k]["sum_abs"] for d in mdicts if k in d)
            row[f"n_{prefix}_mae_{k}"] = n
            row[f"{prefix}_mae_{k}_ms"] = (MS * sa / n) if n else float("nan")


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
