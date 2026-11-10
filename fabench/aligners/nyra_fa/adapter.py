# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""nyra forced aligner, word times, via subprocess.

https://huggingface.co/nyralabs/nyra_forced_aligner_en

WavLM-large features under a triphone GMM-HMM, from nyra labs. It takes audio
and the reference transcript and returns every word with a confidence. It
also returns phones, in a 39 phone set that FA-Bench has no mapping for yet,
so only the word tier is scored. The `nyra-forced-aligner` package is MIT. The model is under the
nyra health Non-Commercial Research License, so read that licence before you
run it for anything else.

It runs in its own interpreter, as every tool with its own torch build does
here. See `fabench.aligners.subprocess_aligner`.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class NyraFA(SubprocessAligner):
    emits_confidence = True
    granularity = ("word",)
    default_model = "nyralabs/nyra_forced_aligner_en"

    def _extra_argv(self) -> list[str]:
        return [str(self.params.get("device", "cuda"))]
