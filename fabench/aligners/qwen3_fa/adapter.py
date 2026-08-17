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

"""Qwen3-ForcedAligner-0.6B — word-level forced alignment, via subprocess.

https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B

A genuine forced aligner: it consumes audio **and the reference transcript** and
returns one unit per reference token with `start_time` / `end_time`, so it
belongs in `fabench.aligners` beside MFA and olign — not in `fabench.timestamp_asrs`.
Non-autoregressive, 11 languages, up to 5 minutes of audio.

**Word-level only.** No phone tier, so it is absent from the phone tables by
construction, exactly like WhisperX.

WHY SUBPROCESS AND NOT IN-PROCESS (this is the whole design decision).

whisperx gets away with `sys.path`-appending its private venv, because it
tolerates the shared `.venv`'s transformers. `qwen_asr` does not: it needs
transformers 4.57.6 against the shared env's 5.14.1. Appending failed at import
(`check_model_inputs() missing 1 required positional argument: 'func'`), and
*prepending* failed deeper, on a compiled extension:

    Version mismatch: this is the 'cffi' package version 2.1.1 ...
    when we import the top-level '_cffi_backend' extension module,
    we get version 2.1.0 ...

**No `sys.path` arrangement can fix a native-extension mismatch** — the .so is
loaded once per process. Two environments with differing compiled deps cannot
share an interpreter. So this runs `evals/aligners/qwen3_fa/worker.py` under the
tool's own python, exactly as the MFA and MAPS adapters shell out.

It is a BATCH adapter so the model loads once per cell rather than once per
utterance, which is what makes the subprocess affordable.

MEASURED (8 TIMIT core_test utterances, 69 items, 2026-08-07): items are 1:1
with the reference words, boundaries are monotonic, and **7.2% have zero
duration** (`end_time == start_time`). Zero-duration units are passed through
UNCHANGED — they are the model's actual output, and inventing a duration would
fabricate a boundary it never produced. The rate is printed per batch.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from fabench.aligners.base import (
    AlignerAdapter,
    AlignerError,
    AlignerOutput,
    BatchItem,
    clamp_intervals,
)
from fabench.schema import Interval

_DEFAULT_MODEL = "Qwen/Qwen3-ForcedAligner-0.6B"


class Qwen3FA(AlignerAdapter):
    source = "orthographic"
    emits_confidence = False
    granularity = ("word",)
    #: one model load per cell, not per utterance
    batch = True

    def load(self) -> None:
        if self._loaded:
            return
        venv = self.params.get("venv")
        if not venv:
            raise AlignerError(
                "aligners.qwen3_fa.params.venv is required (the tool runs in its "
                "own interpreter). Build it with "
                "evals/aligners/qwen3_fa/download_and_install.sh."
            )
        self.python = Path(venv) / "bin" / "python"
        self.worker = Path(venv).parent / "worker.py"
        for p, what in ((self.python, "interpreter"), (self.worker, "worker")):
            if not p.exists():
                raise AlignerError(
                    f"missing {what} at {p}. Run "
                    f"evals/aligners/qwen3_fa/download_and_install.sh."
                )
        self.model = self.params.get("model", _DEFAULT_MODEL)
        self.language = self.params.get("language", "English")
        self.timeout_s = int(self.params.get("timeout_s", 7200))
        self._loaded = True

    def align_corpus(self, items: list[BatchItem]) -> dict[str, AlignerOutput]:
        self.load()
        results: dict[str, AlignerOutput] = {}
        total_zero = total_words = 0
        with tempfile.TemporaryDirectory(dir=self.params.get("tmp_dir")) as td:
            jobs = Path(td) / "jobs.jsonl"
            with open(jobs, "w") as f:
                f.writelines(json.dumps({
                        "item_id": it.item_id,
                        "audio_path": it.audio_path,
                        "transcript": it.transcript,
                    }) + "\n" for it in items)

            cmd = [str(self.python), str(self.worker), str(jobs),
                   self.model, self.language]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout_s
                , check=False)
            except subprocess.TimeoutExpired as e:
                raise AlignerError(f"qwen3_fa worker timed out: {e}") from e
            if proc.returncode != 0:
                raise AlignerError(
                    f"qwen3_fa worker failed (rc={proc.returncode}): "
                    f"{proc.stderr[-400:]}"
                )

            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue          # worker warnings on stdout, not a result
                if "error" in rec:
                    continue          # per-item failure; item simply absent
                words, n_zero, dur = [], 0, 0.0
                for text, start, end in rec.get("words", []):
                    if end <= start:
                        n_zero += 1   # kept as-is; see module docstring
                    label = (text or "").strip().strip(".,!?").lower()
                    if label:
                        words.append(Interval(label, float(start), float(end), None))
                    dur = max(dur, float(end))
                # AlignerOutput carries only words/phones -- no meta field --
                # so the zero-duration count is accumulated here and reported
                # once for the batch rather than silently dropped.
                total_zero += n_zero
                total_words += len(words)
                results[rec["item_id"]] = AlignerOutput(
                    words=clamp_intervals(words, dur)
                )
        if total_words:
            print(f"  [qwen3_fa] {total_zero}/{total_words} units zero-duration "
                  f"({100.0 * total_zero / total_words:.1f}%)")
        return results

    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        """Single-item convenience. SLOW — reloads the model; prefer align_corpus.

        Required because `align` is abstract on AlignerAdapter, and a batch
        adapter that omits it fails at construction, not at call time.
        """
        out = self.align_corpus(
            [BatchItem("single", audio_path, transcript, "spk", phone_seq, mode)]
        )
        if "single" not in out:
            raise AlignerError("qwen3_fa produced no result for this item")
        return out["single"]
