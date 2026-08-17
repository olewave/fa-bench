#!/usr/bin/env python3
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

"""WhisperX forced alignment in its OWN interpreter.

Protocol (fabench/aligners/subprocess_aligner.py):

    in : {"item_id":…, "audio_path":…, "transcript":…}
    out: {"item_id":…, "words":[[text, start, end, conf], …]}

WHY A WORKER AT ALL. WhisperX already had a private venv, but the adapter
appended it to `sys.path` and imported whisperx IN-PROCESS -- deliberately, so
that torch and transformers kept resolving to FA-Bench's shared environment.
Its own comment called that out: "That only holds while the two agree on
torch -- pin them together." So the venv isolated the package and not its
dependencies, which is the arrangement subprocess_aligner.py exists to replace:
`sys.path` grafting is a shared env with extra steps, and it cannot survive a
native-extension mismatch (`_cffi_backend` is loaded once per process).

The alignment model is loaded ONCE for the batch; per-utterance subprocessing
would pay that load every time.
"""
from __future__ import annotations

import json
import sys
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR = 16000


def load_audio(path: str) -> np.ndarray:
    """Mono float32 at 16 kHz, resampled the same way fabench.audio does.

    float32, not float64: whisperx feeds the array straight into a float32
    wav2vec2 and torch refuses to promote, failing EVERY utterance with
    "expected scalar type Double but found Float" while the run still exits 0
    with an empty hypothesis file.
    """
    x, sr = sf.read(path, always_2d=False)
    x = np.asarray(x)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        g = gcd(int(sr), SR)
        x = resample_poly(x, SR // g, sr // g)
    return np.asarray(x, dtype=np.float32)


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    device = argv[2] if len(argv) > 2 else "cuda"

    import torch
    import whisperx

    device = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
    model, meta = whisperx.load_align_model(language_code="en", device=device)

    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                x = load_audio(job["audio_path"])
                dur = len(x) / SR
                segments = [{"start": 0.0, "end": dur, "text": job.get("transcript", "")}]
                result = whisperx.align(segments, model, meta, x, device,
                                        return_char_alignments=False)
                # Clamp to the AUDIO duration here, not downstream. The base
                # parser clamps to the largest span end it sees, which is a
                # different bound: whisperx can place a word end past the end of
                # the file, and the in-process adapter clamped that to len(x)/sr.
                # Left to the parser it shifted WBE by ~0.007 ms -- small, but a
                # real difference from the published rows, not GPU noise
                # (whisperx is deterministic: two identical runs match exactly).
                words = []
                for seg in result.get("segments", []):
                    for w in seg.get("words", []):
                        if "start" in w and "end" in w:
                            s = min(max(float(w["start"]), 0.0), dur)
                            e = min(max(float(w["end"]), s), dur)
                            words.append([w["word"], s, e, w.get("score")])
                rec["words"] = words
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
