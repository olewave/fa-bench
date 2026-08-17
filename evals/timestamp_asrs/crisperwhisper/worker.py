#!/usr/bin/env python
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

"""CrisperWhisper batch worker — BOTH modes, in its own interpreter.

Uses the official `crisperwhisper` package (PyPI), NOT a raw transformers
pipeline. The raw route fails on every utterance with
"The size of tensor a (2) must match the size of tensor b (0)" regardless of
transformers version -- it is the wrong entry point, not a version problem.

Two modes, because this model does both:

  transcribe    audio only -> its own words + times     (timestamp_asrs, track 2)
  forced_align  audio + reference text -> word times    (aligners, track 1)

`forced_align` is a native API of the package, so track-1 CrisperWhisper needs
no teacher-forcing implementation -- which supersedes
fabench/aligners/crisperwhisper_fa/README.md.

Install notes learned the hard way:
  * `crisperwhisper[transformers]` does NOT pull ctranslate2, but the
    hallucination module imports it unconditionally -> install it explicitly.
  * the constructor is CrisperWhisperModel(name, device=...), NOT from_pretrained.

argv: jobs.jsonl  model  mode          mode in {transcribe, forced_align}
"""
import json
import sys


def main() -> int:
    from crisperwhisper import CrisperWhisperModel

    with open(sys.argv[1]) as _jf:

        jobs = [json.loads(l) for l in _jf if l.strip()]
    name = sys.argv[2] if len(sys.argv) > 2 else "nyrahealth/CrisperWhisper"
    mode = sys.argv[3] if len(sys.argv) > 3 else "transcribe"
    model = CrisperWhisperModel(name, device="auto")

    import soundfile as sf

    out = sys.stdout
    n_dropped = n_items_hit = 0
    for j in jobs:
        try:
            if mode == "forced_align":
                r = model.forced_align(j["audio_path"], j["transcript"], language="en")
            else:
                r = model.transcribe(j["audio_path"], language="en")
            units = getattr(r, "words", None) or []

            # DURATION GUARD. Whisper pads every input to a fixed 30 s window,
            # and when the decoder loses a token it attaches it to the trailing
            # silence rather than failing. Measured on timit core_test: 11/192
            # utterances (5.7%) had words ending past the audio, e.g.
            #   SI1993.WAV is 2.48 s; gold "him" is 1.41-1.56 s
            #   CrisperWhisper returned "him" at 29.32-29.62 s
            # The first three words of that utterance were within 20 ms of gold.
            #
            # Those few items dominated the mean: median 30.3 ms vs mean 223.9,
            # so the published figure measured a decode-failure rate, not
            # alignment quality. A boundary outside the audio is not a bad
            # alignment, it is a failure, and must not reach the scorer as a
            # valid time. Dropping the word makes it a DELETION, which the
            # scorer already accounts for in Del%.
            try:
                dur = sf.info(j["audio_path"]).duration
            except Exception:
                dur = None
            tol = 0.05                       # allow a little past the last sample
            words, dropped = [], 0
            for w in units:
                text = getattr(w, "word", None) or getattr(w, "text", "")
                st, en = float(w.start), float(w.end)
                if dur is not None and (st > dur + tol or en > dur + tol or st < -tol):
                    dropped += 1
                    continue
                words.append([text, st, en])
            if dropped:
                n_dropped += dropped
                n_items_hit += 1
                print(f"# {j['item_id']}: dropped {dropped} word(s) outside "
                      f"0..{dur:.2f}s (whisper 30s-window artefact)",
                      file=sys.stderr)
            out.write(json.dumps({"item_id": j["item_id"], "words": words,
                                  "dropped_out_of_range": dropped}) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
        out.flush()
    if n_items_hit:
        print(f"# duration guard: {n_dropped} word(s) dropped across "
              f"{n_items_hit}/{len(jobs)} items", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
