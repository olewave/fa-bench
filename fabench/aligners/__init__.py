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

"""Aligner registry (Plan 1.5 / S4). Maps a config adapter name to its class."""

from __future__ import annotations

from fabench.aligners.base import AlignerAdapter
from fabench.config import AlignerSpec

_REGISTRY = {
    "torchaudio_fa": "fabench.aligners.torchaudio_fa:TorchaudioFA",
    "charsiu": "fabench.aligners.charsiu:Charsiu",
    "whisperx": "fabench.aligners.whisperx:WhisperX",
    "mfa": "fabench.aligners.mfa:MFA",
    "bfa": "fabench.aligners.bfa:BFA",
    "maps": "fabench.aligners.maps:MAPS",
    "olign": "fabench.aligners.olign:Olign",
    # Qwen3-ForcedAligner-0.6B: a real forced aligner (audio + reference
    # transcript -> word times), NOT the Qwen3-ASR model of a similar name.
    "qwen3_fa": "fabench.aligners.qwen3_fa:Qwen3FA",
    # stable-ts: Whisper with stabilised timestamps, driven through its
    # align() API on the reference transcript -- track 1, word tier only.
    "stable_ts": "fabench.aligners.stable_ts:StableTS",
    # TIMESTAMPED ASRs. They satisfy the aligner interface so the scoring
    # path can drive them, but they IGNORE the reference transcript and
    # decode their own -- their rows mix recognition with timing error and
    # must not be ranked head-to-head against aligners. Registered here
    # because this is the adapter registry; the semantics live in
    # fabench.timestamp_asrs and evals/timestamp_asrs/.
    "crisperwhisper": "fabench.timestamp_asrs.crisperwhisper:CrisperWhisper",
    # Same model, FORCED-ALIGNMENT mode: it ships a native forced_align(),
    # so it is a genuine track-1 aligner, not an ASR in an aligner table.
    "crisperwhisper_fa": "fabench.aligners.crisperwhisper_fa:CrisperWhisperFA",
    "parakeet_tdt": "fabench.timestamp_asrs.parakeet_tdt:ParakeetTDT",
    "neufa": "fabench.aligners.neufa:NeuFA",
}


def get_adapter(spec: AlignerSpec) -> AlignerAdapter:
    if spec.adapter not in _REGISTRY:
        raise KeyError(f"no adapter {spec.adapter!r}; known: {sorted(_REGISTRY)}")
    module_path, cls_name = _REGISTRY[spec.adapter].split(":")
    import importlib

    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    adapter = cls(spec.name, spec.params)
    # carry declared traits from config where the class doesn't override
    if spec.emits_confidence:
        adapter.emits_confidence = True
    return adapter
