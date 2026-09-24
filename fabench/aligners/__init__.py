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
    # Decodes its own words, then times them with Qwen3-ForcedAligner-0.6B
    # -- the same checkpoint scored as `qwen3_fa` in track 1.
    "qwen3_asr": "fabench.timestamp_asrs.qwen3_asr:Qwen3ASR",
    "whisper3": "fabench.timestamp_asrs.whisper3:Whisper3",
    "torchaudio_asr": "fabench.timestamp_asrs.torchaudio_asr:TorchAudioASR",
    "whisperx_asr": "fabench.timestamp_asrs.whisperx_asr:WhisperXASR",
    # whisper-timestamped: Whisper plus cross-attention DTW, one step only.
    "whisper_ts": "fabench.timestamp_asrs.whisper_ts:WhisperTS",
    # COMMERCIAL timestamped ASRs, one step. HTTPS endpoints, no venv and no
    # SDK -- see fabench/timestamp_asrs/cloud/. Their rows are marked
    # `access: commercial` in the recipe because the model behind an endpoint
    # can change without a version, so they are reported apart from the
    # open-weight track rather than mixed into one leaderboard.
    "deepgram": "fabench.timestamp_asrs.cloud:Deepgram",
    "assemblyai": "fabench.timestamp_asrs.cloud:AssemblyAI",
    "elevenlabs": "fabench.timestamp_asrs.cloud:ElevenLabs",
    "google_stt": "fabench.timestamp_asrs.cloud:GoogleSTT",
    "speechmatics": "fabench.timestamp_asrs.cloud:Speechmatics",
    "ibm": "fabench.timestamp_asrs.cloud:IBMWatson",
    "aws": "fabench.timestamp_asrs.cloud:AWSTranscribe",
    "azure": "fabench.timestamp_asrs.cloud:AzureSpeech",
    "neufa": "fabench.aligners.neufa:NeuFA",
    # Phone tier, mode B only -- its English path requires the phone
    # sequence; text goes through a Dutch G2P. See the adapter docstring.
    "falcon": "fabench.aligners.falcon:Falcon",
    # UnitY2's alignment extractor: word tier only, 20ms unit frames.
    "unity2": "fabench.aligners.unity2:UnitY2",
    # NeMo Forced Aligner: Viterbi over a NeMo CTC model's posteriors.
    # Word tier only -- its token tier is subword text, not phones.
    "nemo_fa": "fabench.aligners.nemo_fa:NemoFA",
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
