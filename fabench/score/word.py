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
    """Pooled |start| and |end| offsets over matched words, in seconds.

    Words are matched by canonical label via the same monotonic aligner as
    phones (labels here are lowercased word strings; normalization is identity
    for words).
    """
    gl = [w.label for w in gold_words]
    hl = [w.label for w in hyp_words]
    aln = nw_align(gl, hl)
    errs: list[float] = []
    for gi, hj in aln.matched(gl, hl):
        g, h = gold_words[gi], hyp_words[hj]
        errs.append(abs(h.start - g.start))
        errs.append(abs(h.end - g.end))
    return errs


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
    olign ablations sitting 0.04 ms apart, at a cost of 0.078-0.815 ms against
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
