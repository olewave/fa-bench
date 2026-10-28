# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""English (``en``) data processors.

Data processors are organized by language — ``fabench/dataprep/<lang>/<corpus>/``.
This package groups the English-gold corpora (TIMIT, Buckeye, and L2-ARCTIC — the
last is L2/accented English, but its gold is English phones). Add another
language as a sibling package (``ko/``, ``ja/`` …); the orchestrator's
``_dispatch`` imports each corpus from its language package.
"""
