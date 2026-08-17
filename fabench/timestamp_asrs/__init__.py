# Copyright 2026  Olewave, LLC

# See LICENSE at the repository root for the full terms
#
# Licensed under the PolyForm Noncommercial License 1.0.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Noncommercial use is permitted -- research, teaching, personal study, and work
# by charitable, educational, public-safety, environmental and government
# organisations. Any commercial use requires a separate licence from Olewave, LLC.
#
# AS FAR AS THE LAW ALLOWS, THE SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR
# CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING
# OUT OF THESE TERMS OR THE USE OR NATURE OF THE SOFTWARE, UNDER ANY KIND OF
# LEGAL CLAIM.

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
                     the ASR in olign's long-form pipeline.
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
