# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
