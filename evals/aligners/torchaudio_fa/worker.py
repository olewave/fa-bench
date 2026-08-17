#!/usr/bin/env python3
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

"""torchaudio forced alignment in its OWN interpreter.

Reads one JSON job per line and writes one JSON result per line, per the
protocol in fabench/aligners/subprocess_aligner.py:

    in : {"item_id":…, "audio_path":…, "transcript":…, "mode":"A"|"B",
          "phone_seq":[…]}
    out: {"item_id":…, "words":[[t,s,e,conf],…], "phones":[[t,s,e,conf],…]}

TWO MODELS, LOADED ONCE.
  Mode A (words)  — a torchaudio wav2vec2 bundle, CTC forced alignment over
                    CHARACTER tokens, spans merged back into words.
  Mode B (phones) — a HuggingFace CTC phoneme model, forced alignment over the
                    phone sequence eSpeak G2P derives FROM THE TRANSCRIPT.
                    The reference `phone_seq` is deliberately unused: see
                    Aligner.phones.
Loading both up front is what makes the private venv affordable: a subprocess
per utterance would pay two model loads every time.

WHY THIS FILE DUPLICATES NOTHING IMPORTANT. It reads audio with soundfile and
resamples with scipy's resample_poly at the same up/down ratio as
fabench.audio.resample, so a file already at the bundle's rate takes the same
no-op path. The runner only ever hands over `mixed_audio_path`, which the mix
manifest has already materialised as a 16 kHz WAV -- SPHERE is decoded once,
upstream, by fabench.audio. This worker therefore never needs a SPHERE reader,
and FA-Bench is not installed into this venv.
"""
from __future__ import annotations

import json
import sys
from math import gcd

import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy.signal import resample_poly


