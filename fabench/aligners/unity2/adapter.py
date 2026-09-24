# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""UnitY2's alignment extractor (Meta, seamless_communication) -- WORD TIER.

The aligner SeamlessM4T v2 uses as its duration teacher for text-to-unit
training, exposed as a general text-audio aligner. It returns a duration in
20 ms acoustic-unit frames for every text token, so boundaries are a cumulative
sum and the time resolution is 20 ms -- the same order as the tolerance the
benchmark scores at, which is worth remembering when reading its F1.

Tokens are character SentencePiece with a leading marker on each word start, so
words are recovered by regrouping; there is no phone tier.

CPU, not CUDA: seamless_communication pins fairseq2 0.2.*, whose newest build
targets torch 2.1.1+cu121, and cu121 has no kernels for this box's Blackwell
cards ("no kernel image is available for execution on the device"). It runs at
about 0.9 s an utterance on CPU, which is affordable with several workers.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class UnitY2(SubprocessAligner):
    source = "orthographic"
    emits_confidence = False
    granularity = ("word",)
    default_model = "nar_t2u_aligner"
    #: Durations are counted in 20 ms acoustic-unit frames.
    frame_s = 0.020

    def _extra_argv(self) -> list[str]:
        return [str(self.params.get("device", "cpu"))]
