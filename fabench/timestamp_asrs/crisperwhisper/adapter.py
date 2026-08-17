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
