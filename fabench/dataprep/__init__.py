# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Corpus preparation: turning source material into FA-Bench inputs.

Two subpackages, split by what they prepare:

* ``datasets`` -- corpus ANNOTATIONS into FA-Bench's manifest format
  (TIMIT/Buckeye/L2-ARCTIC processors, plausibility checks, TextGrid render).
  This is the imported API: ``from fabench.dataprep.datasets import
  ingest_corpus``.
* ``noisemix`` -- corpus AUDIO into the four Kaldi noise conditions. Run once,
  offline, through ``fabench prepare``; nothing at benchmark runtime imports it.

Deliberately NOT re-exported here. ``ingest_corpus`` moved to ``.datasets``
and a shim would leave both spellings working, so a stale import would keep
resolving instead of failing where it is written.
"""
