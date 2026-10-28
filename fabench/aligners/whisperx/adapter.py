# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""WhisperX forced alignment -- wav2vec2 alignment head, word level only.

Runs in its OWN interpreter (fabench/aligners/subprocess_aligner.py).

It used to have a private venv that it appended to `sys.path`, importing
whisperx in-process so that torch and transformers still resolved to FA-Bench's
shared environment. The adapter said what that cost: "That only holds while the
two agree on torch -- pin them together." The package was isolated; its
dependency set was not, and installing whisperx into the shared venv had already
moved torch under Charsiu and BFA once.

Word level only: WhisperX emits no phone tier, so it appears in the WBE tables
and never in the phone ones.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class WhisperX(SubprocessAligner):
    name = "whisperx"
    source = "arpabet"
    granularity = ("word",)
    default_model = "WAV2VEC2_ASR_BASE_960H"   # whisperx picks its own EN head

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <model> <device>."""
        return [str(self.params.get("device", "cuda"))]
