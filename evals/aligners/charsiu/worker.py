#!/usr/bin/env python
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Charsiu batch worker — runs in evals/aligners/charsiu/repo/env's interpreter.

Separate process because Charsiu's deps (torch/transformers + its custom model
classes) must not be resolved from FA-Bench's shared .venv: installing another
tool there has already silently changed Charsiu's transformers and torch once.

argv: jobs.jsonl  model  repo_path
"""
import json
import sys

sys.path.insert(0, sys.argv[3])          # Charsiu's src/, for its model classes

import numpy as np
import soundfile as sf
from Charsiu import charsiu_forced_aligner


def main() -> int:
    with open(sys.argv[1]) as _jf:
        jobs = [json.loads(l) for l in _jf if l.strip()]
    aligner = charsiu_forced_aligner(aligner=sys.argv[2])
    out = sys.stdout
    for j in jobs:
        try:
            x, _sr = sf.read(j["audio_path"], dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            phones, words = aligner.align(np.asarray(x, dtype=np.float32),
                                          j["transcript"])
            out.write(json.dumps({
                "item_id": j["item_id"],
                "phones": [[str(p[2]), float(p[0]), float(p[1])] for p in phones],
                "words": [[str(w[2]), float(w[0]), float(w[1])] for w in words],
            }) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"], "error": str(e)[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
