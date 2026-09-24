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

"""Word Boundary Error (Plan 5.5).

Dual-edge (start + end) offsets over matched words. This is the only
phone-independent metric, so it is the sole table where a word-only aligner
(WhisperX) appears. We report **micro** (per-boundary, primary) and **macro**
(per-word -> per-utt double average) — they diverge and macro is the more
distortable one, so both are surfaced.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from fabench.schema import Interval
from fabench.score.matched import nw_align


def word_abs_errors(
    gold_words: Sequence[Interval],
    hyp_words: Sequence[Interval],
) -> list[float]:
    """Absolute time error at each MATCHED BOUNDARY, in seconds.

    Words are matched by canonical label via the same monotonic aligner as
    phones (labels here are lowercased word strings; normalization is identity
    for words).

    ONE ENTRY PER BOUNDARY, not two per word. This used to walk the matched
    words and append each one's start and its end. Adjacent words share a time
    in 89.6% of TIMIT and 94.9% of Buckeye, so an interior boundary between two
    matched words went in twice, and the two entries were the same number in
    98-99% of cases. That gave the easy interior double the weight of the
    utterance edges and of boundaries with one matched neighbour, which are
    exactly the ones the benchmark reports on. Deduplicating raises word MAE by
    3 to 5 ms across the systems and changes the reported quantity from a mean
    over word edges to a mean over boundaries, which is what the paper says.

    A BOUNDARY IS MATCHED WHEN EVERY UNIT BESIDE IT MATCHED. An utterance edge
    and a boundary against an interior silence gap have one unit beside them,
    so that one decides; silence is not a unit and matches trivially. This is
    the same rule Boundary F1 uses, so the two metrics now filter alike and
    differ only in what they do with the survivors. On Track 1 nothing turns on
    it, since the reference transcript is given and every unit matches.

    The hypothesis time comes from the left unit's end, or from the right
    unit's start where the boundary opens an utterance or follows a gap. Where
    both exist they are the same time unless the hypothesis puts a gap where
    the reference has none, which is 1-2% of boundaries.
    """
    gl = [w.label for w in gold_words]
    hl = [w.label for w in hyp_words]
    aln = nw_align(gl, hl)
    matched = dict(aln.matched(gl, hl))
    # gold boundary time -> [unit ending here, unit starting here]
    sides: dict[float, list[int | None]] = {}
    for i, w in enumerate(gold_words):
        sides.setdefault(round(w.start, 9), [None, None])[1] = i
        sides.setdefault(round(w.end, 9), [None, None])[0] = i
    errs: list[float] = []
    for left, right in sides.values():
        near = [i for i in (left, right) if i is not None]
        if not all(i in matched for i in near):
            continue
        if left is not None:
            errs.append(abs(hyp_words[matched[left]].end - gold_words[left].end))
        else:
            errs.append(abs(hyp_words[matched[right]].start - gold_words[right].start))
    return errs


def word_tolerance_accuracy(
    per_utt_errors: Sequence[Sequence[float]],
    taus_s: Sequence[float],
) -> dict[int, float]:
    """Share of matched word boundaries within each tolerance.

    The phone tier has had this since the first release and the word tier never
    did, so a word-only system had no tolerance column at all and the published
    sweep covered half the benchmark. Same pooled errors the mean is taken over,
    so TA and MAE describe the same set of boundaries.
    """
    all_errs = [e for utt in per_utt_errors for e in utt]
    if not all_errs:
        return {round(t * 1000): float("nan") for t in taus_s}
    a = np.asarray(all_errs)
    return {round(t * 1000): float((a <= t).mean()) for t in taus_s}


def word_boundary_error(
    per_utt_errors: Sequence[Sequence[float]],
) -> dict:
    """Given per-utterance pooled word abs-errors, return WBE (s).

    ONE number: the mean over *all* word boundaries in the corpus. The
    per-utterance macro average was reported beside it and carried almost no
    information -- across the published cells the two differ by well under 1%
    (46.96 vs 47.24 ms for whisperx on timit/core_test) -- so a reader spent
    attention deciding which to read and learned nothing from the answer.
    The phone tier's speaker-macro average went the same way and for the same
    reason: measured across the published cells it reordered nothing except four
    near-identical variants sitting 0.04 ms apart, at a cost of 0.078-0.815 ms against
    the plain mean. Balanced averaging is a real technique; two columns that
    agree are not.
    """
    all_errs = [e for utt in per_utt_errors for e in utt]
    per_utt_means = [float(np.mean(utt)) for utt in per_utt_errors if len(utt)]
    return {
        "wbe_s": float(np.mean(all_errs)) if all_errs else float("nan"),
        "n_word_boundaries": len(all_errs),
        "n_utts_with_words": len(per_utt_means),
    }

