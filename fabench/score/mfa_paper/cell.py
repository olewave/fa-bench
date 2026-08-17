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

"""Orchestrates one (corpus, aligner) cell of the ``mfa_paper`` scoring protocol:
load the vendored ``custom_mapping`` YAML, batch-call the kalpy bridge, apply the
ported ``data_prep.R`` manner-category filter, and wrap survivors into UttScore.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from fabench.normalize import make_canon
from fabench.schema import Interval, Utterance
from fabench.score.boundary import BoundaryError
from fabench.score.core import UttScore, _prep_phones
from fabench.score.matched import matched_indices
from fabench.score.mfa_paper.bridge import batch_align_phones
from fabench.score.mfa_paper.filter import filter_boundaries
from fabench.score.mfa_paper.manner_categories import UTTERANCE_EDGE, categorize_ref
from fabench.score.mfa_paper.mapping import load_mapping, mapping_path

# kalpy rounds reference_boundary/boundary_error to 3 decimals (ms precision) on
# the way back from the subprocess bridge — up to 0.5ms of rounding slop, so
# 0.6ms comfortably bounds it without risking a match against an adjacent phone.
_BOUNDARY_MATCH_TOL_S = 6e-4

# FA-Bench's own gold ingest preserves each corpus's native silence token as-is
# (fabench/ingest/timit.py, fabench/ingest/buckeye.py) rather than normalizing it
# to "sil" the way the paper's own gold TextGrids already were. Confirmed
# empirically against real staged data: TIMIT's raw .phn silence marker is "h#";
# Buckeye's is "SIL". Folded into silence_phones in score_cell() below.
_NATIVE_GOLD_SILENCE: dict[str, set[str]] = {
    "timit": {"h#"}, "buckeye": {"SIL", "!sil"},
}


def _nearest_gold_idx(gold_ivs: list[Interval], t: float) -> int:
    """Index of the gold phone whose ``.start`` is closest to ``t`` (a kalpy
    ``reference_boundary``), within tolerance; ``-1`` if none is close enough.
    Used only for :class:`BoundaryError.gold_phone_idx` bookkeeping — v1 ships
    with ``matched_gold_phone_idx=[]`` (see ``score_cell``), so this does not
    yet feed the cross-protocol common-matched guard."""
    best_i, best_d = -1, None
    for i, iv in enumerate(gold_ivs):
        d = abs(iv.start - t)
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    if best_d is not None and best_d <= _BOUNDARY_MATCH_TOL_S:
        return best_i
    return -1


# Paper footnote (Sec. 4.2 of arXiv:2606.18466 / MFA's EvaluateAlignmentsFunction
# docstring): "For BFA, which inserts both onset and offset boundaries for each
# phone, we use only the onset boundary, as the inter-phone gaps in its alignments
# are generally an artifact of the CTC alignment algorithm rather than meaningful
# phone boundaries." Verified on staged data: BFA's raw phone intervals have a
# real timing gap between ~78% of consecutive phones, plus an explicit "-"
# placeholder token on ~3.4% of phones marking some of those gaps. kalpy's
# align_phones only ever reports boundary_error from each interval's .begin (never
# .end) — but the underlying compiled DP's own overlap cost uses BOTH begin and
# end (per MFA's docs), so BFA's meaningless end-time noise can still corrupt
# *which* alignment the DP settles on even though it never appears in the metric
# directly. Fix: drop the "-" placeholder and stretch each remaining phone's end
# to the next phone's start, so the DP only ever sees BFA's (reliable) onsets.
_GAP_MARKER_LABELS = frozenset({"-"})


def make_onset_only(ivs: list[Interval]) -> list[Interval]:
    """Drop gap-marker placeholder intervals and collapse each remaining
    interval's end to the next one's start, so only onsets carry information."""
    real = [iv for iv in ivs if iv.label not in _GAP_MARKER_LABELS]
    out = []
    for i, iv in enumerate(real):
        end = real[i + 1].start if i + 1 < len(real) else iv.end
        out.append(Interval(iv.label, iv.start, end, iv.conf))
    return out


def extract_boundary_errors(
    alignment_path: list[dict],
    *,
    include_utterance_edges: bool = False,
    include_gap_adjacent: bool = False,
) -> list[dict]:
    """Re-expresses kalpy's own ``align_phones`` boundary-extraction loop
    (verified against its source in ``kalpy/evaluation.py``) with its two
    hardcoded exclusions exposed as independent toggles, instead of always on:

    - kalpy never scores a boundary when the *immediately preceding* alignment
      step was an insertion or deletion (``include_gap_adjacent`` recovers
      these — the largest-error boundary in our verified toy example was
      exactly one of these).
    - kalpy never scores the very first boundary of an utterance at all,
      structurally (its loop only appends when ``i != 0``) — regardless of
      whether that first step is itself a gap. For TIMIT/MFA this empirically
      tends to coincide with the first step *being* a deletion (gold's leading
      recording-silence phone has no aligner counterpart), so the two
      exclusions often overlap on real data — but they are independent
      conditions in the code, so both are exposed separately here rather than
      collapsed into one flag (``include_utterance_edges`` recovers the
      ``i == 0`` case specifically).

    With both flags ``False``, this must reproduce kalpy's own ``boundary_errors``
    exactly — that equivalence (checked in ``test_mfa_paper_bridge.py``) is the
    point: this is a faithful re-expression of kalpy's logic on top of the fuller
    ``alignment_path``, not an approximation of it.
    """
    out = []
    for i, step in enumerate(alignment_path):
        sa_label, sb_label = step["ref_label"], step["test_label"]
        if sa_label == "-" or sb_label == "-":
            continue  # an insertion/deletion step itself never yields a boundary

        if i == 0:
            if not include_utterance_edges:
                continue
            prev_ref_label, prev_test_label = UTTERANCE_EDGE, UTTERANCE_EDGE
        else:
            prev = alignment_path[i - 1]
            prev_is_gap = prev["ref_label"] == "-" or prev["test_label"] == "-"
            if prev_is_gap and not include_gap_adjacent:
                continue
            prev_ref_label, prev_test_label = prev["ref_label"], prev["test_label"]

        out.append(
            {
                "following_reference_phone": sa_label,
                "following_test_phone": sb_label,
                "previous_reference_phone": prev_ref_label,
                "previous_test_phone": prev_test_label,
                "boundary_error": round(step["ref_begin"] - step["test_begin"], 3),
                "reference_boundary": round(step["ref_begin"], 3),
                "test_boundary": round(step["test_begin"], 3),
            }
        )
    return out


def to_boundary_error(raw: dict, corpus: str, gold_ivs: list[Interval]) -> BoundaryError:
    """Convert one raw kalpy ``boundary_errors`` dict into a FA-Bench
    :class:`~fabench.score.boundary.BoundaryError`.

    Pulled out of :func:`score_cell`'s loop so the two fiddly, easy-to-get-wrong
    bits — the gold/hyp sign flip and the manner-category lookup — are testable
    without a live kalpy bridge.
    """
    # kalpy's boundary_error = reference.begin - test.begin (gold - hyp);
    # fabench's BoundaryError.signed is hyp - gold ("positive => aligner
    # lags") — do not pass kalpy's value straight through.
    gold_time = raw["reference_boundary"]
    hyp_time = raw["reference_boundary"] - raw["boundary_error"]
    return BoundaryError(
        edge="boundary",  # kalpy's single-edge convention, not onset/offset
        gold_time=gold_time,
        hyp_time=hyp_time,
        left_manner=categorize_ref(raw["previous_reference_phone"], corpus),
        right_manner=categorize_ref(raw["following_reference_phone"], corpus),
        conf=None,
        gold_phone_idx=_nearest_gold_idx(gold_ivs, gold_time),
    )


def score_cell(
    cfg,
    corpus: str,
    aligner: str,
    gold_by_id: dict[str, Utterance],
    hyp_recs: list[dict],
    *,
    bridge_fn: Callable = batch_align_phones,
) -> list[UttScore] | None:
    """Score one (corpus, aligner) cell via the ``mfa_paper`` protocol.

    Returns ``None`` (caller logs + skips, mirroring the existing
    ``"  SKIP {corpus}: ..."`` convention in ``score_all``) if this aligner has no
    configured mapping-file family (``scoring.mfa_paper.aligner_key``), or the
    vendored mapping file for (family, corpus) doesn't exist — e.g. torchaudio_fa
    and whisperx, which have no equivalent in the paper's benchmark repo.
    """
    mp = dict(cfg.scoring.get("mfa_paper", {}))
    family = mp.get("aligner_key", {}).get(aligner)
    if not family:
        return None
    path = mapping_path(family, corpus, mp.get("mapping_dir"))
    if not path.exists():
        return None

    custom_mapping = load_mapping(path)
    # MFA's own EvaluateAlignmentsFunction derives silence_phones from the
    # dictionary's PhoneType.silence-typed phones (verified directly in
    # montreal_forced_aligner/alignment/multiprocessing.py) — for the
    # english_us_arpa model FA-Bench's MFA adapter uses, that's just {"sil"}.
    # But that's the paper's *own* gold TextGrids' already-normalized silence
    # label — FA-Bench's own gold ingest emits each corpus's native token
    # instead (confirmed empirically: TIMIT's raw .phn silence marker is "h#",
    # Buckeye's is "SIL"), and kalpy compares labels by exact string match. Add
    # the native token so kalpy's own silence handling (the 10x mismatch cost
    # in compare_labels, and the ignored_phones score/PER bookkeeping) actually
    # recognizes it — without this, every gold silence boundary looks like an
    # ordinary unmapped phone to kalpy itself, not just to the category filter.
    silence_phones = set(mp.get("silence_phones", ["sil"])) | _NATIVE_GOLD_SILENCE.get(corpus, set())
    apply_filter = bool(mp.get("apply_manner_filter", True))
    onset_only_aligners = set(mp.get("onset_only_aligners", ["bfa"]))
    # Ablation-only, both default False (= kalpy's own native behavior, unchanged
    # from earlier). See extract_boundary_errors() above for exactly what each
    # recovers and why they're independent, not just two names for one thing.
    include_utterance_edges = bool(mp.get("include_utterance_edge_boundaries", False))
    include_gap_adjacent = bool(mp.get("include_gap_adjacent_boundaries", False))
    reconstruct = include_utterance_edges or include_gap_adjacent

    gold_canon = make_canon(corpus)

    batch_items = []   # (utt_id, gold_ivs, hyp_ivs) for the bridge
    meta: dict[str, tuple[Utterance, list[Interval], dict]] = {}
    for rec in hyp_recs:
        gold = gold_by_id.get(rec["utt_id"])
        if gold is None or not gold.phones or not rec.get("phones"):
            continue
        hyp_ivs = [Interval.from_dict(p) for p in rec["phones"]]
        if aligner in onset_only_aligners:
            hyp_ivs = make_onset_only(hyp_ivs)
        batch_items.append((rec["utt_id"], gold.phones, hyp_ivs))
        meta[rec["utt_id"]] = (gold, hyp_ivs, rec)

    if not batch_items:
        return []

    bridged = bridge_fn(
        batch_items, silence_phones=silence_phones, custom_mapping=custom_mapping
    )

    scores: list[UttScore] = []
    n_errors = 0
    for utt_id, (gold, hyp_ivs, rec) in meta.items():
        result = bridged.get(utt_id)
        if result is None or "error" in result:
            n_errors += 1
            continue

        if reconstruct:
            raw_boundaries = extract_boundary_errors(
                result["alignment_path"],
                include_utterance_edges=include_utterance_edges,
                include_gap_adjacent=include_gap_adjacent,
            )
        else:
            raw_boundaries = result["boundary_errors"]
        if apply_filter:
            raw_boundaries = filter_boundaries(
                raw_boundaries, aligner_key=family, corpus=corpus
            )

        boundary_errors = [
            to_boundary_error(b, corpus, gold.phones) for b in raw_boundaries
        ]

        hyp_canon = make_canon(rec.get("source", "arpabet"))
        gold_ivs2, gcanon = _prep_phones(gold.phones, gold_canon)
        hyp_ivs2, hcanon = _prep_phones(hyp_ivs, hyp_canon)
        matched = matched_indices(gcanon, hcanon)

        scores.append(
            UttScore(
                utt_id=utt_id,
                speaker_id=gold.speaker_id,
                corpus=gold.source_corpus,
                register=gold.register,
                condition=rec["condition"],
                aligner=rec["aligner"],
                mode=rec["mode"],
                protocol="mfa_paper",
                boundary_errors=boundary_errors,
                n_matched_phone=len(matched),
                n_gold_phone=len(gold_ivs2),
                n_hyp_phone=len(hyp_ivs2),
                # v1 scope: opt out of the cross-protocol common-matched guard
                # (fabench/score/aggregate.py::_common_matched_sets already
                # skips any UttScore with an empty matched_gold_phone_idx).
                matched_gold_phone_idx=[],
                rtf=rec.get("rtf"),
            )
        )

    if n_errors:
        print(
            f"  mfa_paper: {n_errors}/{len(batch_items)} utterances failed in "
            f"{aligner}x{corpus} (kalpy bridge errors)",
            file=sys.stderr,
        )

    return scores
