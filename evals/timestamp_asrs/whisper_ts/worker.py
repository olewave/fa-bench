# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""whisper-timestamped batch worker.

argv: jobs.jsonl  model  device

TRACK 2, ONE STEP. transcribe_timestamped decodes its own words and times them
by cross-attention DTW in the same pass. There is no entry point that takes a
supplied transcript, so this cannot be a Track 1 aligner and there is no
cascade built on it.
"""
import json
import os
import sys

os.environ.setdefault("HF_HOME", "/ndata/hf")

import torch
import whisper_timestamped as wts


def main() -> int:
    jobs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    model_name = sys.argv[2]
    device = sys.argv[3] if len(sys.argv) > 3 else "cuda"
    device = device if (device.startswith("cuda") and torch.cuda.is_available()) else "cpu"
    model = wts.load_model(model_name, device=device)
    for j in jobs:
        try:
            r = wts.transcribe_timestamped(
                model, j["audio_path"], language="en",
                verbose=None, plot_word_alignment=False)
            words = []
            for seg in r.get("segments") or []:
                for w in seg.get("words") or []:
                    lab = (w.get("text") or "").strip().strip(".,!?").lower()
                    if lab:
                        words.append([lab, float(w["start"]), float(w["end"]),
                                      float(w.get("confidence") or 0.0)])
            print(json.dumps({"item_id": j["item_id"], "words": words,
                              "phones": []}), flush=True)
        except Exception as e:
            print(json.dumps({"item_id": j["item_id"],
                              "error": f"{type(e).__name__}: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
