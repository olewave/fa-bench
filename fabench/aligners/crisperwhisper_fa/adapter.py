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
