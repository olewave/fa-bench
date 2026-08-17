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

"""stable-ts — Whisper with stabilised timestamps, driven as a forced aligner.

https://github.com/jianfch/stable-ts

stable-ts wraps Whisper and post-processes its timestamps, and exposes
``model.align(audio, text, language=...)`` — audio **plus the reference
transcript**, returning one segment/word per reference token. That is the
track-1 contract, so it belongs here beside MFA and olign rather than in
``fabench.timestamp_asrs``: it is not decoding its own words.

**Word-level only.** stable-ts aligns to word tokens; there is no phone tier, so
it is absent from the phone tables by construction, exactly like WhisperX and
Qwen3.

WHY SUBPROCESS. Same reason as every other tool here: its dependency set
conflicts with the shared ``.venv``. stable-ts pins its own openai-whisper and
torch range, and whisperx already moved transformers/torch once in this repo
when it was installed into the shared env. One interpreter per tool is the only
thing that actually isolates two dependency sets — see
``fabench/aligners/subprocess_aligner.py`` for the full argument.

Comparability note: stable-ts is a Whisper derivative, so like WhisperX it is
evaluated at FA-Bench's 20 ms tolerance while its own literature uses far wider
collars. Read its boundary F1 with that in mind.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class StableTS(SubprocessAligner):
    """Runs stable-ts in its own interpreter; word tier only."""

    name = "stable_ts"
    default_model = "base"
    worker_name = "worker.py"
    #: given the reference transcript, so track 1 -- NOT a timestamped ASR
    ignores_transcript = False
