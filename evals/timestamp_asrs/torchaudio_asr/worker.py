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


"""wav2vec2 CTC greedy decoding in its OWN interpreter.

    in : {"item_id":..., "audio_path":...}
    out: {"item_id":..., "words": [[label, start_s, end_s], ...]}

The bundle emits per-frame character logits. Greedy decoding takes the argmax
per frame, collapses runs, and drops blanks; the surviving frame indices give
each character a span, and characters between '|' separators form a word. The
word's span therefore runs from its first character's first frame to its last
character's last frame -- an exact CTC span rather than an estimate.
"""
from __future__ import annotations

import json
import sys
from math import gcd

import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy.signal import resample_poly


def load_resample(path: str, target_sr: int):
    x, sr = sf.read(path, always_2d=False)
    x = np.asarray(x)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr == target_sr:
        return x
    g = gcd(int(sr), int(target_sr))
    return resample_poly(x, target_sr // g, sr // g).astype(np.float64)


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    bundle_name = argv[1] if len(argv) > 1 else "WAV2VEC2_ASR_BASE_960H"
    with open(jobs_path) as f:
        jobs = [json.loads(line) for line in f if line.strip()]

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    bundle = getattr(torchaudio.pipelines, bundle_name)
    model = bundle.get_model().to(dev).eval()
    labels = bundle.get_labels()
    sr = bundle.sample_rate
    blank, sep = 0, labels.index("|") if "|" in labels else 4

    out = sys.stdout
    for j in jobs:
        try:
            x = load_resample(j["audio_path"], sr)
            wav = torch.tensor(x, dtype=torch.float32, device=dev).unsqueeze(0)
            with torch.inference_mode():
                emission, _ = model(wav)
            ids = emission[0].argmax(dim=-1).tolist()
            ratio = wav.size(1) / emission.size(1) / sr        # frames -> seconds

            # collapse runs, keep the frame each surviving symbol started on
            chars, prev = [], -1
            for t, k in enumerate(ids):
                if k != prev and k != blank:
                    chars.append([k, t, t])
                elif k == prev and chars:
                    chars[-1][2] = t
                prev = k

            words, cur = [], []
            def flush():
                if cur:
                    lab = "".join(labels[c[0]] for c in cur).lower()
                    if lab:
                        words.append([lab, cur[0][1] * ratio, (cur[-1][2] + 1) * ratio])
                cur.clear()
            for c in chars:
                if c[0] == sep:
                    flush()
                else:
                    cur.append(c)
            flush()
            out.write(json.dumps({"item_id": j["item_id"], "words": words}) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"],
                                  "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
