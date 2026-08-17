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

"""torchaudio forced alignment -- wav2vec2 CTC, the reference implementation.

Runs in its OWN interpreter (see fabench/aligners/subprocess_aligner.py). It
used to import torch/torchaudio in-process from the shared `.venv`, which made
that venv carry a ~3 GB CUDA torch build for exactly one consumer, and tied this
tool's numbers to whatever the shared environment happened to resolve to -- the
failure that already moved Charsiu's and BFA's torch when whisperx was
installed.

Both tiers come from the worker:

  Mode A (words)  -- a torchaudio bundle, CTC forced alignment over CHARACTER
                     tokens, spans merged back into words.
  Mode B (phones) -- a HuggingFace CTC phoneme model over the reference phones.

Useful as the "plain wav2vec2 CTC" baseline against which WhisperX (same
family, different wrapper) and Charsiu can be read.
"""
from __future__ import annotations

from fabench.aligners.base import BatchItem
from fabench.aligners.subprocess_aligner import SubprocessAligner


class TorchaudioFA(SubprocessAligner):
    name = "torchaudio_fa"
    granularity = ("word", "phone")
    default_model = "WAV2VEC2_ASR_BASE_960H"

    def load(self) -> None:
        """Also declare the PHONE INVENTORY the worker will emit.

        `source` picks the normalization table the scorer canonicalizes with
        (fabench.normalize.SOURCES). The espeak phoneme model emits IPA, not the
        ARPABET the base class assumes, and leaving the default in place scored
        IPA phones through the ARPABET map: 5,474 boundaries matched instead of
        5,348, and every phone metric shifted. Mode A is unaffected -- words are
        not canonicalized -- which is why only the phone row moved.
        """
        super().load()
        self.source = str(self.params.get("phoneme_source", "ipa"))

    def _job(self, it: BatchItem) -> dict:
        """Carry the mode and the phone sequence, which the base job omits.

        Every other subprocess tool aligns words from a transcript, so the base
        record is (item_id, audio_path, transcript). This one also does phone
        Mode B, and the reference phone sequence is the input for it -- without
        these two keys the worker would silently fall back to word alignment and
        the phone tier would come back empty.
        """
        j = super()._job(it)
        j["mode"] = it.mode
        if it.phone_seq:
            j["phone_seq"] = list(it.phone_seq)
        return j

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <bundle> <phoneme_model|-> <device>."""
        return [str(self.params.get("phoneme_model") or "-"),
                str(self.params.get("device", "cuda"))]
