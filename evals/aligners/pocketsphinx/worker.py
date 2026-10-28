#!/usr/bin/env python
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""PocketSphinx batch worker -- runs in evals/aligners/pocketsphinx/venv's interpreter.

Aligns the way `pocketsphinx align` does (programs/pocketsphinx_main.c): no
language model, bestpath off, the transcript as a straight chain of words,
one decode for the words and a second pass over the same samples for the
phones. The model's own feat.params apply, so this is the shipped setup.

Pronunciations come from the model's CMUdict, where a plain word may take any
of its listed variants. A word CMUdict lacks is given one by g2p_en, stress
removed, before the first utterance. A token g2p_en cannot pronounce either is
left out of the alignment text and scores as a deletion, as in MAPS.

An utterance whose word pass falls off the default beams before the last word
("Final result does not match the grammar") is aligned again with the beams
open, after the beam and retry beam MFA also uses. The record says so in
`retry_beam`.

argv: jobs.jsonl  model
"""
import json
import re
import sys

import soundfile as sf
from pocketsphinx import Decoder

_VARIANT = re.compile(r"\(\d+\)$")
#: beam, wbeam, pbeam for the second attempt, wide enough to leave a
#: one-sentence chain unpruned. 1e-80 rescued 1 of 10 TIMIT core-test failures
#: under additive noise and this rescued all 10. Where the default beams
#: succeed, this setting gave the same alignment on 173 of 176 TIMIT
#: utterances across clean, noise and babble, and moved the other 3 by at
#: most one frame, so the default beams only buy speed.
RETRY_BEAMS = {"beam": 1e-200, "wbeam": 1e-200, "pbeam": 1e-200}


def _speech(name: str) -> bool:
    """False for <s>, </s>, <sil>, [NOISE], SIL and +NSN+ style fillers."""
    return bool(name) and name[0] not in "<[+" and name != "SIL"


def _add_oov(dec: Decoder, jobs: list[dict]) -> tuple[set[str], set[str]]:
    """Give each word CMUdict lacks a g2p_en pronunciation, before any search
    exists, so update=False is enough. Returns (added, unpronounceable)."""
    oov = sorted({w for j in jobs for w in j["transcript"].lower().split()
                  if dec.lookup_word(w) is None})
    if not oov:
        return set(), set()
    from g2p_en import G2p
    g2p, added, mute = G2p(), set(), set()
    for w in oov:
        phones = [re.sub(r"\d", "", p) for p in g2p(w) if p and p[0].isalpha()]
        if not phones:              # Buckeye's `?`. An empty entry segfaults
            mute.add(w)             # the decoder later instead of raising.
            continue
        try:
            dec.add_word(w, " ".join(phones), update=False)
            added.add(w)
        except (RuntimeError, ValueError):
            mute.add(w)
    return added, mute


def _align(dec: Decoder, raw: bytes, text: list[str], frate: int):
    """Both passes of `pocketsphinx align` over one utterance."""
    dec.set_align_text(" ".join(text))
    for second in (False, True):            # words, then phones
        if second:
            dec.set_alignment()
        dec.start_utt()
        dec.process_raw(raw, full_utt=True)
        dec.end_utt()
    words, phones = [], []
    for w in dec.get_alignment():
        if not _speech(w.name):
            continue
        words.append([_VARIANT.sub("", w.name), w.start / frate,
                      (w.start + w.duration) / frate])
        phones += [[p.name, p.start / frate, (p.start + p.duration) / frate]
                   for p in w if _speech(p.name)]
    return words, phones


def main() -> int:
    with open(sys.argv[1]) as _jf:
        jobs = [json.loads(line) for line in _jf if line.strip()]
    if sys.argv[2] != "en-us":
        raise SystemExit(f"only the bundled en-us model is wired up, not {sys.argv[2]!r}")
    dec = Decoder(bestpath=False, lm=None, loglevel="FATAL")
    frate, samprate = int(dec.config["frate"]), int(dec.config["samprate"])
    added, mute = _add_oov(dec, jobs)
    wide = None                             # built on the first failure only
    out = sys.stdout
    for j in jobs:
        try:
            pcm, sr = sf.read(j["audio_path"], dtype="int16")
            if sr != samprate or pcm.ndim != 1:
                raise ValueError(f"{sr} Hz, {pcm.ndim}-d audio; the model takes {samprate} Hz mono")
            text = [w for w in j["transcript"].lower().split() if w not in mute]
            if not text:
                raise ValueError("no pronounceable word in the transcript")
            try:
                words, phones = _align(dec, pcm.tobytes(), text, frate)
                retry = False
            except RuntimeError:
                if wide is None:
                    wide = Decoder(bestpath=False, lm=None, loglevel="FATAL",
                                   **RETRY_BEAMS)
                    _add_oov(wide, jobs)
                words, phones = _align(wide, pcm.tobytes(), text, frate)
                retry = True
            rec = {"item_id": j["item_id"], "words": words, "phones": phones}
            if retry:
                rec["retry_beam"] = True
            # Diagnostics that land in hyp.jsonl, so a reader can see which
            # utterances leaned on the G2P or lost a token.
            if n := sum(w in added for w in text):
                rec["n_g2p_words"] = n
            if n := len(j["transcript"].split()) - len(text):
                rec["n_unpronounceable"] = n
            out.write(json.dumps(rec) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
