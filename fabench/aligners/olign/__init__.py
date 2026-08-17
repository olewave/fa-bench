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

"""olign aligner subpackage.

Layout of a per-model aligner package (the pattern all aligners follow):
    adapter.py   the AlignerAdapter subclass + any pure helpers
    proto/       model-specific vendored assets (here: compiled gRPC stubs)
    README.md    what it is, how to point fabench at it, licence/citation

Public names are re-exported here so the registry entry
(``fabench.aligners.olign:Olign``) and existing imports keep resolving after
the module->subpackage move.
"""
from fabench.aligners.olign.adapter import (
    Olign,
    build_config,
    build_query,
    parse_olign_result,
)

__all__ = ["Olign", "build_config", "build_query", "parse_olign_result"]
