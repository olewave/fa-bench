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

"""Load the vendored MFA-2026 benchmark-repo ``custom_mapping`` YAMLs
(``vendor/mapping_files/``, see ``vendor/THIRD_PARTY_NOTICES.md`` for provenance).
"""

from __future__ import annotations

from pathlib import Path

import yaml

_VENDOR_MAPPING_DIR = Path(__file__).with_name("vendor") / "mapping_files"


def mapping_path(aligner_key: str, corpus: str, mapping_dir: str | None = None) -> Path:
    base = Path(mapping_dir) if mapping_dir else _VENDOR_MAPPING_DIR
    return base / f"{aligner_key}_{corpus}_mapping.yaml"


def load_mapping(path: Path) -> dict[str, set[str]]:
    """Parse one ``custom_mapping`` YAML into ``{test_label: {ref_label, ...}}``.

    Mirrors MFA's own loader (``AlignmentComparer.load_mapping`` /
    ``load_evaluation_mapping``): a scalar string value becomes a singleton set,
    e.g. ``TH: th`` -> ``{"TH": {"th"}}``.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    out: dict[str, set[str]] = {}
    for k, v in raw.items():
        if isinstance(v, str):
            out[k] = {v}
        else:
            out[k] = set(v)
    return out
