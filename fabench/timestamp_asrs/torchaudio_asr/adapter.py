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


"""TorchAudio wav2vec2 CTC as a plain ASR — the weak-baseline row in track 2.
https://pytorch.org/audio (WAV2VEC2_ASR_BASE_960H)

NOT a forced aligner: it decodes its own words. Included deliberately as a
floor. The same bundle is scored in track 1 as `torchaudio_fa`, where it is
given the transcript; here it must find the words itself, so the pair shows
what recognition error costs a cascade that starts from a weak recogniser.

Expect poor WER on Buckeye: the bundle is trained on 960 h of read LibriSpeech
and this is spontaneous conversational speech.

Word times are exact in the CTC sense -- they are the frame spans of the greedy
path, not an estimate from attention -- which makes this row's timing error
attributable to recognition rather than to timestamp estimation.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class TorchAudioASR(SubprocessTimestampASR):
    default_model = "WAV2VEC2_ASR_BASE_960H"
    frame_s = 0.02
