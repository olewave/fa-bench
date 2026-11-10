#!/usr/bin/env python
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""nyra forced aligner batch worker. Runs in evals/aligners/nyra_fa/venv.

argv: jobs.jsonl  model  device

The model card asks for fillers as bracketed upper-case tags, so "um" and
"uh" are sent as [UM] and [UH]. The aligner returns one entry per token it
was given. When the counts agree the times go back under the reference
labels, which is what the label-checked scorer pairs on. When they differ,
a token was skipped or split, and the aligner's own labels are returned.
"""
import json
import sys

from nyra_align import Aligner

FILLERS = {"um": "[UM]", "uh": "[UH]"}


def main() -> int:
    with open(sys.argv[1]) as f:
        jobs = [json.loads(l) for l in f if l.strip()]
    aligner = Aligner(sys.argv[2], device=sys.argv[3] if len(sys.argv) > 3 else None)
    out = sys.stdout
    for j in jobs:
        try:
            ref = j["transcript"].split()
            res = aligner.align(j["audio_path"], " ".join(FILLERS.get(w.lower(), w) for w in ref))
            same = len(res.words) == len(ref)
            words = []
            for i, w in enumerate(res.words):
                label = ref[i] if same else str(w.word).strip("[]").lower()
                span = [label, float(w.start), float(w.end)]
                if w.confidence is not None:
                    span.append(float(w.confidence))
                words.append(span)
            out.write(json.dumps({"item_id": j["item_id"], "words": words, "phones": []}) + "\n")
        except Exception as e:  # one bad utterance must not end the batch
            out.write(json.dumps({"item_id": j["item_id"], "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
