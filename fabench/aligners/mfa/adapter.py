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

"""MFA adapter (McAuliffe 2017) — Montreal Forced Aligner 3.x (HMM-GMM / Kaldi).

MFA is a **batch** aligner: heavy Kaldi startup (~40-60 s) is amortized over a
whole corpus, so per-utterance alignment is impractical. This adapter implements
``align_corpus``: it lays out a speaker-structured corpus directory
(``<speaker>/uNNNNN.wav`` + ``.lab``), runs a single ``mfa align``, and parses
the per-utterance TextGrids back.

MFA is conda-installed; we invoke it through a micromamba env. It emits no
per-boundary probability (log-likelihood -> rank only), so calibration is N/A.
"""

from __future__ import annotations

import os
import shutil
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

# Machine-specific; override via env or params (micromamba/mamba_root).
_DEFAULT_MM = os.environ.get(
    "FABENCH_MICROMAMBA", str(Path.home() / "micromamba" / "bin" / "micromamba"))
_DEFAULT_ROOT = os.environ.get("FABENCH_MAMBA_ROOT", str(Path.home() / "micromamba"))
# Default conda env per MFA version, so `version` can select the aligner build
# without hard-coding an env name. Override with params.env or params.version_envs.
_VERSION_ENVS = {"3.4": "mfa", "3.0": "mfa30"}


class MFA(AlignerAdapter):
    source = "mfa"  # ARPABET
    emits_confidence = False
    granularity = ("word", "phone")
    batch = True

    def load(self) -> None:
        if self._loaded:
            return
        self.mm = self.params.get("micromamba", _DEFAULT_MM)
        self.mm_root = self.params.get("mamba_root", _DEFAULT_ROOT)
        # MFA version -> conda env. `env` wins if set; otherwise the `version`
        # param (default 3.4) maps through version_envs (default 3.4->mfa, 3.0->mfa30).
        self.version = str(self.params.get("version", "3.4"))
        envs = {**_VERSION_ENVS, **self.params.get("version_envs", {})}
        self.env = self.params.get("env") or envs.get(self.version, "mfa")
        self.dictionary = self.params.get("dictionary", "english_us_arpa")
        self.acoustic = self.params.get("acoustic_model", "english_us_arpa")
        self.num_jobs = int(self.params.get("num_jobs", 8))
        # MFA's model store is PER USER (~/Documents/MFA), not per conda env,
        # and `english_us_arpa` is resolved by NAME out of it. Two MFA versions
        # on one machine therefore share one model directory and whichever
        # downloaded last wins: MFA 2.0.6 was seen loading the v3 model that
        # MFA 3.4 had fetched, which does not error -- it yields an empty
        # word-boundary file and zero aligned records. Give each version its
        # own root via params.mfa_root.
        self.mfa_root = self.params.get("mfa_root")
        if not Path(self.mm).exists() and shutil.which("mfa") is None:
            raise AlignerError(
                f"MFA not available: no micromamba at {self.mm} and no `mfa` on "
                "PATH. Install via `micromamba create -n mfa -c conda-forge "
                "montreal-forced-aligner` and `mfa model download acoustic/"
                "dictionary english_us_arpa`."
            )
        self._loaded = True

    def _mfa_cmd(self, *args: str) -> list[str]:
        if Path(self.mm).exists():
            return [self.mm, "run", "-n", self.env, "mfa", *args]
        return ["mfa", *args]

    def align_corpus(self, items: list[BatchItem]) -> dict[str, AlignerOutput]:
        self.load()
        import soundfile as sf

        from fabench.audio import load_resample

        env = dict(os.environ, MAMBA_ROOT_PREFIX=self.mm_root)
        if self.mfa_root:
            env["MFA_ROOT_DIR"] = str(self.mfa_root)
        results: dict[str, AlignerOutput] = {}
        with tempfile.TemporaryDirectory(dir=self.params.get("tmp_dir")) as td:
            td = Path(td)
            corpus = td / "corpus"
            out = td / "out"
            idx2item: dict[str, tuple[str, float]] = {}
            for i, it in enumerate(items):
                name = f"u{i:06d}"
                spk = "".join(c if c.isalnum() else "_" for c in it.speaker) or "spk"
                d = corpus / spk
                d.mkdir(parents=True, exist_ok=True)
                x, sr = load_resample(it.audio_path, 16000)
                sf.write(str(d / f"{name}.wav"), x, sr, subtype="PCM_16")
                (d / f"{name}.lab").write_text(it.transcript or "")
                idx2item[name] = (it.item_id, len(x) / sr)

            # params.align_args injects extra `mfa align` options before the
            # positionals, e.g. ["--uses_speaker_adaptation", "false"] to run
            # speaker-blind (no per-speaker fMLLR) for an apples-to-apples
            # baseline against per-utterance aligners.
            cmd = self._mfa_cmd(
                "align", "--clean", "--quiet", "-j", str(self.num_jobs),
                *[str(a) for a in self.params.get("align_args", [])],
                str(corpus), self.dictionary, self.acoustic, str(out),
            )
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, env=env,
                                   timeout=self.params.get("timeout", 7200), check=False)
            except subprocess.TimeoutExpired as e:
                raise AlignerError(f"mfa align timed out: {e}") from e
            if r.returncode != 0:
                raise AlignerError(f"mfa align failed (rc={r.returncode}): {r.stderr[-500:]}")

            for tg in out.rglob("*.TextGrid"):
                name = tg.stem
                if name not in idx2item:
                    continue
                item_id, dur = idx2item[name]
                results[item_id] = self._parse_tg(tg, dur)
        return results

    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        # Single-item convenience (slow — prefer align_corpus).
        out = self.align_corpus(
            [BatchItem("single", audio_path, transcript, "spk", phone_seq, mode)]
        )
        return out.get("single", AlignerOutput())

    def _parse_tg(self, tg_path: Path, dur: float) -> AlignerOutput:
        from praatio import textgrid

        tg = textgrid.openTextgrid(str(tg_path), includeEmptyIntervals=True)
        names = {n.lower(): n for n in tg.tierNames}

        def read(tier):
            if tier not in names:
                return []
            return [
                Interval(str(e[2]).strip(), float(e[0]), float(e[1]))
                for e in tg.getTier(names[tier]).entries
                if str(e[2]).strip()
            ]

        words = read("words")
        for w in words:
            w.label = w.label.lower()
        return AlignerOutput(
            words=clamp_intervals(words, dur), phones=clamp_intervals(read("phones"), dur)
        )
