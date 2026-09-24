# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""UnitY2 batch worker -- runs in evals/aligners/unity2/venv's interpreter.

argv: jobs.jsonl  model  device

`extract_alignment` returns a duration in 20 ms acoustic-unit frames for every
character SentencePiece token, so boundaries are a cumulative sum and words are
recovered by regrouping on the word-start marker.

add_trailing_silence=True is not optional here. With it the trailing silence
gets its own marker token and the last real word ends where it should; without
it that silence is absorbed into the final token and every utterance's last
word runs to the end of the audio -- 5.50s against a 4.71s gold end on the
utterance this was checked against.
"""
import json
import os
import sys

os.environ.setdefault("HF_HOME", "/ndata/hf")

import torch
from seamless_communication.models.aligner.alignment_extractor import (
    AlignmentExtractor,
)

FRAME_S = 0.020
KMEANS = ("https://dl.fbaipublicfiles.com/seamlessM4T/models/unit_extraction/"
          "kmeans_10k.npy")
MARK = "▁"                      # SentencePiece word-start marker


def _words(tokens, durations):
    """Character tokens plus per-token durations -> word intervals in seconds."""
    out, label, start, t = [], None, 0.0, 0.0
    for tok, d in zip(tokens, durations):
        s = str(tok)
        if s.startswith(MARK):
            if label:                # empty label = the trailing-silence marker
                out.append([label, start, t])
            label, start = s[len(MARK):], t
        elif label is not None:
            label += s
        t += d * FRAME_S
    if label:
        out.append([label, start, t])
    return out


def main() -> int:
    jobs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    model = sys.argv[2]
    device = torch.device(sys.argv[3] if len(sys.argv) > 3 else "cpu")
    ex = AlignmentExtractor(
        aligner_model_name_or_card=model,
        unit_extractor_model_name_or_card="xlsr2_1b_v2",
        unit_extractor_output_layer=35,
        unit_extractor_kmeans_model_uri=KMEANS,
        device=device,
    )
    for j in jobs:
        try:
            text = (j.get("transcript") or "").strip()
            if not text:
                raise ValueError("no transcript")
            durs, _units, toks = ex.extract_alignment(
                j["audio_path"], text, plot=False, add_trailing_silence=True)
            d = durs.tolist()
            if d and isinstance(d[0], list):
                d = d[0]
            print(json.dumps({"item_id": j["item_id"],
                              "words": _words(list(toks), d),
                              "phones": []}), flush=True)
        except Exception as e:
            print(json.dumps({"item_id": j["item_id"],
                              "error": f"{type(e).__name__}: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
