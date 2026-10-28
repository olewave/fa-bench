# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""NeuFA — Neural Network Based End-to-End Forced Alignment.

Li et al., ICASSP 2022 (arXiv:2203.16838) | github.com/thuhcsi/NeuFA

A bidirectional-attention model that aligns text and speech jointly rather than
decoding a per-frame path. Text-driven (Mode A only): it runs its own sequitur
G2P over the transcript.

Runs in its OWN interpreter (fabench/aligners/subprocess_aligner.py). It used to
put the NeuFA checkout on FA-Bench's `sys.path` and import its `inference`
module in-process -- with a guard against that import being shadowed, which is
the tell that a research repo's modules were sharing the benchmark's namespace.
It also took torch from the shared .venv, and was the last adapter to do so.

NOT INSTALLED BY DEFAULT: NeuFA publishes no trained checkpoint, so
evals/aligners/neufa/download_and_install.sh builds the environment and clones
the repo but cannot finish. Supply neufa.pt, then enable it in
evals/config.yaml.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class NeuFA(SubprocessAligner):
    name = "neufa"
    granularity = ("word", "phone")
    default_model = "neufa"

    def _extra_argv(self) -> list[str]:
        """worker.py <jobs> <model> <repo_path> <model_path> <device>."""
        return [str(self.params.get("repo_path", "repo")),
                str(self.params.get("model_path", "repo/neufa.pt")),
                str(self.params.get("device", "cuda"))]
