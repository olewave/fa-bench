# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Base for timestamped ASRs that run in their own interpreter.

Thin specialisation of `fabench.aligners.subprocess_aligner.SubprocessAligner`:
the subprocess plumbing, batching and JSONL protocol are identical, and the
only difference is the INPUT — these get audio alone.

**They IGNORE the reference transcript** (`ignores_transcript = True`, which
drops it from the job record). Consequences for reading their rows:

* their recall carries **recognition** error as well as timing error, so a low
  MAE at a low ARR is not a better system;
* `B-F1` (time-based, label-agnostic) is the honest primary metric and MAE the
  secondary — the inverse of the aligner tables;
* WER belongs on every row, or a bad MAE cannot be attributed.

They subclass an *aligner* base only because the scoring pipeline drives
`AlignerAdapter`; that is how they get scored at all. The semantics live in this
package and in `ignores_transcript`, not in the base class. See
`docs/methodology.md`.

Note a model can legitimately appear in BOTH families — CrisperWhisper ships
`transcribe` (here) and a native `forced_align` (in `fabench.aligners`), from
one package and one venv.
"""
from __future__ import annotations

from fabench.aligners.subprocess_aligner import SubprocessAligner


class SubprocessTimestampASR(SubprocessAligner):
    """Audio -> its own words, with times. Subclasses set model/worker."""

    source = "orthographic"
    emits_confidence = False
    granularity = ("word",)

    #: drops `transcript` from the job record — this is the defining difference
    ignores_transcript = True

    #: Native timestamp resolution (s) where the architecture bounds it; None if
    #: unknown. Recorded because it caps what a finer tolerance can measure.
    frame_s: float | None = None
