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

"""NVIDIA Parakeet-TDT 0.6B v3 — ASR with intrinsic word timestamps.

https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3

TDT = Token-and-Duration Transducer: it predicts token DURATIONS, so timestamps
fall out of decoding rather than being estimated afterwards. This is also the
ASR in olign's long-form pipeline, which makes it the operationally relevant
row here.

NOT a forced aligner — it ignores the reference transcript. See
fabench/timestamp_asrs/subprocess_asr.py.

frame_s left None: the TDT duration head predicts in encoder frames, and the
effective resolution is not a single documented constant. Measure it rather than
assume one.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class ParakeetTDT(SubprocessTimestampASR):
    default_model = "nvidia/parakeet-tdt-0.6b-v3"
    frame_s = None
