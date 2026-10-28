# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0


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
