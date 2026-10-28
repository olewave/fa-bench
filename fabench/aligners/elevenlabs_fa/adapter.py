# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
