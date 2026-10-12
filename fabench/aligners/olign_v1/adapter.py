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
