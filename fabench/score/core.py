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
from fabench.score.matched import nw_align


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
    #: Each matched unit's start and end, tagged onset and offset. Feeds the
    #: onset/offset columns only. `boundary_errors` counts BOUNDARIES and so
    #: cannot carry that split, two contiguous units sharing one boundary.
    unit_edge_errors: list[boundary.BoundaryError] = field(default_factory=list)
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
    #: hits keyed by tolerance in whole ms, for the F1 sweep. Only the hit
    #: count moves with the tolerance, so the gold and hyp counts above serve
    #: every width. Default factories, because a score built without boundary
    #: scoring must still compare equal to one built with it.
    n_bnd_hits_by_tol: dict = field(default_factory=dict)
    n_wbnd_hits_by_tol: dict = field(default_factory=dict)
    #: LABEL-CHECKED hits, same boundaries and same widths, but a hit must also
    #: agree about which boundary it is: the units on BOTH sides have to be the
    #: aligned, same-labelled units. `_lbl` is the strict set, `_pos` allows a
    #: substitution on either side (the units correspond, the labels need not).
    #: The gap to the time-only count above is the share of hits that credit a
    #: neighbouring boundary. See segmentation.labelled_hits_by_tol.
    n_bnd_hits_lbl_by_tol: dict = field(default_factory=dict)
    n_bnd_hits_pos_by_tol: dict = field(default_factory=dict)
    n_wbnd_hits_lbl_by_tol: dict = field(default_factory=dict)
    n_wbnd_hits_pos_by_tol: dict = field(default_factory=dict)
    #: The word tier's label-checked score runs on the SILENCE-FILTERED word
    #: sequences, because a "[sil]" pseudo-word is not a word and the WER path
    #: already drops it. Its denominators therefore differ from n_gold_wbnd /
    #: n_hyp_wbnd for the two systems that emit them (Charsiu, MAPS), so they
    #: are carried here, together with the time-only hit count over the same
    #: filtered sequences -- which is the only baseline the label-checked score
    #: can honestly be differenced against.
    n_gold_wbnd_lbl: int = 0
    n_hyp_wbnd_lbl: int = 0
    n_wbnd_hits_nosil_by_tol: dict = field(default_factory=dict)
    #: BY RECOGNITION CONTEXT (fabench.score.segmentation.f1_by_word_context).
    #: Every boundary is classed by the words around it, the interior three
    #: ways and the two utterance edges apart, so a boundary can be read
    #: against the words the system got right there rather than against the
    #: utterance as a whole. ``{key: {"n_gold","n_hyp","hits":{ms:count}}}``
    #: over the classes, their named unions, ``pool`` and ``all``; ``all`` is
    #: the whole utterance's denominators with only the matched-both hits, so
    #: it charges a recognition error exactly like a timing error. The MAE
    #: dicts are ``{key: {"n","sum_abs"}}`` over the same classes.
    wbnd_ctx: dict = field(default_factory=dict)
    bnd_ctx: dict = field(default_factory=dict)
    wbnd_ctx_mae: dict = field(default_factory=dict)
    bnd_ctx_mae: dict = field(default_factory=dict)
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
    #: Wall time for the ONE request that produced this utterance, and the
    #: audio it was given. rtf cannot stand in: on the batch path it is one
    #: amortised figure for the whole cell, and it divides by duration, which
    #: for a network endpoint buries a fixed per-request cost. See
    #: fabench/score/latency.py.
    latency_s: float | None = None
    audio_s: float | None = None
    #: DNS + TCP + TLS floor to this endpoint from the machine that ran the
    #: sweep. Network, not service; recorded so lat_fixed_s can be read net.
    setup_s: float | None = None
    #: How many utterances the SPLIT has, not how many were scored. The two
    #: differ when a tool drops items and nothing else in the row shows it: a
    #: Chirp 2 cell holding 837 of Buckeye dev's 4,456 scored as a clean row at
    #: WER 19.8 against ~14.7 for the complete ones. Wrong, not merely partial,
    #: and invisible.
    n_gold_utts: int | None = None


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
    input_tokens: list[str] | None = None,
    rtf: float | None = None,
    latency_s: float | None = None,
    audio_s: float | None = None,
    setup_s: float | None = None,
    n_gold_utts: int | None = None,
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
        latency_s=latency_s,
        audio_s=audio_s,
        setup_s=setup_s,
        n_gold_utts=n_gold_utts,
    )

    if input_tokens and score_words and hyp.words:
        # Map the aligner's output back onto the words it was GIVEN, before any
        # word-tier metric sees it -- the label metrics (WER/S/D/I) and the
        # boundary metrics must agree about how many words the system produced.
        #
        # `input_tokens` is the real input: the reference words for a
        # gold-transcript aligner, the ASR's decoded words for a cascade.
        # Passing gold here for a cascade would erase the recognition error
        # that track exists to measure, which is why the caller supplies it
        # rather than this function assuming `gold`.
        from dataclasses import replace as _replace

        from fabench.aligners.relabel import relabel_to_input
        hyp = _replace(hyp, words=relabel_to_input(input_tokens, hyp.words))

    # THE WORD CLASSING BOTH TIERS USE. Computed once, before either tier is
    # scored, because a phone boundary takes the class of the word holding it
    # and the two tiers must agree about which words those are. The reference
    # side is classed by the transcript the system was GIVEN, so every system
    # handed the same words sees the same reference classes; the recognized
    # side is classed by what the system returned. A system that emits no word
    # tier at all was still handed words and timed them, so its phones are
    # classed by those, which is the reference classing exactly.
    _cgw = [w for w in gold.words if w.label.lower() not in _SILENCE_WORDS]
    _chw = [w for w in hyp.words if w.label.lower() not in _SILENCE_WORDS]
    _cgl = [w.label.lower() for w in _cgw]
    _chl = [w.label.lower() for w in _chw]
    _c_gold_matched = None
    if input_tokens is not None:
        _itok = [str(t).lower() for t in input_tokens]
        _c_gold_matched = {gi for gi, _ in nw_align(_cgl, _itok).matched(_cgl, _itok)}
    if _chw:
        _c_wmatched = nw_align(_cgl, _chl).matched(_cgl, _chl)
    elif input_tokens is not None:
        _chw, _c_wmatched = _cgw, [(i, i) for i in range(len(_cgw))]
    else:
        _c_wmatched = []

    if boundary_unit == "word" and score_words and gold.words and hyp.words:
        # Word-boundary benchmark: us.boundary_errors carries WORD boundaries, so
        # the whole downstream pipeline (aggregate -> leaderboard MAE/median/TA/CI,
        # per-type, speaker-macro) reports word-level numbers unchanged. The count
        # fields are populated with WORD counts so ARR/InsertRate are word-level
        # too. common-matched is a phone concept -> opt out (empty idx list).
        us.boundary_errors, wmatched, gw, hw = _word_boundary_errors(gold.words, hyp.words)
        us.unit_edge_errors = boundary.unit_edge_errors(
            wmatched, gw, hw, lambda _label: "word")
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
            # nw_align rather than matched_indices, which calls it anyway: the
            # label-checked boundary score needs the alignment itself, not
            # just the pairs whose labels agreed.
            aln = nw_align(gcanon, hcanon)
            matched = aln.matched(gcanon, hcanon)
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
        us.n_bnd_hits_by_tol = _seg.hits_by_tolerance(
            _seg.boundaries_from_intervals(gold_ivs),
            _seg.boundaries_from_intervals(hyp_ivs))
        # The same boundaries and widths, scored with the identity check.
        us.n_bnd_hits_lbl_by_tol = _seg.labelled_hits_by_tol(
            gold_ivs, hyp_ivs, matched)
        us.n_bnd_hits_pos_by_tol = _seg.labelled_hits_by_tol(
            gold_ivs, hyp_ivs, aln.aligned())
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
        us.unit_edge_errors = boundary.unit_edge_errors(
            bmatched, gold_ivs, hyp_ivs, manner_fn)
        if _cgw:
            # THE PHONE'S OWN LABEL DECIDES. `matched` is the canonical-label
            # alignment of the phones, and each phone's flag is whether it is
            # in it, the rule the word tier applies to words. Inheriting the
            # word's flag instead marked every phone matched on Track 1 and
            # bnd_f1_all fell to a time-only match while PER read 30 percent.
            _pg = {gi for gi, _ in matched}
            _ph = {hj for _, hj in matched}
            us.bnd_ctx = _seg.f1_by_word_context(
                _cgw, _chw, _c_wmatched, gold_ivs, hyp_ivs,
                gold_matched=_c_gold_matched,
                gold_unit_matched=_pg, hyp_unit_matched=_ph)
            us.bnd_ctx_mae = _seg.mae_by_word_context(
                _cgw, _chw, _c_wmatched, aln.aligned(), gold_ivs, hyp_ivs,
                gold_matched=_c_gold_matched, gold_unit_matched=_pg)

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
        us.n_wbnd_hits_by_tol = _wseg.hits_by_tolerance(
            _wseg.boundaries_from_intervals(gold.words),
            _wseg.boundaries_from_intervals(hyp.words))
        # Label-checked, on the silence-filtered sequences the word-boundary
        # MAE path already uses, with its own denominators and its own
        # time-only baseline over exactly those sequences.
        _gwl = [w for w in gold.words if w.label.lower() not in _SILENCE_WORDS]
        _hwl = [w for w in hyp.words if w.label.lower() not in _SILENCE_WORDS]
        _gll = [w.label.lower() for w in _gwl]
        _hll = [w.label.lower() for w in _hwl]
        _waln = nw_align(_gll, _hll)
        us.n_gold_wbnd_lbl = len(_wseg.boundaries_from_intervals(_gwl))
        us.n_hyp_wbnd_lbl = len(_wseg.boundaries_from_intervals(_hwl))
        us.n_wbnd_hits_nosil_by_tol = _wseg.hits_by_tolerance(
            _wseg.boundaries_from_intervals(_gwl),
            _wseg.boundaries_from_intervals(_hwl))
        us.n_wbnd_hits_lbl_by_tol = _wseg.labelled_hits_by_tol(
            _gwl, _hwl, _waln.matched(_gll, _hll))
        us.n_wbnd_hits_pos_by_tol = _wseg.labelled_hits_by_tol(
            _gwl, _hwl, _waln.aligned())
        if _gwl:
            us.wbnd_ctx = _wseg.f1_by_word_context(
                _gwl, _hwl, _waln.matched(_gll, _hll),
                gold_matched=_c_gold_matched)
            us.wbnd_ctx_mae = _wseg.mae_by_word_context(
                _gwl, _hwl, _waln.matched(_gll, _hll), _waln.aligned(),
                gold_matched=_c_gold_matched)
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
