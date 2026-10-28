# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Buckeye data processor.

Ingestion logic lives in ``processor.py``; the public API is re-exported here.
See ``README.md`` for the source format and the fabench/paper segmentation
protocols.
"""
from .processor import (
    iter_utterances,
    parse_tier,
    segment_track,
    segment_track_paper,
)

__all__ = ["iter_utterances", "parse_tier", "segment_track", "segment_track_paper"]
