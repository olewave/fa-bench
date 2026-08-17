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

"""Per-utterance boundary-error extraction (library-general).

Given a gold and a hypothesis :class:`~fabench.schema.Utterance`, produce the
per-boundary error lists the analytics consume, each tagged interior vs
silence/edge. Scoring uses the headline fabench protocol (manner-match) so the
matched set is identical to the leaderboard's.

The interior/edge tag is derived two ways by tier, deliberately: phones use the
manner engine (a ``silence`` neighbour, which also fires at utterance edges);
words have no manner, so silence-adjacency is read from gold timing (utterance
edge, or a >1 ms gap to the neighbour).
"""
from __future__ import annotations

from collections.abc import Callable

from fabench.normalize import make_canon, manner_of
from fabench.schema import Interval, Utterance
from fabench.score.core import _SILENCE_WORDS, score_pair
from fabench.score.matched import nw_align

_WORD_GAP_S = 0.001


def hyp_utt_from_record(rec: dict) -> Utterance:
    """Build a minimal hyp Utterance from a FA-Bench hyp JSONL record."""
    return Utterance(
        rec["utt_id"], "hyp", "", "", "", 16000, 0.0,
        words=[Interval.from_dict(w) for w in rec.get("words", [])],
        phones=[Interval.from_dict(p) for p in rec.get("phones", [])],
    )


def phone_boundary_errors(
    gold: Utterance, hyp: Utterance, gold_canon: Callable[[str], str],
) -> list[tuple[float, float, bool]]:
    """(abs_ms, signed_ms, silence_adjacent) per matched phone boundary."""
    us = score_pair(
        gold, hyp, condition="c", aligner="x", mode="A",
        gold_canon=gold_canon, hyp_canon=make_canon("arpabet"),
        manner_of_canonical=manner_of, manner_match=True,
    )
    out = []
    for b in us.boundary_errors:
        sil = b.left_manner == "silence" or b.right_manner == "silence"
        out.append((b.abs * 1000, b.signed * 1000, sil))
    return out


def word_boundary_errors(gold: Utterance, hyp: Utterance) -> list[tuple[float, bool]]:
    """(abs_ms, silence_adjacent) per matched word boundary (onset + offset)."""
    gw = [w for w in gold.words if w.label.lower() not in _SILENCE_WORDS]
    hw = [w for w in hyp.words if w.label.lower() not in _SILENCE_WORDS]
    if not gw or not hw:
        return []
    gl = [w.label.lower() for w in gw]
    hl = [w.label.lower() for w in hw]
    ng = len(gw)
    out: list[tuple[float, bool]] = []
    for gi, hj in nw_align(gl, hl).matched(gl, hl):
        on_sil = gi == 0 or (gw[gi].start - gw[gi - 1].end > _WORD_GAP_S)
        off_sil = gi == ng - 1 or (gw[gi + 1].start - gw[gi].end > _WORD_GAP_S)
        out.append((abs(hw[hj].start - gw[gi].start) * 1000, on_sil))
        out.append((abs(hw[hj].end - gw[gi].end) * 1000, off_sil))
    return out
