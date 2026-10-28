# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""MUSAN/RIRS noise conditions for TIMIT and Buckeye.

Offline dataset construction, not benchmark runtime. The entry point is
``fabench prepare`` (``prepare.py``), which runs ``datadirs.py``,
``make_noisy.py`` (or the ``make_noisy.sh`` it was ported from; the two are
verified to produce identical audio) and ``shadow_root.py``.
"""
