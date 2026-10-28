# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Corpus-level aggregation (Plan 5.9 / Section 6).

Rolls a stream of per-utterance :class:`UttScore` up into one leaderboard row
per system, with the headline columns of both tiers at 20 ms.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence

import numpy as np

from fabench.score import boundary as B
from fabench.score import word
from fabench.score.core import UttScore
from fabench.score.segmentation import F1_TOL_S, SegmentationScore

MS = 1000.0  # seconds -> milliseconds

#: The tolerance the F1 columns are reported at, in ms. 20 ms is what the
#: segmentation literature reports and what the paper's tables print.
F1_TOL_MS = round(F1_TOL_S * MS)


def _group_key(us: UttScore) -> tuple:
    return (us.corpus, us.register, us.aligner, us.mode, us.condition)


def aggregate(
    scores: Iterable[UttScore],
    *,
    extras: Sequence[Callable[[dict, list[UttScore]], None]] = (),
) -> list[dict]:
    """Return the leaderboard rows, one per (corpus, register, system, mode,
    condition), in key order.

    Each callable in ``extras`` is called as ``fn(row, group)`` once a row's
    columns are set, with the UttScores the row was built from, and may add
    to the row or rewrite it in place. FA-Bench itself never passes one.
    """
    groups: dict[tuple, list[UttScore]] = defaultdict(list)
    for us in scores:
        groups[_group_key(us)].append(us)

    leaderboard: list[dict] = []
    for key, group in sorted(groups.items()):
        corpus, register, aligner, mode, condition = key
        # Records the system returned. `group` also holds the reference
        # utterances it returned nothing for (UttScore.absent), which count in
        # every recall and deletion total below; the utterance counts and the
        # MAE see only these.
        present = [g for g in group if not g.absent]
        row = {
            "corpus": corpus,
            "register": register,
            "aligner": aligner,
            "mode": mode,
            "condition": condition,
            "n_utts": len(present),
            "n_absent": len(group) - len(present),
            "n_empty": sum(1 for g in present if g.empty),
        }

        # ---- phone boundary MAE ----
        pooled: list[B.BoundaryError] = [e for g in group for e in g.boundary_errors]
        row["n_boundaries"] = len(pooled)
        row["mae_ms"] = B.mae(pooled) * MS

        # ---- PER ----
        # Insertions have no gold counterpart and are normalised by the gold
        # count per the PER/WER convention.
        n_g = sum(g.n_gold_phone for g in group)
        n_s = sum(g.n_sub_phone for g in group)
        n_d = sum(g.n_del_phone for g in group)
        n_i = sum(g.n_ins_phone for g in group)
        row["per"] = 100.0 * (n_s + n_d + n_i) / n_g if n_g else float("nan")

        # ---- label-checked phone boundary F1 @ 20 ms ----
        # Pooled over the corpus, not averaged per utterance: these are ratios
        # of counts, and a per-utterance mean would weight a 3-boundary
        # utterance the same as a 300-boundary one.
        _all_columns(row, group, "bnd", "bnd_all")

        # ---- word boundary MAE ----
        wm = word.word_boundary_error([g.word_abs_errors for g in group])
        row["wbe_ms"] = wm["wbe_s"] * MS
        row["n_word_boundaries"] = wm["n_word_boundaries"]

        # ---- label-checked word boundary F1 @ 20 ms ----
        # On the silence-filtered word sequences, so "[sil]" from Charsiu and
        # MAPS is not a boundary.
        _all_columns(row, group, "wbnd", "wbnd_all")

        # ---- word timestamps: P/R/F1 @ 20 ms and MAE over each word's start and end ----
        # Two timestamps per word, a hit when the word is label-matched and the
        # same timestamp lies within the width. Precision and recall divide by
        # the system's and the reference's timestamps. The hit is inclusive with
        # the TA_TOL_S float guard, so an error of exactly 20 ms on a 10 ms grid
        # counts. See word.word_timestamp_errors.
        _ts = np.asarray([e for g in group for e in g.wts_start_errors])
        _te = np.asarray([e for g in group for e in g.wts_end_errors])
        _ta = np.concatenate([_ts, _te])
        _tg = sum(g.n_gold_wts for g in group)
        _th = sum(g.n_hyp_wts for g in group)
        row["n_wts_gold"], row["n_wts_hyp"] = _tg, _th
        row["n_wts_matched"] = int(_ta.size)
        row["wts_mae_ms"] = float(_ta.mean()) * MS if _ta.size else float("nan")
        row["wts_start_mae_ms"] = float(_ts.mean()) * MS if _ts.size else float("nan")
        row["wts_end_mae_ms"] = float(_te.mean()) * MS if _te.size else float("nan")
        _s = SegmentationScore(
            n_gold=_tg, n_hyp=_th,
            hits=int((_ta <= F1_TOL_S + B.TA_TOL_S).sum()), tol_s=F1_TOL_S)
        row["wts_precision"] = _s.precision
        row["wts_recall"] = _s.recall
        row["wts_f1"] = _s.f1

        # ---- WER ----
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
        row["wer"] = 100.0 * (n_ws + n_wd + n_wi) / n_gw if n_gw else float("nan")

        for fn in extras:
            fn(row, group)
        leaderboard.append(row)

    return leaderboard


def _all_columns(row: dict, group: Sequence[UttScore], prefix: str, field: str) -> None:
    """``{prefix}_f1_all_20ms`` and its two denominators, summed over the cell.

    The denominators are every boundary of the cell, the two utterance edges
    included, and only a boundary with a matched unit on each side can score.
    A cell where no utterance scored the tier reads NaN in all three, so a
    word-only system has no phone F1 rather than one over zero boundaries.
    """
    dicts = [getattr(g, field) for g in group if getattr(g, field)]
    ng = nh = f1 = float("nan")
    if dicts:
        ng = sum(d["n_gold"] for d in dicts)
        nh = sum(d["n_hyp"] for d in dicts)
        hits = sum(d["hits"] for d in dicts)
        den = ng + nh
        f1 = (2.0 * hits / den) if den else float("nan")
    row[f"n_{prefix}_gold_all"] = ng
    row[f"n_{prefix}_hyp_all"] = nh
    row[f"{prefix}_f1_all_{F1_TOL_MS}ms"] = f1
