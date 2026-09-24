# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Commercial timestamped ASR APIs, Track 2 one-step.

These rows are NOT reproducible in the sense the open-weight rows are: the
model behind an endpoint can change without notice and without a version
number, so a row records what the service returned on the date in the recipe
and nothing stronger. That is a property of the systems, not of the benchmark,
and it is why they are marked `access: commercial` and reported apart from the
open-weight track rather than mixed into one leaderboard.
"""
from fabench.timestamp_asrs.cloud.adapter import (
    AssemblyAI,
    AWSTranscribe,
    AzureSpeech,
    CloudASR,
    Deepgram,
    ElevenLabs,
    GoogleSTT,
    IBMWatson,
    Speechmatics,
)

__all__ = ["CloudASR", "Deepgram", "AssemblyAI", "ElevenLabs", "GoogleSTT",
           "IBMWatson", "Speechmatics", "AWSTranscribe", "AzureSpeech"]
