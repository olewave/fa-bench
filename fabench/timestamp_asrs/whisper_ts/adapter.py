# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""whisper-timestamped -- Whisper with cross-attention DTW word times.

TRACK 2, ONE STEP ONLY. It decodes its own words and times them in the same
pass, and exposes no entry point that takes a supplied transcript, so it cannot
enter Track 1 and nothing can be cascaded on it.

Sibling of stable_ts, which times Whisper the same way. Having both answers the
obvious question about stable-ts sitting at 91 ms, whether that is the approach
or one implementation of it.
"""
from fabench.timestamp_asrs.subprocess_asr import SubprocessTimestampASR


class WhisperTS(SubprocessTimestampASR):
    source = "orthographic"
    emits_confidence = True
    granularity = ("word",)
    default_model = "large-v3"
    #: Whisper's encoder is ~50 fps, so attention-derived timing is ~20 ms
    #: granular natively.
    frame_s = 0.020

    def _extra_argv(self) -> list[str]:
        return [str(self.params.get("device", "cuda"))]
