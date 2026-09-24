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


"""Qwen3-ASR 1.7B — multilingual ASR that returns its own word timestamps.
https://huggingface.co/Qwen/Qwen3-ASR-1.7B

NOT a forced aligner: it ignores the reference transcript and decodes its own
words, so its row belongs in track 2. See
fabench/timestamp_asrs/subprocess_asr.py.

WHERE ITS TIMESTAMPS COME FROM, which matters when reading its row against the
aligners. Qwen3-ASR does not predict times itself. `return_time_stamps=True`
loads a SECOND model, Qwen3-ForcedAligner-0.6B, and force-aligns the transcript
it just decoded. That is the same checkpoint this benchmark already scores as a
track-1 aligner under the name `qwen3_fa`. So this row is a cascade internally:
Qwen3-ASR text, aligned by Qwen3-ForcedAligner. Comparing it against MFA run on
the same decoded text isolates the aligner, because the words are identical.

frame_s MEASURED at 80 ms, not documented. Every boundary this row emits is
a multiple of 80 ms, which caps word F1 near 0.50 at the 20 ms tolerance
however good the acoustics are, and gives 47 short words on TIMIT core test
a duration of exactly zero. See evals/measure_grid.py.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class Qwen3ASR(SubprocessTimestampASR):
    default_model = "Qwen/Qwen3-ASR-1.7B"
    frame_s = 0.080
