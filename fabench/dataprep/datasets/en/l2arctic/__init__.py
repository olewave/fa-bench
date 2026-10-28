# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""L2-ARCTIC data processor.

Ingestion logic lives in ``processor.py``; the public API is re-exported here.
See ``README.md`` for the source format.
"""
from .processor import iter_utterances

__all__ = ["iter_utterances"]
