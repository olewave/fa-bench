# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""NVIDIA Parakeet-TDT 0.6B v3 — ASR with intrinsic word timestamps.

https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3

TDT = Token-and-Duration Transducer: it predicts token DURATIONS, so timestamps
fall out of decoding rather than being estimated afterwards. It is a
production-grade ASR rather than a research checkpoint, which makes it an
operationally relevant row here.

NOT a forced aligner — it ignores the reference transcript. See
fabench/timestamp_asrs/subprocess_asr.py.

frame_s MEASURED at 80 ms. The TDT duration head predicts in encoder frames
and the effective resolution is not documented, so it was read off the
hypotheses rather than assumed.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class ParakeetTDT(SubprocessTimestampASR):
    default_model = "nvidia/parakeet-tdt-0.6b-v3"
    frame_s = 0.080
