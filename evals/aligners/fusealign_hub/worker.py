#!/usr/bin/env python
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Batch forced-alignment worker for the fusealign_hub package.

Runs in evals/aligners/fusealign_hub/venv (download_and_install.sh).

    argv: <jobs.jsonl> <model> <revision> <checkpoint> <device> <batch_size> <unplaced>
    in  : {"item_id": ..., "audio_path": ..., "transcript": ...}
    out : {"item_id": ..., "words": [[text, start, end, presence], ...], "n_unplaced": N}
          {"item_id": ..., "error": "..."}

The checkpoint is the file ``checkpoint`` of Hugging Face repo ``model`` at
``revision``, read from the local cache that download_and_install.sh fills, so
the worker also runs offline (HF_HUB_OFFLINE=1).

One word per ``transcript.split()`` token, in order, with the package defaults
for everything else. ``unplaced=fallback`` keeps the package's uniform fallback
interval for words it does not place; ``unplaced=drop`` omits them.
``n_unplaced`` counts them in both modes.

Jobs go through ``align_batch`` CHUNK at a time, which bounds the audio held in
memory. If a slice's batch call raises, its jobs are retried one by one, so one
bad item costs only its own record.
"""

import json
import sys

CHUNK = 1024


def main() -> int:
    jobs_path, model, revision, checkpoint, device, batch_size, unplaced = sys.argv[1:8]
    if unplaced not in ("fallback", "drop"):
        raise SystemExit(f"unplaced must be 'fallback' or 'drop', got {unplaced!r}")
    out = sys.stdout
    sys.stdout = sys.stderr
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio
    from fusealign_hub import SAMPLE_RATE, load_aligner
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(repo_id=model, filename=checkpoint, revision=revision)
    aligner = load_aligner(path, device=device, batch_size=int(batch_size))
    print(f"# fusealign_hub {model}@{revision[:12]}/{checkpoint} device={aligner.device} "
          f"batch_size={batch_size} unplaced={unplaced}", file=sys.stderr)

    with open(jobs_path) as f:
        jobs = [json.loads(line) for line in f if line.strip()]

    def error(job, e):
        return {"item_id": job["item_id"], "error": f"{type(e).__name__}: {e}"[:300]}

    def record(job, result):
        return {
            "item_id": job["item_id"],
            "words": [[w.word, float(w.start), float(w.end), float(w.presence)]
                      for w in result if unplaced == "fallback" or w.placed],
            "n_unplaced": sum(not w.placed for w in result),
        }

    for lo in range(0, len(jobs), CHUNK):
        records = []
        loaded = []  # (job, wav)
        for job in jobs[lo:lo + CHUNK]:
            try:
                wav, sr = sf.read(job["audio_path"], dtype="float32", always_2d=True)
                wav = torch.from_numpy(np.ascontiguousarray(wav.mean(axis=1)))
                if sr != SAMPLE_RATE:
                    wav = torchaudio.functional.resample(wav, sr, SAMPLE_RATE)
                loaded.append((job, wav))
            except Exception as e:
                records.append(error(job, e))
        if loaded:
            try:
                results = aligner.align_batch([wav for _, wav in loaded], SAMPLE_RATE,
                                              [job["transcript"] for job, _ in loaded])
                records += [record(job, r) for (job, _), r in zip(loaded, results)]
            except Exception as e:
                print(f"# align_batch failed on jobs {lo}..{lo + len(loaded)}, "
                      f"retrying one by one: {type(e).__name__}: {e}", file=sys.stderr)
                for job, wav in loaded:
                    try:
                        records.append(record(job, aligner.align(wav, SAMPLE_RATE,
                                                                 job["transcript"])))
                    except Exception as e1:
                        records.append(error(job, e1))
        out.writelines(json.dumps(r) + "\n" for r in records)
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
