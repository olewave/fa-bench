#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Worker for NVIDIA NeMo Forced Aligner.

    worker.py jobs.jsonl <pretrained_name> <nfa_repo_dir> [device] [batch_size]

NFA has no python API. Its whole interface is align.py, a hydra script that
reads a manifest and writes CTM files, so this worker builds a manifest for the
entire cell, runs align.py ONCE, and reads the CTMs back. One run per cell means
one model load per cell, which is the whole point of the batch protocol.

utt_id is the CTM filename and NFA derives it from the audio filename, so the
audio is symlinked into a scratch directory under a sanitised item_id. Reading
the output manifest instead would work until two items share an audio file,
which Buckeye does.

If the single run fails the worker retries in chunks. align.py aborts the whole
manifest on one bad utterance, and losing 890 alignments to one of them is not
a trade worth making; the chunk retry costs a model load per chunk and only
happens when something already went wrong.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

#: At most this many retry chunks after a whole-manifest failure. A fixed
#: chunk size looked fine on TIMIT and would have meant 140 model loads on
#: Buckeye, so the chunk grows with the cell instead.
MAX_CHUNKS = 8
MIN_CHUNK = 32


def sanitise(item_id: str, seen: set[str]) -> str:
    u = re.sub(r"[^A-Za-z0-9._-]", "_", item_id) or "utt"
    base, n = u, 1
    while u in seen:
        n += 1
        u = f"{base}__{n}"
    seen.add(u)
    return u


def read_ctm(path: Path) -> list[list]:
    """CTM is <source> <chan> <start> <dur> <token> <conf> <type> <speaker>."""
    spans = []
    for line in path.read_text().splitlines():
        f = line.split()
        if len(f) < 5:
            continue
        try:
            start, dur = float(f[2]), float(f[3])
        except ValueError:
            continue
        tok = f[4].replace("<space>", " ").strip()
        if tok:
            spans.append([tok, start, start + dur])
    return spans


def last_error(stderr: str) -> str:
    """The line a reader needs out of a hydra traceback.

    The parent only prints a worker's stderr when the worker itself exits
    non-zero, and this one does not: it reports per item and returns 0. Without
    this the failure reason lived in a stream nobody reads.
    """
    lines = [x.strip() for x in stderr.splitlines() if x.strip()]
    for x in reversed(lines):
        if "Error" in x or "error" in x or "Exception" in x:
            return x[:300]
    return lines[-1][:300] if lines else "no stderr"


def run_align(tools: Path, model: str, manifest: Path, outdir: Path,
              device: str, batch_size: int, hydra_dir: Path):
    cmd = [
        sys.executable, "align.py",
        f"pretrained_name={model}",
        f"manifest_filepath={manifest}",
        f"output_dir={outdir}",
        f"transcribe_device={device}",
        f"viterbi_device={device}",
        f"batch_size={batch_size}",
        "save_output_file_formats=[ctm]",
        "audio_filepath_parts_in_utt_id=1",
        "additional_segment_grouping_separator=null",
        f"hydra.run.dir={hydra_dir}",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tools) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("HYDRA_FULL_ERROR", "1")
    # check=False on purpose. The caller reads returncode and stderr and
    # reports the cell as failed; raising here would abort the sweep.
    return subprocess.run(cmd, cwd=str(tools), env=env, check=False,
                          capture_output=True, text=True)


def main() -> int:
    jobs_path, model, repo = sys.argv[1], sys.argv[2], sys.argv[3]
    device = sys.argv[4] if len(sys.argv) > 4 else "cuda"
    batch_size = int(sys.argv[5]) if len(sys.argv) > 5 else 4

    tools = Path(repo).resolve()
    if not (tools / "align.py").is_file():
        tools = tools / "tools" / "nemo_forced_aligner"
    if not (tools / "align.py").is_file():
        print(json.dumps({"item_id": "*", "error": f"no align.py under {repo}"}))
        return 1

    jobs = [json.loads(ln) for ln in Path(jobs_path).read_text().splitlines() if ln.strip()]

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        audio_dir = td / "audio"
        audio_dir.mkdir()
        seen: set[str] = set()
        entries = []                       # (utt_id, item_id, manifest line)
        for j in jobs:
            text = (j.get("transcript") or "").strip()
            if not text:
                print(json.dumps({"item_id": j["item_id"],
                                  "error": "empty transcript"}))
                continue
            src = Path(j["audio_path"]).resolve()
            utt = sanitise(j["item_id"], seen)
            link = audio_dir / (utt + src.suffix)
            try:
                link.symlink_to(src)
            except OSError as e:
                print(json.dumps({"item_id": j["item_id"], "error": str(e)}))
                continue
            entries.append((utt, j["item_id"],
                            {"audio_filepath": str(link), "text": text}))

        if not entries:
            return 0

        def align_batch(batch, tag):
            man = td / f"manifest_{tag}.json"
            out = td / f"out_{tag}"
            man.write_text("".join(json.dumps(e[2]) + "\n" for e in batch))
            p = run_align(tools, model, man, out, device, batch_size,
                          td / f"hydra_{tag}")
            return p, out / "ctm" / "words"

        proc, words_dir = align_batch(entries, "all")
        done: dict[str, list] = {}
        why = "align.py wrote no CTM for this item"
        if proc.returncode == 0 and words_dir.is_dir():
            for utt, item_id, _ in entries:
                ctm = words_dir / f"{utt}.ctm"
                if ctm.is_file():
                    done[item_id] = read_ctm(ctm)
        else:
            sys.stderr.write(proc.stderr[-3000:] + "\n")
            why = "align.py failed: " + last_error(proc.stderr)
            size = max(MIN_CHUNK, -(-len(entries) // MAX_CHUNKS))
            for i in range(0, len(entries), size):
                chunk = entries[i:i + size]
                p, wd = align_batch(chunk, f"c{i}")
                if p.returncode != 0 or not wd.is_dir():
                    sys.stderr.write(f"chunk {i} failed\n" + p.stderr[-1500:] + "\n")
                    continue
                for utt, item_id, _ in chunk:
                    ctm = wd / f"{utt}.ctm"
                    if ctm.is_file():
                        done[item_id] = read_ctm(ctm)

        for utt, item_id, _ in entries:
            if item_id in done:
                print(json.dumps({"item_id": item_id, "words": done[item_id]}))
            else:
                print(json.dumps({"item_id": item_id, "error": why}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