def load_resample(path: str, target_sr: int) -> tuple[np.ndarray, int]:
    """Mono float64 at `target_sr`. Same polyphase ratio as fabench.audio."""
    x, sr = sf.read(path, always_2d=False)
    x = np.asarray(x)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr == target_sr:
        return x, sr
    g = gcd(int(sr), int(target_sr))
    return resample_poly(x, target_sr // g, sr // g).astype(np.float64), target_sr


class Aligner:
    def __init__(self, bundle_name: str, phoneme_model: str | None, device: str):
        self.device = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        self.F = torchaudio.functional

        self.bundle = getattr(torchaudio.pipelines, bundle_name)
        self.model = self.bundle.get_model().to(self.device).eval()
        self.sr = self.bundle.sample_rate
        labels = self.bundle.get_labels()
        self.tok = {c: i for i, c in enumerate(labels)}
        self.blank = 0

        self.phoneme = None
        if phoneme_model:
            from transformers import AutoModelForCTC, AutoProcessor

            self.ph_proc = AutoProcessor.from_pretrained(phoneme_model)
            self.ph_model = AutoModelForCTC.from_pretrained(phoneme_model).to(self.device).eval()
            vocab = self.ph_proc.tokenizer.get_vocab()
            self.ph_tok = dict(vocab)
            self.phoneme = phoneme_model

            # One backend for the whole cell: constructing it per utterance
            # dominates the alignment cost.
            from phonemizer.backend import EspeakBackend
            from phonemizer.separator import Separator

            self._espeak = EspeakBackend(
                "en-us", with_stress=False, language_switch="remove-flags")
            self._sep = Separator(phone=" ", word=" | ", syllable="")

    # ---- mode A: words ------------------------------------------------
    def words(self, audio_path: str, transcript: str):
        import re

        x, _ = load_resample(audio_path, self.sr)
        wav = torch.tensor(x, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.inference_mode():
            emission, _ = self.model(wav)
            logp = torch.log_softmax(emission, dim=-1)
        n_samples, n_frames = wav.size(1), logp.size(1)
        ratio = n_samples / n_frames / self.sr

        wlist = re.findall(r"[A-Za-z']+", transcript.upper())
        if not wlist:
            return []
        tokens, per_word = [], []
        for w in wlist:
            chars = [c for c in w if c in self.tok]
            per_word.append(len(chars))
            tokens.extend(self.tok[c] for c in chars)
        if not tokens:
            return []
        tgt = torch.tensor([tokens], dtype=torch.int32, device=self.device)
        aligned, scores = self.F.forced_align(logp, tgt, blank=self.blank)
        spans = self.F.merge_tokens(aligned[0], scores[0].exp())

        out, si = [], 0
        for w, cnt in zip(wlist, per_word):
            if cnt == 0:
                continue
            ws = spans[si:si + cnt]
            si += cnt
            if not ws:
                continue
            conf = float(sum(s.score for s in ws) / len(ws))
            out.append([w.lower(), ws[0].start * ratio, ws[-1].end * ratio, conf])
        return out

    # ---- mode B: phones -----------------------------------------------
    def phones(self, audio_path: str, transcript: str):
        """Align the phone sequence THIS SYSTEM derives from the transcript.

        The sequence comes from eSpeak G2P, never from the reference. A forced
        aligner is given words and must work out the phones itself; handing it
        the gold labels removes the substitution and insertion decisions
        entirely, so S and I come out at exactly 0.0 and the tier measures
        boundary placement on a problem no other system was set.
        """
        if self.phoneme is None:
            raise RuntimeError("no phoneme_model configured")
        keep = self.g2p(transcript)
        if not keep:
            raise RuntimeError("g2p produced no phones for this transcript")

        target_sr = self.ph_proc.feature_extractor.sampling_rate
        x, _ = load_resample(audio_path, target_sr)
        n_samples = len(x)
        inputs = self.ph_proc(x, sampling_rate=target_sr, return_tensors="pt")
        with torch.inference_mode():
            logits = self.ph_model(inputs.input_values.to(self.device)).logits
            logp = torch.log_softmax(logits, dim=-1)
        ratio = n_samples / logp.size(1) / target_sr

        # CTC cannot align more targets than frames.
        if len(keep) > logp.size(1):
            raise RuntimeError(f"{len(keep)} targets exceed {logp.size(1)} frames")
        targets = [self.ph_tok[p] for p in keep]
        blank = self.ph_model.config.pad_token_id or 0
        tgt = torch.tensor([targets], dtype=torch.int32, device=self.device)
        aligned, scores = self.F.forced_align(logp, tgt, blank=blank)
        spans = self.F.merge_tokens(aligned[0], scores[0].exp())
        return [[p, s.start * ratio, s.end * ratio, float(s.score)]
                for s, p in zip(spans, keep)]

    def g2p(self, transcript: str) -> list[str]:
        """Transcript -> eSpeak IPA tokens that exist in the model vocabulary.

        `with_stress=False` matters: the stressed forms eSpeak would otherwise
        emit (ˈiː, ˈaɪ, ...) are absent from the 392-symbol vocabulary, and
        keeping them drops roughly a quarter of the sequence. Unstressed output
        was measured at 100% vocabulary coverage, so the filter below is a
        guard, not a routine path.
        """
        out = self._espeak.phonemize([transcript], separator=self._sep, strip=True)
        toks = [t for t in out[0].split() if t != "|"]
        keep = [t for t in toks if t in self.ph_tok]
        if toks and len(keep) < 0.95 * len(toks):
            raise RuntimeError(
                f"g2p coverage {len(keep)}/{len(toks)} below 95% — unmapped: "
                + ",".join(sorted(set(toks) - set(keep))))
        return keep


def main(argv: list[str]) -> int:
    jobs_path, bundle = argv[0], argv[1]
    phoneme = argv[2] if len(argv) > 2 and argv[2] != "-" else None
    device = argv[3] if len(argv) > 3 else "cuda"

    al = Aligner(bundle, phoneme, device)
    with open(jobs_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            rec = {"item_id": job["item_id"]}
            try:
                if job.get("mode") == "B":
                    rec["phones"] = al.phones(job["audio_path"], job.get("transcript", ""))
                else:
                    rec["words"] = al.words(job["audio_path"], job.get("transcript", ""))
            except Exception as e:  # one bad utterance must not lose the cell
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
