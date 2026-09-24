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


"""WhisperX run end to end: Whisper decodes, wav2vec2 CTC re-aligns.

Track 2, because no transcript is given to it. This is deliberately a DIFFERENT
row from `whisperx` in track 1, which is handed the reference and exercises the
alignment stage alone. Same package, two configurations, and the benchmark
scores both rather than letting one stand for the other:

  * track 1 `whisperx`      -- reference words in, timing error only
  * track 2 `whisperx_asr`  -- audio in, recognition and timing together

The pairing is what makes it informative. Whisper large-v3 is scored in track 2
on its own cross-attention times; WhisperX's reason to exist is that those times
are poor. Reading the two rows over the same audio says how much the wav2vec2
stage recovers, and reading this row against track-1 `whisperx` says how much
recognition error costs the same aligner.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class WhisperXASR(SubprocessTimestampASR):
    #: faster-whisper's own name for the checkpoint, not the HF repo id --
    #: whisperx.load_model resolves it through faster-whisper.
    default_model = "large-v3"
    frame_s = 0.02
