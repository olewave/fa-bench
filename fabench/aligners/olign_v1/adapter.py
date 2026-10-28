# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Olign 1.0, given the reference transcript. A Track 1 forced aligner.

Olewave's job API at https://api.olewave.com/olign/v1. The audio and the
transcript go up together, the job is polled until it is done, and the
answer carries every word and its phones with times in seconds. The call
itself lives with the cloud providers (fabench/timestamp_asrs/cloud), which
already cache, retry and run requests concurrently.

The same endpoint without a transcript recognizes the words first. That is
the Track 2 row, fabench.timestamp_asrs.cloud.OlignV1ASR.
"""
from __future__ import annotations

from fabench.timestamp_asrs.cloud.adapter import CloudASR


class OlignV1(CloudASR):
    """POST /olign/v1 with the audio and the reference transcript, then poll."""
    provider = "olign_v1"
    default_model = "olign-1.0"
    source = "arpabet"
    granularity = ("word", "phone")
    ignores_transcript = False
    sends_transcript = True
