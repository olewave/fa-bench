# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Charsiu — wav2vec2 frame classifier, phone + word forced alignment.

github.com/lingjzhu/charsiu. Ships custom model classes, so its repo `src/`
must be importable — passed to the worker as an argument.

RUNS IN ITS OWN INTERPRETER (evals/aligners/charsiu/repo/env). It used to import
in-process from FA-Bench's shared `.venv`, which meant another tool's install
could redefine its dependencies: whisperx's install moved this tool's
transformers 5.14.1 -> 4.57.6 and torch 2.13 -> 2.8 without anything failing.
Its `repo/env` existed all along and was simply unused, which is worse than
having none — it looked isolated.

Its env also carried torch cu130 against this box's 12.9 driver, so
`torch.cuda.is_available()` was False and it ran on CPU. Pinned to cu128.
"""
from fabench.aligners.subprocess_aligner import SubprocessAligner


class Charsiu(SubprocessAligner):
    source = "arpabet"
    emits_confidence = True
    granularity = ("word", "phone")
    default_model = "charsiu/en_w2v2_fc_10ms"

    def _extra_argv(self) -> list[str]:
        # Charsiu's custom model classes live in its checkout's src/
        return [str(self.params.get("repo_path", ""))]
