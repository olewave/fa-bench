# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Per-utterance scoring: gold + hypothesis alignment -> one UttScore.

Kept separate from aggregation so the expensive matching runs once per item and
the corpus rollup is pure arithmetic over UttScores.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from types import SimpleNamespace

from fabench.aligners.relabel import SILENCE as _RELABEL_SILENCE
from fabench.schema import Utterance
from fabench.score import boundary, word
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
# ONE set, the relabeller's, for word matching, WER and relabelling alike. There
# used to be three, and two of them lacked "<eps>", "!sil" and "<unk>"; no word
# in any reference or hypothesis is one of those, so merging moved no number.
_SILENCE_WORDS = frozenset(_RELABEL_SILENCE)


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

    n_gold_phone: int = 0
    #: LABEL-CHECKED F1 AT 20 MS (segmentation.f1_all). ``{"n_gold", "n_hyp",
    #: "hits"}`` over every boundary of the utterance, the two edges included,
    #: where only a boundary with a matched unit on each side can be a hit. The
    #: word tier's runs on the SILENCE-FILTERED word sequences, because a
    #: "[sil]" pseudo-word is not a word and the WER path already drops it.
    #: Empty when the tier was not scored, so a cell where no utterance scored
    #: it reports no F1 rather than one over zero boundaries.
    bnd_all: dict = field(default_factory=dict)
    wbnd_all: dict = field(default_factory=dict)
    #: WORD TIMESTAMPS (word.word_timestamp_errors). Each reference word owns a
    #: start and an end. The lists hold the start and end errors, in seconds, of
    #: every label-matched word on the silence-filtered sequences. The counts are
    #: two per word on those same sequences, so an absent or empty hypothesis
    #: still charges recall for every reference timestamp.
    wts_start_errors: list[float] = field(default_factory=list)
    wts_end_errors: list[float] = field(default_factory=list)
    n_gold_wts: int = 0
    n_hyp_wts: int = 0
    # Edit decomposition of the phone alignment, PER's numerator. n_match +
    # n_sub + n_del == n_gold_phone exactly.
    n_sub_phone: int = 0
    n_del_phone: int = 0
    n_ins_phone: int = 0
    n_gold_word: int = 0
    # Edit decomposition of the WORD alignment, same shape as the phone one.
    # Required for track-2 systems (timestamped ASRs): they decode their own
    # transcript, so a bad word MAE is unattributable without WER --
    # recognition failure and timing failure look identical. See
    # fabench/timestamp_asrs/base.py, which has specified this all along.
    n_sub_word: int = 0
    n_del_word: int = 0
    n_ins_word: int = 0

    #: True for a reference utterance the system returned no record for. It is
    #: scored against an empty hypothesis, so its boundaries count against F1
    #: recall and its words and phones as deletions, while MAE still sees only
    #: the records the system did return.
    absent: bool = False
    #: True when the system's record for this utterance holds no words and no
    #: phones. Scored like an absent one, and counted apart from it, so a
    #: reader can see how many utterances a MAE was not computed over.
    empty: bool = False
    #: Room for whatever a caller's ``extras`` (see score_pair) keep per
    #: utterance. FA-Bench itself never fills it.
    extra: dict = field(default_factory=dict)


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
    extras: Sequence[Callable[[UttScore, SimpleNamespace], None]] = (),
    context: dict | None = None,
) -> UttScore:
    """Score one (gold, hyp) pair into a UttScore.

    ``gold_canon`` / ``hyp_canon`` map each source's raw phone labels to the
    shared canonical inventory (Plan S2). ``manner_of_canonical`` maps a
    canonical label to a coarse manner class (Plan 5.4).

    ``manner_match`` toggles the MFA-2026 paper's exclusion rule
    (arXiv:2606.18466): matched phone pairs whose paper-manner classes differ are
    dropped from the *boundary* pool (MAE). PER keeps the full label alignment.

    ``matcher`` selects the alignment: ``"levenshtein"`` (label-only NW) or
    ``"boundary_distance"`` (the paper's modified Levenshtein, whose cost also
    rewards time-close boundaries — breaks same-label ties toward the nearest
    boundary).

    THE EXTENSION POINT. Each callable in ``extras`` is called once, as
    ``fn(us, ctx)``, after every field above is set. ``ctx`` is a namespace of
    what this function computed on the way, so a caller can score more from
    the same alignments without running them again. Its keys are ``gold``,
    ``hyp`` (relabelled onto ``input_tokens`` where that applies), the
    options, the word classing both tiers share (``cgw``, ``chw``,
    ``c_wmatched``, ``c_gold_matched``), ``word_mode`` (``wmatched``, ``gw``,
    ``hw``), ``phone`` (``gold_ivs``, ``hyp_ivs``, ``aln``, ``matched``,
    ``bmatched``, ``manner_fn``) and ``words`` (``gwl``, ``hwl``, ``waln``,
    ``gl``, ``hl``), each of the last three None when its tier was not
    scored, plus every key of ``context``, which this function passes through
    untouched. FA-Bench itself never passes an extra.
    """
    us = UttScore(
        utt_id=gold.utt_id,
        speaker_id=gold.speaker_id,
        corpus=gold.source_corpus,
        register=gold.register,
        condition=condition,
        aligner=aligner,
        mode=mode,
        empty=not hyp.words and not hyp.phones,
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

    word_mode = phone = words = None
    # AN EMPTY HYPOTHESIS IS SCORED, NOT SKIPPED. Each tier below runs whenever
    # the REFERENCE has units, so a system that returned nothing for an
    # utterance is charged for every boundary and unit it missed. These gates
    # used to require hyp units too, and an empty record then counted for
    # nothing: no recall miss, no deletion, which rewarded giving up.
    if boundary_unit == "word" and score_words and gold.words:
        # Word-boundary benchmark: us.boundary_errors carries WORD boundaries, so
        # the leaderboard MAE reports word-level numbers unchanged.
        us.boundary_errors, wmatched, gw, hw = _word_boundary_errors(gold.words, hyp.words)
        us.n_gold_phone = len(gw)
        word_mode = SimpleNamespace(wmatched=wmatched, gw=gw, hw=hw)
    elif boundary_unit == "phone" and score_phones and gold.phones:
        # Canonicalize; drop DELETE phones (e.g. glottal stop, dropped by the
        # standard folding), keep UNMAPPED ones with a unique token so they are
        # counted but never spuriously match (Plan S2).
        gold_ivs, gcanon = _prep_phones(gold.phones, gold_canon)
        hyp_ivs, hcanon = _prep_phones(hyp.phones, hyp_canon)
        # Alignment. Default label-only NW; paper uses a boundary-distance-aware
        # modified Levenshtein. manner_match then scores boundary error on *all*
        # aligned pairs (exact + manner-consistent substitutions) and drops
        # manner-mismatched pairs.
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
        us.n_gold_phone = len(gold_ivs)
        # SUB / DEL / INS on the same canonical label sequences the matcher used.
        from fabench.score.matched import edit_counts

        _, us.n_sub_phone, us.n_del_phone, us.n_ins_phone = edit_counts(gcanon, hcanon)

        # Manner context uses the gold canonical label of each neighbour.
        def manner_fn(raw_gold_label: str) -> str:
            return manner_of_canonical(gold_canon(raw_gold_label))

        us.boundary_errors = boundary.build_boundary_errors(
            bmatched, gold_ivs, hyp_ivs, manner_fn,
            skip_silence_adjacent=exclude_silence_boundaries,
        )
        if _cgw:
            # THE PHONE'S OWN LABEL DECIDES. `matched` is the canonical-label
            # alignment of the phones, and each phone's flag is whether it is
            # in it, the rule the word tier applies to words. Inheriting the
            # word's flag instead marked every phone matched on Track 1 and
            # bnd_f1_all fell to a time-only match while PER read 30 percent.
            from fabench.score import segmentation as _seg

            us.bnd_all = _seg.f1_all(
                _cgw, _chw, _c_wmatched, gold_ivs, hyp_ivs,
                gold_matched=_c_gold_matched,
                gold_unit_matched={gi for gi, _ in matched},
                hyp_unit_matched={hj for _, hj in matched})
        phone = SimpleNamespace(gold_ivs=gold_ivs, hyp_ivs=hyp_ivs, aln=aln,
                                matched=matched, bmatched=bmatched, manner_fn=manner_fn)

    if score_words and gold.words:
        us.word_abs_errors = word.word_abs_errors(gold.words, hyp.words)
        # Word timestamps and the label-checked F1, on the silence-filtered
        # sequences the word-boundary MAE path already uses.
        from fabench.score import segmentation as _wseg

        _gwl = [w for w in gold.words if w.label.lower() not in _SILENCE_WORDS]
        _hwl = [w for w in hyp.words if w.label.lower() not in _SILENCE_WORDS]
        _gll = [w.label.lower() for w in _gwl]
        _hll = [w.label.lower() for w in _hwl]
        _waln = nw_align(_gll, _hll)
        us.n_gold_wts, us.n_hyp_wts = 2 * len(_gwl), 2 * len(_hwl)
        us.wts_start_errors, us.wts_end_errors = word.word_timestamp_errors(
            _gwl, _hwl, _waln.matched(_gll, _hll))
        if _gwl:
            us.wbnd_all = _wseg.f1_all(
                _gwl, _hwl, _waln.matched(_gll, _hll),
                gold_matched=_c_gold_matched)
        from fabench.score.matched import edit_counts

        # Silence pseudo-words are NOT recognition units. Charsiu and MAPS emit
        # "[sil]"/"sil" in the word tier (15 tokens where MFA emits 13), and
        # counting them charged both a ~25% WER made entirely of insertions --
        # for forced aligners, which are handed the reference and cannot
        # misrecognise anything. Drop them on both sides so WER measures words.
        _WSIL = _SILENCE_WORDS

        def _words(seq):
            return [w.label.lower() for w in seq
                    if w.label.lower().strip() not in _WSIL]

        gl = _words(gold.words)
        hl = _words(hyp.words)
        us.n_gold_word = len(gl)
        # WER's numerator, from the SAME label sequences and the same NW
        # alignment the phone tier uses -- one implementation, so the word and
        # phone decompositions cannot disagree about what a substitution is.
        _, us.n_sub_word, us.n_del_word, us.n_ins_word = edit_counts(gl, hl)
        words = SimpleNamespace(gwl=_gwl, hwl=_hwl, waln=_waln, gl=gl, hl=hl)

    if extras:
        ctx = SimpleNamespace(
            **(context or {}), gold=gold, hyp=hyp, boundary_unit=boundary_unit,
            score_phones=score_phones, score_words=score_words,
            cgw=_cgw, chw=_chw, c_wmatched=_c_wmatched, c_gold_matched=_c_gold_matched,
            word_mode=word_mode, phone=phone, words=words)
        for fn in extras:
            fn(us, ctx)
    return us
