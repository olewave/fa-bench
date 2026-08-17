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
                    reference phone sequence.
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
    def phones(self, audio_path: str, phone_seq: list[str]):
        if self.phoneme is None:
            raise RuntimeError("no phoneme_model configured")
        target_sr = self.ph_proc.feature_extractor.sampling_rate
        x, _ = load_resample(audio_path, target_sr)
        n_samples = len(x)
        inputs = self.ph_proc(x, sampling_rate=target_sr, return_tensors="pt")
        with torch.inference_mode():
            logits = self.ph_model(inputs.input_values.to(self.device)).logits
            logp = torch.log_softmax(logits, dim=-1)
        ratio = n_samples / logp.size(1) / target_sr

        wanted = [p for p in phone_seq if p.lower() not in _SILENCE]
        keep = []
        for p in wanted:
            ipa = ARPA_TO_ESPEAK.get(p.lower())
            if ipa is not None and ipa in self.ph_tok:
                keep.append(ipa)
        targets = [self.ph_tok[p] for p in keep]
        if not targets:
            raise RuntimeError("no phone_seq tokens in phoneme model vocab")
        # Fail loudly rather than align a fraction and report it as a tier.
        if len(keep) < _MIN_COVERAGE * max(len(wanted), 1):
            raise RuntimeError(
                f"phone_seq coverage {len(keep)}/{len(wanted)} below "
                f"{_MIN_COVERAGE:.0%} — unmapped: "
                + ",".join(sorted({p for p in wanted
                                   if ARPA_TO_ESPEAK.get(p.lower()) not in self.ph_tok})))
        blank = self.ph_model.config.pad_token_id or 0
        tgt = torch.tensor([targets], dtype=torch.int32, device=self.device)
        aligned, scores = self.F.forced_align(logp, tgt, blank=blank)
        spans = self.F.merge_tokens(aligned[0], scores[0].exp())
        return [[p, s.start * ratio, s.end * ratio, float(s.score)]
                for s, p in zip(spans, keep)]


# --- ARPABET/TIMIT-39 -> eSpeak IPA ----------------------------------------
# The phoneme model is facebook/wav2vec2-lv-60-espeak-cv-ft, whose 392-symbol
# vocabulary is eSpeak IPA. FA-Bench hands the reference sequence in ARPABET.
# Without this table the old code kept only `p in self.ph_tok`, which is the
# accidental spelling overlap between the two alphabets: 17 consonants, every
# vowel dropped, 39% of the reference aligned and scored as if it were whole.
#
# Every target below was checked to be present in the model vocabulary, and to
# fold back through fabench's IPA_TO_39 to the ARPABET symbol it came from --
# exact for all 38, so the emitted labels normalize to the right phone.
#
# `sil` has no target: silence is the CTC blank, not something to align to.
ARPA_TO_ESPEAK = {
    # Generated by composing fabench's TIMIT61_TO_39 and ARPABET_TO_39
    # with the TIMIT-39 -> eSpeak correspondence, so this table and the
    # scorer's folding cannot disagree. Raw TIMIT-61 arrives here (the
    # runner passes gold labels verbatim: h#, ix, ax, axr, dcl ...), which
    # is why a TIMIT-39-only table covered just 70% of the sequence.
    # Silence and closures are deliberately absent: they have no target.
    "aa": "ɑ", "ae": "æ", "ah": "ʌ", "ao": "ɑ", "aw": "aʊ",
    "ax": "ʌ", "ax-h": "ʌ", "axr": "ɜ", "ay": "aɪ", "b": "b",
    "ch": "tʃ", "d": "d", "dh": "ð", "dx": "ɾ", "eh": "ɛ",
    "el": "l", "em": "m", "en": "n", "eng": "ŋ", "er": "ɜ",
    "ey": "eɪ", "f": "f", "g": "ɡ", "hh": "h", "hv": "h",
    "ih": "ɪ", "ix": "ɪ", "iy": "i", "jh": "dʒ", "k": "k",
    "l": "l", "m": "m", "n": "n", "ng": "ŋ", "nx": "n",
    "ow": "oʊ", "oy": "ɔɪ", "p": "p", "r": "ɹ", "s": "s",
    "sh": "ʃ", "t": "t", "th": "θ", "uh": "ʊ", "uw": "u",
    "ux": "u", "v": "v", "w": "w", "y": "j", "z": "z",
    "zh": "ʃ",
}
_SILENCE = {"sil", "sp", "spn", ""}
#: Refuse to align a sequence we can barely represent. gate#10 catches this in
#: the published tables; failing here means it never reaches them.
_MIN_COVERAGE = 0.65


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
                if job.get("mode") == "B" and job.get("phone_seq"):
                    rec["phones"] = al.phones(job["audio_path"], job["phone_seq"])
                else:
                    rec["words"] = al.words(job["audio_path"], job.get("transcript", ""))
            except Exception as e:  # one bad utterance must not lose the cell
                rec["error"] = f"{type(e).__name__}: {e}"
            print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
