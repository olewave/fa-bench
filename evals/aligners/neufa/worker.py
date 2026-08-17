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

"""NeuFA (Li et al., ICASSP 2022) in its OWN interpreter.

Protocol (fabench/aligners/subprocess_aligner.py):

    in : {"item_id":…, "audio_path":…, "transcript":…}
    out: {"item_id":…, "words":[[t,s,e],…], "phones":[[t,s,e],…]}

Mode A only: NeuFA is text-driven, running its own sequitur G2P.

WHY A WORKER. The adapter used to `sys.path.insert` the NeuFA checkout into
FA-Bench's own process and import its `inference` module -- it even had to
verify that import had not been shadowed by something else on the path -- while
taking torch from the shared .venv. A research repo's modules do not belong on
the benchmark's path, and it was the last reason that venv carried a CUDA build.

NeuFA is loaded ONCE for the batch.
"""
from __future__ import annotations

import json
import sys
import tempfile
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR = 16000


def load_resample(path: str, target_sr: int = SR):
    """Mono float64 at target_sr -- same polyphase ratio as fabench.audio."""
    x, sr = sf.read(path, always_2d=False)
    x = np.asarray(x)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr == target_sr:
        return x, sr
    g = gcd(int(sr), int(target_sr))
    return resample_poly(x, target_sr // g, sr // g).astype(np.float64), target_sr


def align_one(neufa, id2symbol, transcript: str, x, sr: float) -> dict:
    """One utterance -> {"words": [...], "phones": [...]}.

    Factored out of main() so the guards below -- an empty G2P result, and a
    boundary count that disagrees with the phoneme count -- stay unit-testable
    against a stub, which is what they were before this tool moved into a
    worker. They are the two failures a wrong checkpoint produces, and both are
    silent if unchecked.
    """
    import numpy as _np

    dur = len(x) / sr
    words = neufa.get_words(transcript)
    phonemes = neufa.get_phonemes(words)
    n_phones = sum(len(p) for p in phonemes)
    if not n_phones:
        raise RuntimeError(f"no alignable words in {transcript!r}")

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "u.wav"
        sf.write(str(wav), _np.clip(x, -1.0, 1.0), sr, subtype="PCM_16")
        boundaries, _w_tts, _w_asr = neufa.align(transcript, str(wav))

    if len(boundaries) != n_phones:
        raise RuntimeError(
            f"{len(boundaries)} boundary rows for {n_phones} phonemes "
            "-- checkpoint/repo mismatch?")

    out_words, out_phones, start = [], [], 0
    for word, pids in zip(words, phonemes):
        if not pids:                # G2P produced nothing -> no boundary
            continue
        seg = boundaries[start:start + len(pids)]
        start += len(pids)
        wl, wr = float(seg[0][0]), float(seg[-1][1])
        if wr > wl:
            out_words.append([word, min(wl, dur), min(wr, dur)])
        for pid, row in zip(pids, seg):
            left, right = float(row[0]), float(row[1])
            if right <= left:       # degenerate span; NeuFA allows them
                continue
            out_phones.append([str(id2symbol[pid - 1]),
                               min(left, dur), min(right, dur)])
    return {"words": out_words, "phones": out_phones}


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    repo = Path(argv[2])
    model_path = Path(argv[3])
    device = argv[4] if len(argv) > 4 else "cuda"

    import torch

    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    sys.path.insert(0, str(repo))
    import importlib

    mod = importlib.import_module("inference")
    if not str(getattr(mod, "__file__", "")).startswith(str(repo)):
        raise SystemExit(f"`import inference` resolved outside {repo} -- shadowed")
    neufa = mod.NeuFA(model_path=str(model_path), device=device)
    id2symbol = neufa.g2p.id2symbol

    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                x, sr = load_resample(job["audio_path"])
                rec.update(align_one(neufa, id2symbol, job.get("transcript", ""), x, sr))
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
