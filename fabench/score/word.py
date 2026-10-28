# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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

    Words are matched by lowercased label via the same monotonic aligner as
    phones, as the word F1, WER and word classes already were. This used to
    compare raw labels, so a recognizer's "The" against the reference's "the"
    lost both boundaries of that word here while counting as a hit in F1.

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
    gl = [w.label.lower() for w in gold_words]
    hl = [w.label.lower() for w in hyp_words]
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


def word_timestamp_errors(
    gold_words: Sequence[Interval],
    hyp_words: Sequence[Interval],
    matched: Sequence[tuple[int, int]],
) -> tuple[list[float], list[float]]:
    """Start error and end error, in seconds, of every matched word.

    THE UNIT IS THE WORD TIMESTAMP. Every reference word owns a start and an
    end, and a timestamp is judged against the same timestamp of the system
    word matched to it, nothing else. A boundary belongs to two words, so the
    boundary metrics above need a rule for every mix of recognised, substituted,
    deleted and inserted neighbours. A timestamp belongs to one, so a
    recognition error costs the word it happened to and its neighbours keep
    their own timestamps. A deleted word whose time the next word absorbs shows
    up as that word's real start error, which is what an API user receives.

    At a joint where both sides tile, the end of one word and the start of the
    next are the same time and carry the same error. That is two timestamps a
    user receives, so both count. Read the start and end lists apart to see
    each once.

    ``matched`` is the label-matched pairs (gold index, hyp index) of the same
    sequences, so only a correct word's timestamps are scored.
    """
    starts = [abs(hyp_words[j].start - gold_words[i].start) for i, j in matched]
    ends = [abs(hyp_words[j].end - gold_words[i].end) for i, j in matched]
    return starts, ends


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

