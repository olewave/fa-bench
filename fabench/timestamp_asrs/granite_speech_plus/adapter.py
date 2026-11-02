# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""IBM Granite Speech 4.1 2B-plus — speech LLM that writes word end times.

https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus

NOT a forced aligner — it ignores the reference transcript. See
fabench/timestamp_asrs/subprocess_asr.py.

Prompted for timestamps, it emits an end-time tag after each word in
centiseconds, and a `_` token for each silence. There is no start time, so
the worker starts each word where the token before it ended. The timing comes
from the same decode as the words, which makes this a one-step row.

frame_s MEASURED at 10 ms: every boundary on TIMIT core test sits on a
10 ms step, which is the centisecond tag itself. At that step the 20 ms
tolerance is not capped.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class GraniteSpeechPlus(SubprocessTimestampASR):
    default_model = "ibm-granite/granite-speech-4.1-2b-plus"
    frame_s = 0.010

    def _extra_argv(self) -> list[str]:
        return [str(int(self.params.get("num_beams", 4)))]
