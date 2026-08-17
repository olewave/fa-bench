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

"""Shared base for aligners that run in their OWN interpreter.

WHY EVERY TOOL GETS ITS OWN VENV.

These packages conflict. Concretely, in this repo:

* installing whisperx into the shared `.venv` moved **transformers 5.14.1 ->
  4.57.6 and torch 2.13 -> 2.8** for Charsiu and BFA, which import from that
  same env. Their published numbers were then set by a different tool's
  dependency resolution.
* `qwen_asr` needs transformers 4.57.6 against the shared 5.14.1, and grafting
  its site-packages onto `sys.path` failed on a **native extension** —
  `cffi` 2.1.1 (python) against `_cffi_backend` 2.1.0 (`.so`). No `sys.path`
  ordering fixes that: the `.so` is loaded once per process.

So `sys.path` grafting is not isolation, it is a shared env with extra steps.
The only thing that actually isolates two dependency sets is **two
interpreters**. That is what this base provides.

Contract for a subclass:

* set `worker_name` (default `worker.py`, resolved next to the tool's venv) and
  `default_model`;
* ship `evals/<kind>/<tool>/worker.py`, which loads the model ONCE and speaks
  JSONL over stdout;
* set `params.venv` in `evals/<kind>/<tool>/config.yaml`.

Batch by construction — a subprocess per utterance would pay model load every
time, which is what makes the isolation affordable.

Protocol (one JSON object per line):

    in : {"item_id":..., "audio_path":..., "transcript":...}
    out: {"item_id":..., "words":[[t,s,e],...], "phones":[[t,s,e],...]}
         {"item_id":..., "error":"..."}

A span may carry a 4th element, its confidence: [text, start, end, conf].
Omit it and confidence is None, which is what every metric that needs one
(calibration: Spearman, AUROC@20 ms, ECE) treats as "not reported".
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


class SubprocessAligner(AlignerAdapter):
    """Runs its tool in a separate interpreter, one batch per cell."""

    batch = True
    default_model = ""
    worker_name = "worker.py"
    #: timestamped ASRs set this True and their job records omit the transcript
    ignores_transcript = False

    def load(self) -> None:
        if self._loaded:
            return
        venv = self.params.get("venv")
        if not venv:
            raise AlignerError(
                f"{self.name}: params.venv is required — each tool runs in its "
                f"own interpreter. Build it with the tool's "
                f"download_and_install.sh."
            )
        self.python = Path(venv) / "bin" / "python"
        # Find the worker by SEARCHING UP from the venv, not at a fixed depth.
        # Venvs sit at different depths per tool -- `<tool>/venv` for qwen3_fa
        # and crisperwhisper, `<tool>/repo/env` for charsiu and bfa -- so
        # `Path(venv).parent` silently looked in `repo/` and every cell failed.
        # `params.worker` overrides outright.
        explicit = self.params.get("worker")
        if explicit:
            self.worker = Path(explicit)
        else:
            self.worker = None
            d = Path(venv).resolve().parent
            for _ in range(4):
                cand = d / self.worker_name
                if cand.exists():
                    self.worker = cand
                    break
                d = d.parent
            if self.worker is None:
                raise AlignerError(
                    f"{self.name}: no {self.worker_name} found above {venv}. "
                    f"Add one, or set params.worker."
                )
        for p, what in ((self.python, "interpreter"), (self.worker, "worker")):
            if not p.exists():
                raise AlignerError(f"{self.name}: missing {what} at {p}")
        self.model = self.params.get("model", self.default_model)
        # `timeout_s: null` (or 0) means NO timeout, and for these workers that
        # is usually what you want. The worker is BATCH and the parent reads
        # stdout only after the process exits, so a timeout does not truncate a
        # run -- it destroys it. crisperwhisper and crisperwhisper_fa each spent
        # 4 h on buckeye_dev, hit the 14400 s limit, and wrote 0 records; the
        # work was done and thrown away. A wall-clock guess cannot distinguish
        # "wedged" from "slow but progressing", and at 5.9 s/item Buckeye's 4456
        # utterances legitimately need ~7.3 h.
        t = self.params.get("timeout_s", 14400)
        self.timeout_s = int(t) if t else None
        self._loaded = True

    def _job(self, it: BatchItem) -> dict:
        j = {"item_id": it.item_id, "audio_path": it.audio_path}
        if not self.ignores_transcript:
            j["transcript"] = it.transcript
        return j

    def _extra_argv(self) -> list[str]:
        """Extra worker arguments; subclasses override (e.g. repo_path)."""
        return []

    def align_corpus(self, items: list[BatchItem]) -> dict[str, AlignerOutput]:
        self.load()
        results: dict[str, AlignerOutput] = {}
        n_err = 0
        with tempfile.TemporaryDirectory(dir=self.params.get("tmp_dir")) as td:
            jobs = Path(td) / "jobs.jsonl"
            with open(jobs, "w") as f:
                f.writelines(json.dumps(self._job(it)) + "\n" for it in items)

            cmd = [str(self.python), str(self.worker), str(jobs), self.model]
            cmd += self._extra_argv()
            # `params.env` lets a tool set/unset environment for its subprocess.
            # NeMo (parakeet) needs LD_LIBRARY_PATH UNSET -- it is run as
            # `env -u LD_LIBRARY_PATH ...` -- and an HF_HOME it can write
            # to. A value of null unsets the variable.
            import os as _os

            env = dict(_os.environ)
            # Cap the BLAS/OpenMP pools before the worker starts.
            #
            # torch sizes them to the CORE COUNT unless told otherwise, so each
            # worker opened ~120 threads and burned ~5 cores on a 48-core box
            # even with the model on the GPU -- the CPU goes on feature
            # extraction and resampling, which device= does not affect. Six
            # concurrent workers took ~30 cores and pushed the machine into
            # swap while the GPUs sat at 16-41% utilisation.
            #
            # FABENCH_THREADS already existed as the knob and nothing read it.
            # setdefault, so an explicit OMP_NUM_THREADS in the environment or
            # in params.env still wins.
            _threads = env.get("FABENCH_THREADS", "2")
            for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                         "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                         "VECLIB_MAXIMUM_THREADS"):
                env.setdefault(_var, _threads)
            for k, v in (self.params.get("env") or {}).items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[str(k)] = str(v)
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout_s,
                    env=env,
                check=False)
            except subprocess.TimeoutExpired as e:
                raise AlignerError(f"{self.name} worker timed out: {e}") from e
            if proc.returncode != 0:
                raise AlignerError(
                    f"{self.name} worker failed (rc={proc.returncode}): "
                    f"{proc.stderr[-400:]}"
                )

            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue          # library chatter on stdout, not a result
                if "error" in rec:
                    n_err += 1
                    continue
                dur = 0.0
                tiers: dict[str, list[Interval]] = {}
                for tier in ("words", "phones"):
                    ivs = []
                    for span in rec.get(tier) or []:
                        # [text, start, end] or [text, start, end, conf]. The
                        # 3-form dropped confidence for EVERY subprocess tool:
                        # whisperx declares emits_confidence: true and its
                        # cal_spearman/auroc/ece came out empty, because the
                        # parser hardcoded None. Optional 4th element, so
                        # existing workers are unaffected.
                        text, start, end = span[0], span[1], span[2]
                        conf = float(span[3]) if len(span) > 3 and span[3] is not None else None
                        label = (text or "").strip()
                        if tier == "words":
                            label = label.strip(".,!?").lower()
                        if label:
                            ivs.append(Interval(label, float(start), float(end), conf))
                        dur = max(dur, float(end))
                    tiers[tier] = ivs
                # Anything the worker reported beyond the tiers is diagnostic
                # and must survive into hyp.jsonl -- see AlignerOutput.meta.
                meta = {k: v for k, v in rec.items()
                        if k not in ("item_id", "words", "phones", "error")}
                results[rec["item_id"]] = AlignerOutput(
                    words=clamp_intervals(tiers["words"], dur),
                    phones=clamp_intervals(tiers["phones"], dur),
                    meta=meta,
                )
        if n_err:
            print(f"  [{self.name}] {n_err}/{len(items)} items failed in worker")
        return results

    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        """Single-item convenience. SLOW — reloads the model; prefer align_corpus.

        Present because `align` is abstract on AlignerAdapter and a batch
        adapter omitting it fails at construction rather than at call time.
        """
        out = self.align_corpus(
            [BatchItem("single", audio_path, transcript, "spk", phone_seq, mode)]
        )
        if "single" not in out:
            raise AlignerError(f"{self.name} produced no result for this item")
        return out["single"]
