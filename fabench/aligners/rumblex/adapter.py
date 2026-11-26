# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""rumblex forced alignment -- an ASR model's own CTC head, word level only.

rumblex (https://github.com/EdwardGlockner/rumblex) runs the encoder of
Reson8/Rumble-2-Flash and force-aligns the reference transcript to the
auxiliary CTC head that ships with the checkpoint (`rumblex.align`). There is
no second alignment model. The head shares the decoder's subword vocabulary and
the encoder emits 13 frames a second, so boundaries sit on an 80 ms grid that
rumblex then refines with a small linear map on the encoder states.

Runs in its OWN interpreter (fabench/aligners/subprocess_aligner.py).

Word level only: the head has no phone tier, so rumblex appears in the WBE
tables and never in the phone ones.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class Rumblex(SubprocessAligner):
    name = "rumblex"
    source = "orthographic"
    granularity = ("word",)
    default_model = "Reson8/Rumble-2-Flash"

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <model> <device>."""
        return [str(self.params.get("device", "cuda"))]
