# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""ASR registry — maps a config adapter name to its class.

EMPTY BY DESIGN. The contract (``base.py``) is in place; adapters land here when
the two-track word-level evaluation is agreed — see
``docs/methodology.md`` (three-track word evaluation), which still has open questions that
change what gets built.

Expected first inhabitants:

    crisperwhisper   timestamped ASR (Interspeech 2024); removed from
                     fabench.aligners on 2026-08-06 because it is not a forced
                     aligner. This is where it belongs.
    parakeet_tdt     timestamped ASR; TDT predicts token durations, so it is
                     both a transcript source and a timestamped row. Already
                     a production-grade ASR rather than a research checkpoint.
    whisper_v3_large transcript source for the forced aligners.
    qwen3_asr        transcript source (Qwen3-ASR-1.7B). NOTE: the separate
                     Qwen3-ForcedAligner-0.6B is a forced ALIGNER and belongs in
                     fabench.aligners, not here.
"""

from __future__ import annotations

import importlib

from fabench.timestamp_asrs.base import ASRAdapter

_REGISTRY: dict[str, str] = {}


def get_asr(name: str, params: dict | None = None) -> ASRAdapter:
    if name not in _REGISTRY:
        raise KeyError(
            f"no ASR adapter {name!r}; known: {sorted(_REGISTRY) or '(none registered yet)'}"
        )
    module_path, cls_name = _REGISTRY[name].split(":")
    cls = getattr(importlib.import_module(module_path), cls_name)
    return cls(name, params or {})
