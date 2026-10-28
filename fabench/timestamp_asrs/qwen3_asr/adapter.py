# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0


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
a duration of exactly zero.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class Qwen3ASR(SubprocessTimestampASR):
    default_model = "Qwen/Qwen3-ASR-1.7B"
    frame_s = 0.080
