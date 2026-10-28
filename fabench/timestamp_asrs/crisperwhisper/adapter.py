# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""CrisperWhisper — verbatim ASR with word timestamps (Interspeech 2024).

Zusag, Wagner & Thallinger, DOI 10.21437/Interspeech.2024-731, arXiv:2408.16589.
Retokenized Whisper + DTW over cross-attention.

NOT a forced aligner — it ignores the reference transcript and times its own
hypothesis. See fabench/timestamp_asrs/subprocess_asr.py for what that means
when reading its rows.

frame_s: Whisper's encoder emits ~50 frames/s after its stride-2 conv, so
attention-derived timing is natively ~20 ms granular. That is an architectural
bound, not a tuning limit, and it caps what a sub-20 ms tolerance can show.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class CrisperWhisper(SubprocessTimestampASR):
    default_model = "nyrahealth/CrisperWhisper"
    frame_s = 0.020

    def _extra_argv(self) -> list[str]:
        # ASR mode: decode its own transcript. The same worker also serves
        # `crisperwhisper_fa` in fabench.aligners with mode=forced_align.
        return ["transcribe"]
