# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""CrisperWhisper in FORCED-ALIGNMENT mode — audio + reference transcript.

The `crisperwhisper` package exposes a native
`CrisperWhisperModel.forced_align(audio, text, language=...)`, so the model can
be measured on the same task as MFA, olign and qwen3_fa: given the words, where
are they?

**This supersedes the original plan**, which proposed
implementing teacher forcing by hand (forced decode + cross-attention DTW).
None of that is needed — the capability ships.

Distinct from `fabench.timestamp_asrs.crisperwhisper`, which calls `transcribe`
and decodes its own words. Same model, same venv, different input contract:

    crisperwhisper      audio only            -> timestamp_asrs (track 2)
    crisperwhisper_fa   audio + reference     -> aligners       (track 1)

Reusing the one venv is deliberate: it is the same package, so there is no
dependency conflict to isolate, and a second 6 GB copy would buy nothing. The
isolation policy is about conflicts BETWEEN tools, not per registry entry.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class CrisperWhisperFA(SubprocessAligner):
    source = "orthographic"
    emits_confidence = False
    granularity = ("word",)
    default_model = "nyrahealth/CrisperWhisper"
    #: Whisper's encoder is ~50 fps, so attention-derived timing is ~20 ms
    #: granular natively — an architectural bound, not a tuning limit.
    frame_s = 0.020

    def _extra_argv(self) -> list[str]:
        return ["forced_align"]
