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


"""WhisperX END TO END, in its own interpreter: Whisper decodes, wav2vec2 aligns.

    in : {"item_id":..., "audio_path":...}
    out: {"item_id":..., "words": [[label, start_s, end_s], ...]}

This is the system as its users actually run it, and it is NOT the `whisperx`
row in track 1. That row is handed the reference transcript and exercises only
the wav2vec2 alignment stage, which isolates the component the benchmark
measures but is not a configuration anyone deploys. Here no transcript is
supplied: Whisper produces the words, and the aligner then places them, so the
row carries recognition error like every other track-2 system.

It is worth scoring precisely because Whisper large-v3 is already in track 2 on
its own attention-derived times. WhisperX exists to replace exactly those times
with a forced alignment, so the two rows over the same audio measure what that
replacement is worth.
"""
from __future__ import annotations

import json
import sys

SR = 16000


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    asr_name = argv[1] if len(argv) > 1 else "large-v3"
    device = argv[2] if len(argv) > 2 else "cuda"

    import torch
    import whisperx

    # `device.startswith` and NOT `device == "cuda"`. The cell runners pin a
    # card by passing "cuda:0" with CUDA_VISIBLE_DEVICES set, and an exact
    # match against "cuda" sent every one of those runs to the CPU without a
    # word. Same alignments, an order of magnitude slower: the MMS Buckeye
    # cells took 90 minutes on 32 cores while three Blackwells sat at 0%.
    device = device if (device.startswith("cuda")
                        and torch.cuda.is_available()) else "cpu"
    # float16 is unavailable on CPU in faster-whisper; int8 is its documented
    # fallback and keeps a CPU run possible rather than crashing on a box whose
    # driver is down.
    # Precision follows the device, so a GPU run is float16 and a CPU run is
    # int8. Worth knowing before re-running this tool: the published rows were
    # produced by the CPU path, back when a "cuda:0" argument fell through to
    # it, so a fresh GPU run will not reproduce them to the last digit.
    compute = "float16" if device.startswith("cuda") else "int8"
    asr = whisperx.load_model(asr_name, device, compute_type=compute, language="en")
    align_model, meta = whisperx.load_align_model(language_code="en", device=device)

    out = sys.stdout
    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                x = whisperx.load_audio(job["audio_path"])
                dur = len(x) / SR
                # STEP 1 -- recognise. No transcript is passed in: that is the
                # whole difference from the track-1 whisperx row.
                asr_out = asr.transcribe(x, batch_size=8)
                segments = asr_out.get("segments") or []
                if not segments:
                    rec["words"] = []
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    continue
                # STEP 2 -- align what step 1 decoded.
                aligned = whisperx.align(segments, align_model, meta, x, device,
                                         return_char_alignments=False)
                words = []
                for seg in aligned.get("segments", []):
                    for w in seg.get("words", []):
                        lab = str(w.get("word", "")).strip()
                        s, e = w.get("start"), w.get("end")
                        if not lab or s is None or e is None:
                            # wav2vec2 returns no span for a token it could not
                            # place (often a digit or a symbol Whisper emitted).
                            # Dropping it loses the word; keeping it with no time
                            # would invent one. It is dropped and shows up as a
                            # deletion, which is the honest accounting.
                            continue
                        words.append([lab, max(0.0, float(s)), min(float(e), dur)])
                rec["words"] = words
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
            out.write(json.dumps(rec) + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
