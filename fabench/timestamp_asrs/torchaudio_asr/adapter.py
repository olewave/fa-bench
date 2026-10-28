# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0


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
