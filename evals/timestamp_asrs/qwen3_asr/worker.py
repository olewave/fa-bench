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


"""Qwen3-ASR in its OWN interpreter.

Protocol, per fabench/timestamp_asrs/subprocess_asr.py:
    in : {"item_id":..., "audio_path":...}      -- no transcript: this is an ASR
    out: {"item_id":..., "words": [[label, start_s, end_s], ...]}

`return_time_stamps=True` makes the package load Qwen3-ForcedAligner-0.6B and
align the text it just decoded, so two models sit on the GPU at once.

The exact shape of `result.time_stamps` is not pinned by the model card, so
_words() accepts the plausible encodings rather than betting on one, and the
first record that matches none is reported with its repr instead of being
silently dropped. Times are converted to seconds only if they are obviously
milliseconds -- see _to_seconds.
"""
from __future__ import annotations

import json
import sys


def _to_seconds(vals: list[float], dur_hint: float | None) -> float:
    """Qwen does not document the unit. If the last end time is far past any
    plausible utterance length, the stamps are milliseconds."""
    if not vals:
        return 1.0
    hi = max(vals)
    if dur_hint and hi > dur_hint * 5:
        return 1000.0
    return 1000.0 if hi > 3600 else 1.0


def _words(ts, dur_hint=None):
    """Normalise whatever `time_stamps` is into [[label, start, end], ...]."""
    flat = []
    def walk(node):
        # What the package actually returns:
        #   ForcedAlignResult(items=[ForcedAlignItem(text=, start_time=, end_time=)])
        # i.e. plain objects, not dicts or tuples -- attributes first.
        lab = getattr(node, "text", None)
        st = getattr(node, "start_time", None)
        en = getattr(node, "end_time", None)
        if lab is not None and st is not None and en is not None:
            flat.append([str(lab), float(st), float(en)]); return
        kids = getattr(node, "items", None)
        if isinstance(kids, (list, tuple)):          # not dict.items, that is a method
            for v in kids:
                walk(v)
            return
        if isinstance(node, dict):
            lab = node.get("word", node.get("text", node.get("token", node.get("char"))))
            st, en = node.get("start", node.get("begin")), node.get("end")
            if lab is not None and st is not None and en is not None:
                flat.append([str(lab), float(st), float(en)]); return
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            # a bare (label, start, end) triple
            if (len(node) == 3 and isinstance(node[0], str)
                    and all(isinstance(x, (int, float)) for x in node[1:])):
                flat.append([node[0], float(node[1]), float(node[2])]); return
            for v in node:
                walk(v)
    walk(ts)
    scale = _to_seconds([w[2] for w in flat], dur_hint)
    return [[w[0], w[1] / scale, w[2] / scale] for w in flat]


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    name = argv[1] if len(argv) > 1 else "Qwen/Qwen3-ASR-1.7B"
    with open(jobs_path) as f:
        jobs = [json.loads(l) for l in f if l.strip()]

    import torch
    from qwen_asr import Qwen3ASRModel

    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    model = Qwen3ASRModel.from_pretrained(
        name,
        dtype=torch.bfloat16 if dev.startswith("cuda") else torch.float32,
        device_map=dev,
        max_inference_batch_size=16,
        max_new_tokens=256,
        forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
        forced_aligner_kwargs={
            "dtype": torch.bfloat16 if dev.startswith("cuda") else torch.float32,
            "device_map": dev,
        },
    )

    out = sys.stdout
    B = 16                       # chunked so one bad file cannot lose the cell
    for i in range(0, len(jobs), B):
        batch = jobs[i:i + B]
        try:
            res = model.transcribe(
                audio=[j["audio_path"] for j in batch],
                language=["English"] * len(batch),
                return_time_stamps=True,
            )
        except Exception as e:
            for j in batch:
                out.write(json.dumps({"item_id": j["item_id"],
                                      "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
            out.flush(); continue
        for j, r in zip(batch, res):
            try:
                ws = _words(getattr(r, "time_stamps", None), j.get("duration_s"))
                rec = {"item_id": j["item_id"], "words": ws}
                if not ws:
                    rec["error"] = ("no timestamps parsed from "
                                    + repr(getattr(r, "time_stamps", None))[:200])
                out.write(json.dumps(rec) + "\n")
            except Exception as e:
                out.write(json.dumps({"item_id": j["item_id"],
                                      "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
