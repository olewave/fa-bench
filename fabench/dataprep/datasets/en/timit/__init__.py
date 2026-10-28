# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
