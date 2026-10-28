# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Render a canonical Utterance to a Praat TextGrid (Plan S1 plausibility gate)."""

from __future__ import annotations

from pathlib import Path

from fabench.schema import Utterance


def _nonoverlapping(ivs):
    """Clip start to the running previous end so Praat (which forbids overlaps)
    can render TIMIT's co-articulated word boundaries. Display-only — does not
    touch the gold."""
    out, prev_end = [], 0.0
    for iv in sorted(ivs, key=lambda x: x.start):
        s = max(iv.start, prev_end)
        e = max(iv.end, s + 1e-4)
        out.append((s, e, iv.label))
        prev_end = e
    return out


def render_textgrid(utt: Utterance, path: str | Path) -> None:
    from praatio import textgrid

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    max_t = max(
        [utt.duration_s]
        + [p.end for p in utt.phones]
        + [w.end for w in utt.words]
    )
    tg = textgrid.Textgrid()
    for name, ivs in (("phones", utt.phones), ("words", utt.words)):
        if not ivs:
            continue
        entries = _nonoverlapping(ivs)
        # extend tier maxT past the last entry to satisfy praatio bounds
        tier = textgrid.IntervalTier(name, entries, 0.0, max(max_t, entries[-1][1]))
        tg.addTier(tier)
    tg.save(str(path), format="long_textgrid", includeBlankSpaces=True)
