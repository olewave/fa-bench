# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""olign aligner subpackage.

Layout of a per-model aligner package (the pattern all aligners follow):
    adapter.py   the AlignerAdapter subclass + any pure helpers
    README.md    what it is, how to point fabench at it, licence/citation

Public names are re-exported here so the registry entry
(``fabench.aligners.olign:Olign``) and existing imports keep resolving after
the module->subpackage move.
"""
from fabench.aligners.olign.adapter import (
    Olign,
    build_query,
    parse_olign_result,
)

__all__ = ["Olign", "build_query", "parse_olign_result"]
