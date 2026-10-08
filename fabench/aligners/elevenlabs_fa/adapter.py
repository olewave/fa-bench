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

"""ElevenLabs forced alignment. Audio and the reference transcript go in, and
word times come out. TRACK 1, word tier, commercial.

It shares the account and the key with the Scribe row (`elevenlabs`, Track 2),
which decodes its own words. This one is handed the words, so it is measured on
the task MFA and Olign are measured on, and the two rows together show what
ElevenLabs' recognition costs it.

Everything that makes a paid endpoint safe to run comes from CloudASR. That is
the response cache, the spend cap (`max_calls`), the key from `.fabench.env`,
the per-request latency, and the stop when the account runs out of credit. The
transcript goes out as the request's `text` and into the cache key.
"""
from fabench.timestamp_asrs.cloud.adapter import CloudASR


class ElevenLabsFA(CloudASR):
    """POST /v1/forced-alignment with the audio and the reference transcript."""

    provider = "elevenlabs_fa"
    default_model = "forced-alignment"
    ignores_transcript = False
    sends_transcript = True
    #: Each word comes with ElevenLabs' alignment `loss`, lower being better and
    #: with no stated scale, so no confidence is claimed for it.
    emits_confidence = False
