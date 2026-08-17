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

"""BFA (Bournemouth Forced Aligner) in its OWN interpreter.

Protocol (fabench/aligners/subprocess_aligner.py):

    in : {"item_id":…, "audio_path":…, "transcript":…}
    out: {"item_id":…, "words":[[t,s,e,conf],…], "phones":[[t,s,e,conf],…]}

Mode A only: BFA is text-driven, phonemizing the transcript with espeak itself,
so there is no phone_seq to supply. Phone labels are eSpeak IPA -- the adapter
declares `source = "ipa"` so the scorer canonicalizes them through the right
table.

The model is loaded ONCE for the batch.
"""
from __future__ import annotations

import json
import sys
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def load_resample(path: str, target_sr: int):
    """Mono float64 at target_sr -- same polyphase ratio as fabench.audio."""
    x, sr = sf.read(path, always_2d=False)
    x = np.asarray(x)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr == target_sr:
        return x, sr
    g = gcd(int(sr), int(target_sr))
    return resample_poly(x, target_sr // g, sr // g).astype(np.float64), target_sr


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    preset = argv[2] if len(argv) > 2 and argv[2] != "-" else "en-us"
    device = argv[3] if len(argv) > 3 else "cuda"

    import torch
    from bournemouth_aligner import PhonemeTimestampAligner

    device = "cuda" if (device == "cuda" and torch.cuda.is_available()) else "cpu"
    al = PhonemeTimestampAligner(preset=preset, device=device)
    sr = al.sample_rate

    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                x, got_sr = load_resample(job["audio_path"], sr)
                wav = torch.tensor(x, dtype=torch.float32).unsqueeze(0)  # [1, N]
                out = al.process_sentence(job.get("transcript", ""), wav)
                dur = len(x) / got_sr
                phones, words = [], []
                for seg in out.get("segments", []):
                    for p in seg.get("phoneme_ts", []):
                        lab = p.get("ipa_label", p.get("phoneme_label", ""))
                        s = min(max(p["start_ms"] / 1000.0, 0.0), dur)
                        e = min(max(p["end_ms"] / 1000.0, s), dur)
                        phones.append([lab, s, e, p.get("confidence")])
                    for w in seg.get("words_ts", []):
                        s = min(max(w["start_ms"] / 1000.0, 0.0), dur)
                        e = min(max(w["end_ms"] / 1000.0, s), dur)
                        words.append([str(w["word"]), s, e, w.get("confidence")])
                rec["words"], rec["phones"] = words, phones
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
