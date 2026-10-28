# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""BFA — Bournemouth Forced Aligner (Rehman et al. 2025, arXiv:2509.23147).

Neural CUPE + CTC aligner: given a transcript it phonemizes with espeak and
places per-phone onset/offset boundaries with confidence (and word timings).
Phone labels are eSpeak IPA -> canonical via the `ipa` normalization source.

Mode A (from text) only: BFA drives itself from the transcript's G2P.

Runs in its OWN interpreter (fabench/aligners/subprocess_aligner.py). It used to
import torch in-process from the shared .venv, which meant its published numbers
were set by whatever that shared environment resolved to -- installing whisperx
there once moved torch under it, which is the exposure this removes.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class BFA(SubprocessAligner):
    name = "bfa"
    source = "ipa"
    emits_confidence = True
    granularity = ("word", "phone")
    default_model = "en-us"          # BFA calls it a preset

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <preset> <preset> <device>."""
        return [str(self.params.get("preset", "en-us")),
                str(self.params.get("device", "cuda"))]
