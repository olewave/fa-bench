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

"""Per-utterance scoring: gold + hypothesis alignment -> one UttScore.

Kept separate from aggregation so the expensive matching runs once per item and
the corpus rollup (bootstrap, grouping) is pure arithmetic over UttScores.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fabench.schema import Utterance
from fabench.score import boundary, recall, word
from fabench.score.matched import matched_indices, nw_align


def identity(label: str) -> str:
    return label


def _prep_phones(phones, canon_fn):
    """Return (kept_intervals, canonical_labels) with DELETE phones removed and
    UNMAPPED phones given a unique never-matching token."""
    from fabench.normalize import DELETE, UNMAPPED

    ivs, labels = [], []
    for i, p in enumerate(phones):
        c = canon_fn(p.label)
        if c == DELETE:
            continue
        if c == UNMAPPED:
            c = f"{UNMAPPED}:{i}"  # unique -> never matches, still counted
        ivs.append(p)
        labels.append(c)
    return ivs, labels


# Word-tier silence pseudo-words some aligners emit (charsiu "[sil]", maps "sil",
# MFA optional "sp"/"spn"). Dropped before word matching so they never count as
# a real word boundary in the word-boundary benchmark (scoring.boundary_unit).
_SILENCE_WORDS = frozenset({"[sil]", "sil", "sp", "spn", "<sil>", "silence", ""})


def _word_boundary_errors(gold_words, hyp_words):
    """Dual-edge boundary errors over matched WORD pairs (the word-boundary
    benchmark). Same machinery as phones — monotonic label match, then onset +
    offset of each matched pair — but over the word tier, with silence
    pseudo-words dropped. Manner context is a flat ``"word"`` (utterance edges
    still register as ``"silence"`` via the out-of-range rule in
    ``build_boundary_errors``, so the interior-vs-edge split carries over).

    Returns ``(boundary_errors, matched_pairs, kept_gold_words, kept_hyp_words)``.
    """
    gw = [w for w in gold_words if w.label.lower() not in _SILENCE_WORDS]
    hw = [w for w in hyp_words if w.label.lower() not in _SILENCE_WORDS]
    gl = [w.label.lower() for w in gw]
    hl = [w.label.lower() for w in hw]
    matched = nw_align(gl, hl).matched(gl, hl)
    errs = boundary.build_boundary_errors(matched, gw, hw, lambda _label: "word")
    return errs, matched, gw, hw


@dataclass
class UttScore:
    utt_id: str
    speaker_id: str
    corpus: str
    register: str
    condition: str
    aligner: str
    mode: str

    boundary_errors: list[boundary.BoundaryError] = field(default_factory=list)
    word_abs_errors: list[float] = field(default_factory=list)

    # "fabench" (default, general-purpose scorer) or "mfa_paper" (bridges to the
    # real kalpy.evaluation.align_phones + ported data_prep.R filter). Only ever
    # set explicitly by fabench.score.mfa_paper.cell.score_cell; the default
    # keeps every existing score_pair() call site byte-for-byte unchanged.
    protocol: str = "fabench"

    n_matched_phone: int = 0
    n_gold_phone: int = 0
    n_hyp_phone: int = 0
    # Boundary-detection counts (fabench.score.segmentation). Paired by TIME
    # within a tolerance and label-agnostic, unlike everything above -- this is
    # what makes insertions cost precision instead of being invisible to a
    # matched-path average.
    n_gold_bnd: int = 0
    n_hyp_bnd: int = 0
    n_bnd_hits: int = 0
    n_gold_wbnd: int = 0
    n_hyp_wbnd: int = 0
    n_wbnd_hits: int = 0
    # Edit decomposition of the phone alignment. n_match + n_sub + n_del ==
    # n_gold_phone exactly, so these say WHY a gold phone left the matched path
    # -- ARR alone cannot separate "labelled differently" from "never emitted".
    n_sub_phone: int = 0
    n_del_phone: int = 0
    n_ins_phone: int = 0
    n_matched_word: int = 0
    n_gold_word: int = 0
    n_hyp_word: int = 0
    # Edit decomposition of the WORD alignment, same shape as the phone one.
    # Required for track-2 systems (timestamped ASRs): they decode their own
    # transcript, so a bad word MAE is unattributable without WER --
    # recognition failure and timing failure look identical. See
    # fabench/timestamp_asrs/base.py, which has specified this all along.
    n_sub_word: int = 0
    n_del_word: int = 0
    n_ins_word: int = 0

    # Gold indices of matched phones — needed for the cross-system common-matched
    # set (survivor-bias guard, Plan 5.1).
    matched_gold_phone_idx: list[int] = field(default_factory=list)

    rtf: float | None = None


def score_pair(
    gold: Utterance,
    hyp: Utterance,
    *,
    condition: str,
    aligner: str,
    mode: str,
    gold_canon: Callable[[str], str] = identity,
    hyp_canon: Callable[[str], str] = identity,
    manner_of_canonical: Callable[[str], str] = lambda c: "vowel",
    score_phones: bool = True,
    score_words: bool = True,
    manner_match: bool = False,
    matcher: str = "levenshtein",
    matcher_lambda: float = 2.0,
    exclude_silence_boundaries: bool = False,
    boundary_unit: str = "phone",
    rtf: float | None = None,
) -> UttScore:
    """Score one (gold, hyp) pair into a UttScore.

    ``gold_canon`` / ``hyp_canon`` map each source's raw phone labels to the
    shared canonical inventory (Plan S2). ``manner_of_canonical`` maps a
    canonical label to a coarse manner class (Plan 5.4).

    ``manner_match`` toggles the MFA-2026 paper's exclusion rule
    (arXiv:2606.18466): matched phone pairs whose paper-manner classes differ are
    dropped from the *boundary* pool (MAE/TA/per-type/common-matched). ARR and
    InsertRate keep the full label-matched set, so the anti-gaming pair is
    unchanged.

    ``matcher`` selects the alignment: ``"levenshtein"`` (label-only NW) or
    ``"boundary_distance"`` (the paper's modified Levenshtein, whose cost also
    rewards time-close boundaries — breaks same-label ties toward the nearest
    boundary).
    """
    us = UttScore(
        utt_id=gold.utt_id,
        speaker_id=gold.speaker_id,
        corpus=gold.source_corpus,
        register=gold.register,
        condition=condition,
        aligner=aligner,
        mode=mode,
        rtf=rtf,
    )

    if boundary_unit == "word" and score_words and gold.words and hyp.words:
        # Word-boundary benchmark: us.boundary_errors carries WORD boundaries, so
        # the whole downstream pipeline (aggregate -> leaderboard MAE/median/TA/CI,
        # per-type, speaker-macro) reports word-level numbers unchanged. The count
        # fields are populated with WORD counts so ARR/InsertRate are word-level
        # too. common-matched is a phone concept -> opt out (empty idx list).
        us.boundary_errors, wmatched, gw, hw = _word_boundary_errors(gold.words, hyp.words)
        us.n_matched_phone, us.n_gold_phone, us.n_hyp_phone = len(wmatched), len(gw), len(hw)
        us.matched_gold_phone_idx = []
    elif boundary_unit == "phone" and score_phones and gold.phones and hyp.phones:
        # Canonicalize; drop DELETE phones (e.g. glottal stop, dropped by the
        # standard folding), keep UNMAPPED ones with a unique token so they are
        # counted but never spuriously match (Plan S2).
        gold_ivs, gcanon = _prep_phones(gold.phones, gold_canon)
        hyp_ivs, hcanon = _prep_phones(hyp.phones, hyp_canon)
        # Alignment. Default label-only NW; paper uses a boundary-distance-aware
        # modified Levenshtein. manner_match then scores boundary error on *all*
        # aligned pairs (exact + manner-consistent substitutions) and drops
        # manner-mismatched pairs; ARR keeps the exact-label matches only.
        if matcher == "boundary_distance" or manner_match:
            from fabench.normalize import manner_class_paper
        if matcher == "boundary_distance":
            from fabench.score.matched import boundary_aware_align

            aln = boundary_aware_align(
                gold_ivs, gcanon, hyp_ivs, hcanon, manner_class_paper,
                lam=matcher_lambda,
            )
        elif manner_match:
            aln = nw_align(gcanon, hcanon)
        else:
            aln = None

        if aln is not None:
            matched = aln.matched(gcanon, hcanon)
            if manner_match:
                bmatched = [
                    (gi, hj)
                    for gi, hj in aln.pairs
                    if gi is not None
                    and hj is not None
                    and manner_class_paper(gcanon[gi]) == manner_class_paper(hcanon[hj])
                ]
            else:
                bmatched = matched
        else:
            matched = matched_indices(gcanon, hcanon)
            bmatched = matched
        # ARR / InsertRate use the full label-matched set (Plan 5.6).
        us.n_matched_phone = len(matched)
        us.n_gold_phone = len(gold_ivs)
        us.n_hyp_phone = len(hyp_ivs)
        # Boundary detection, on the SAME interval sequences but paired by time
        # rather than by label -- so it charges for over-segmentation, which the
        # matched-path MAE structurally cannot.
        from fabench.score import segmentation as _seg

        _s = _seg.score_segmentation(gold_ivs, hyp_ivs)
        us.n_gold_bnd, us.n_hyp_bnd, us.n_bnd_hits = _s.n_gold, _s.n_hyp, _s.hits
        # SUB / DEL / INS on the same canonical label sequences the matcher used,
        # so the decomposition is consistent with ARR by construction.
        from fabench.score.matched import edit_counts

        _, us.n_sub_phone, us.n_del_phone, us.n_ins_phone = edit_counts(gcanon, hcanon)
        # Common-matched (survivor-bias guard, Plan 5.1) follows the scored pool.
        us.matched_gold_phone_idx = [gi for gi, _ in bmatched]

        # Manner context uses the gold canonical label of each neighbour.
        def manner_fn(raw_gold_label: str) -> str:
            return manner_of_canonical(gold_canon(raw_gold_label))

        us.boundary_errors = boundary.build_boundary_errors(
            bmatched, gold_ivs, hyp_ivs, manner_fn,
            skip_silence_adjacent=exclude_silence_boundaries,
        )

    if score_words and gold.words and hyp.words:
        us.word_abs_errors = word.word_abs_errors(gold.words, hyp.words)
        # Word-boundary detection, same time-based label-agnostic pairing as the
        # phone tier. This is the tier the collar-based literature actually uses
        # (AMI-IHM, MGB), and the only tier word-only systems -- whisperx,
        # crisperwhisper -- appear on at all.
        from fabench.score import segmentation as _wseg

        _ws = _wseg.score_segmentation(gold.words, hyp.words)
        us.n_gold_wbnd, us.n_hyp_wbnd, us.n_wbnd_hits = (
            _ws.n_gold, _ws.n_hyp, _ws.hits
        )
        # word match counts for a word-level ARR (reuse matcher on labels)
        from fabench.score.matched import edit_counts, recall_counts

        # Silence pseudo-words are NOT recognition units. Charsiu and MAPS emit
        # "[sil]"/"sil" in the word tier (15 tokens where MFA emits 13), and
        # counting them charged both a ~25% WER made entirely of insertions --
        # for forced aligners, which are handed the reference and cannot
        # misrecognise anything. Drop them on both sides so WER measures words.
        _WSIL = {"sil", "[sil]", "<sil>", "sp", "spn", "<eps>", "!sil",
                 "silence", "", "<unk>"}

        def _words(seq):
            return [w.label.lower() for w in seq
                    if w.label.lower().strip() not in _WSIL]

        gl = _words(gold.words)
        hl = _words(hyp.words)
        us.n_matched_word, us.n_gold_word, us.n_hyp_word = recall_counts(gl, hl)
        # WER's numerator, from the SAME label sequences and the same NW
        # alignment the phone tier uses -- one implementation, so the word and
        # phone decompositions cannot disagree about what a substitution is.
        _, us.n_sub_word, us.n_del_word, us.n_ins_word = edit_counts(gl, hl)

    return us


def phone_recall(us: UttScore) -> tuple[float, float]:
    return (
        recall.arr(us.n_matched_phone, us.n_gold_phone),
        recall.insertion_rate(us.n_matched_phone, us.n_hyp_phone),
    )
