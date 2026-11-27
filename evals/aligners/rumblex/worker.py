#!/usr/bin/env python3
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""rumblex forced alignment in its OWN interpreter.

Protocol (fabench/aligners/subprocess_aligner.py):

    in : {"item_id":…, "audio_path":…, "transcript":…}
    out: {"item_id":…, "words":[[text, start, end, conf], …]}

`rumblex.align` runs the encoder of the ASR checkpoint and force-aligns the
given transcript to the checkpoint's CTC head. Nothing is decoded, so the words
that come back are the words that went in, one for one, split at spaces.

The audio is read here with soundfile and handed over as an array. Given a
path, rumblex decodes it with ffmpeg, which the benchmark box would then need
on PATH for this one tool.

The model is loaded ONCE for the batch; per-utterance subprocessing would pay
that load every time.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import soundfile as sf


def load_audio(path: str) -> tuple[np.ndarray, int]:
    """Mono float32 at the file's own rate. rumblex resamples to 16 kHz itself."""
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return np.ascontiguousarray(x, dtype=np.float32), int(sr)


def main(argv: list[str]) -> int:
    jobs_path, model_id = argv[0], argv[1]
    device = argv[2] if len(argv) > 2 else "cuda"

    import rumblex
    import torch

    # startswith, as in the other workers: the cell runners pass "cuda:0".
    device = device if (device.startswith("cuda")
                        and torch.cuda.is_available()) else "cpu"
    model = rumblex.load_model(model_id, device=device)

    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                x, sr = load_audio(job["audio_path"])
                result = rumblex.align(x, job.get("transcript", ""), model, sr=sr)
                rec["words"] = [[w.word, w.start, w.end, w.score]
                                for seg in result.segments for w in seg.words]
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
