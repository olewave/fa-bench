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
"""Map an aligner's output words back onto the tokens it was GIVEN.

THE PROBLEM. An aligner is handed a word sequence and asked for its timings.
Most of them first normalise that sequence to whatever their lexicon accepts --
MFA looks each word up in its dictionary, so ``tom-boy`` becomes ``tom`` ``boy``
and ``kids'`` becomes ``kids`` while in-vocabulary ``who's`` survives untouched;
BFA has no apostrophe at all, so every ``don't`` comes back as ``don`` ``t``.
They then return the NORMALISED tokens instead of converting back.

Nothing downstream can tell the difference between that and a real error. The
word tier compares surface tokens, so each rewritten word costs a substitution
plus an insertion, and each split adds a boundary the reference does not have --
inflating the hypothesis word count and dragging word MAE, P/R, F1, OS and
R-val. On a GOLD transcript this is pure noise: a forced aligner cannot
misrecognise a word it was given, so its word error rate should be exactly zero,
and BFA was scoring 12.13 % against MFA's 0.47 % on the same reference.

THE FIX belongs here, at the boundary where the input is still known, not in the
scorer -- the scorer only sees two token lists and cannot know which differences
the aligner was responsible for. Relabelling here also fixes every variant at
once (apostrophe, hyphen, possessive, and a reference token that itself contains
a space) rather than one rule per orthographic quirk.

CONSERVATIVE BY CONSTRUCTION. A hypothesis token is only ever relabelled or
merged when it demonstrably reconstructs the input token: the comparison is on
the letters alone, with punctuation and case removed. Anything that does not
reconstruct is left exactly as the aligner produced it, so genuine infidelity --
Charsiu duplicating a word, an aligner dropping one -- stays visible in the
numbers. This makes a faithful aligner score zero, not every aligner.
"""
from __future__ import annotations

#: Word-tier tokens belonging to an aligner's own topology rather than the
#: transcript. Kept in step with ``_WSIL`` in :mod:`fabench.score.core`.
SILENCE = {"sil", "[sil]", "<sil>", "sp", "spn", "<eps>", "!sil",
           "silence", "", "<unk>"}

#: Stripped before comparing. Case and punctuation are the aligner's to choose;
#: the LETTERS are what say whether it returned the word it was given.
_DROP = "'’`-.,!?;:\"()[]{} \t"


def _key(text: str) -> str:
    return "".join(c for c in text.lower() if c not in _DROP)


def _is_silence(label: str) -> bool:
    return label.lower().strip() in SILENCE


def relabel_to_input(input_tokens, hyp_words, max_span: int = 5):
    """Return ``hyp_words`` with each output word restored to its input token.

    ``input_tokens`` is the word sequence the aligner was actually given -- the
    reference words on track 1, the ASR's decoded words on track 2. Using the
    real input is what keeps track 2 honest: relabelling a cascade against the
    REFERENCE would erase the recognition errors the track exists to measure.

    A run of consecutive hypothesis words is merged when their letters together
    rebuild one input token; the merged interval runs from the first word's
    start to the last word's end, so the timing stays the aligner's own and only
    the tokenisation is repaired. A single word whose letters already match is
    relabelled to the input's spelling. Everything else is passed through.
    """
    if not input_tokens or not hyp_words:
        return hyp_words

    out, ii, hi = [], 0, 0
    n_in, n_hyp = len(input_tokens), len(hyp_words)
    while hi < n_hyp:
        if _is_silence(hyp_words[hi].label):
            out.append(hyp_words[hi])
            hi += 1
            continue
        while ii < n_in and _is_silence(str(input_tokens[ii])):
            ii += 1
        if ii >= n_in:
            out.extend(hyp_words[hi:])
            break

        want = str(input_tokens[ii])
        wkey = _key(want)
        if _key(hyp_words[hi].label) == wkey:
            w = hyp_words[hi]
            # Relabel even on a 1:1 match: "kids" must read back as "kids'".
            out.append(type(w)(want, w.start, w.end, getattr(w, "conf", None))
                       if w.label != want else w)
            hi += 1
            ii += 1
            continue

        merged = None
        run = [hyp_words[hi]]
        # How many hypothesis tokens could this input token have become? A
        # reference token may itself contain spaces (Buckeye annotates "take
        # care" and "so well yknow what I mean" as single words), and each of
        # those words can split again on an apostrophe -- so the ceiling scales
        # with the token, it is not a constant. Widening costs nothing but a
        # few string compares: a run is only ever merged on an EXACT letter
        # match, so a longer window cannot merge something it should not.
        span = max(max_span, 2 * len(want.split()) + 3)
        for k in range(1, span):
            if hi + k >= n_hyp or _is_silence(hyp_words[hi + k].label):
                break
            run.append(hyp_words[hi + k])
            if _key("".join(x.label for x in run)) == wkey:
                merged = list(run)
                break
        if merged:
            first, last = merged[0], merged[-1]
            out.append(type(first)(want, first.start, last.end,
                                   getattr(first, "conf", None)))
            hi += len(merged)
            ii += 1
        else:
            out.append(hyp_words[hi])      # a real difference: leave it alone
            hi += 1
            ii += 1
    return out
