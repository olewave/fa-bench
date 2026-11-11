# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""FuseAlign as Zyphra packages it (``fusealign_hub``), word tier only, own venv.

The worker drives the package's batched ``align_batch`` API in the venv that
``download_and_install.sh`` builds. ``params.model`` is the Hugging Face repo,
``revision`` pins its commit and ``checkpoint`` names the ``fusealign-hub/1``
safetensors file in it; ``device`` and ``batch_size`` go to ``load_aligner``.

``unplaced`` picks what happens to words the model does not place (presence
< 0.1): ``fallback`` keeps the package's uniform fallback interval, ``drop``
omits them. Either way the worker reports their count as ``n_unplaced``.

Each word's presence probability is its confidence.
"""

from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class FuseAlignHub(SubprocessAligner):
    source = "orthographic"
    emits_confidence = True
    granularity = ("word",)
    default_model = "Zyphra/fusealign"

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <model> <revision> <checkpoint> <device> <batch_size> <unplaced>."""
        p = self.params
        return [str(p.get("revision", "main")),
                str(p.get("checkpoint", "fusealign-multilingual-cjkft-step2500.safetensors")),
                str(p.get("device", "cuda")),
                str(p.get("batch_size", 64)),
                str(p.get("unplaced", "fallback"))]
