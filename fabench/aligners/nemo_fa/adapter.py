# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""NVIDIA NeMo Forced Aligner (NFA) -- WORD TIER ONLY.

NFA is Viterbi alignment over the CTC posteriors of a NeMo ASR model, so what
it can time is whatever that model emits. Every English checkpoint NVIDIA ships
is a character or BPE model, which means the token tier NFA writes is subword
text, not phones. There is no phone tier here and no mode B: the units are not
phones, so a gold phone sequence has nothing to attach to.

The frame rate is the model's, not the aligner's, and it is coarse. The
checkpoint NFA's own README uses, stt_en_fastconformer_hybrid_large_pc,
subsamples 8x from a 10 ms window, so its posteriors arrive every 80 ms and no
boundary it places can be sharper than that. That is a property of the tool as
people actually run it, and the table reports it rather than papering over it
by swapping in a finer model nobody uses.

CTM is the only output NFA offers and it writes two decimal places, so the
timestamps this adapter reads are quantised to 10 ms on top of the model's own
stride. Both quantisations are far below the 80 ms frame, so neither changes
the ranking.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class NemoFA(SubprocessAligner):
    source = "orthographic"
    granularity = ("word",)
    default_model = "stt_en_fastconformer_hybrid_large_pc"
    #: 8x subsampling of a 10 ms window in the FastConformer encoder. The
    #: CHECKPOINT sets this, not the aligner, so a variant recipe overrides it
    #: through params -- nemo_fa_conformer reads 40 ms off a 4x Conformer.
    #: Nothing consumes it yet; it documents the row's resolution floor, and a
    #: stale value here would misdescribe a row rather than miscompute one.
    frame_s = 0.080

    def load(self) -> None:
        super().load()
        self.frame_s = float(self.params.get("frame_s", type(self).frame_s))

    def _extra_argv(self) -> list[str]:
        return [
            str(self.params["repo"]),
            str(self.params.get("device", "cuda")),
            str(self.params.get("batch_size", 4)),
        ]
