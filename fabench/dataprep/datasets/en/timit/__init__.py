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

"""TIMIT data processor.

Ingestion logic lives in ``processor.py``; the public API is re-exported here so
``from fabench.dataprep.datasets.en.timit import iter_utterances`` keeps resolving after the
module->subpackage move. See ``README.md`` for the source format and options.
"""
from .processor import (
    _merge_closures,
    _parse_intervals,
    iter_utterances,
    parse_utterance,
)

__all__ = ["_merge_closures", "_parse_intervals", "iter_utterances", "parse_utterance"]
