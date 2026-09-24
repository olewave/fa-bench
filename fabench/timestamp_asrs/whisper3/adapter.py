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


"""Whisper large-v3 — ASR with word timestamps from cross-attention.
https://huggingface.co/openai/whisper-large-v3

NOT a forced aligner: it ignores the reference transcript and decodes its own
words, so its row belongs in track 2. See
fabench/timestamp_asrs/subprocess_asr.py.

Its word times come from `return_timestamps="word"`, which reads them off the
decoder's cross-attention (dynamic time warping over attention weights) rather
than from an explicit duration head. They are therefore an estimate derived
from a model trained for transcription, not for timing -- which is the point of
scoring it here rather than assuming.

Distinct from WhisperX, already scored in track 1: WhisperX discards these
times and re-aligns with a separate wav2vec2 CTC model.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class Whisper3(SubprocessTimestampASR):
    default_model = "openai/whisper-large-v3"
    frame_s = 0.02
