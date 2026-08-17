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
