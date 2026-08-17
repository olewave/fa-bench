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

"""ASR adapter contract — the counterpart to ``fabench.aligners``.

**The distinction is the INPUT, not the model family.**

* ``fabench.aligners`` — given audio **and a transcript**, say where those words
  are. The word sequence is fixed; only timing can be wrong.
* ``fabench.timestamp_asrs`` (here) — given audio **only**, say what was said, and
  optionally when. Both the words and the timing can be wrong.

That is why WhisperX lives in ``aligners`` while CrisperWhisper belongs here:
WhisperX is handed the reference transcript and runs only its wav2vec2 aligner,
whereas CrisperWhisper decodes its own transcript. Putting the latter in an
aligner table conflates recognition error with timing error — see
``evals/README.md``.

Two roles, distinguished by ``emits_timestamps`` rather than by directory:

* **transcript source** (``emits_timestamps = False`` is still useful): decode
  once, cache, feed the text to every forced aligner so aligner-vs-aligner stays
  a controlled comparison.
* **timestamped ASR** (``emits_timestamps = True``): also returns word
  intervals, so it can be scored directly against gold boundaries.

Design notes for whoever populates this:

* A timestamped ASR's word intervals are NOT comparable to an aligner's without
  saying so. Its recall carries recognition error, so a boundary-level metric
  (B-F1, label-agnostic) is the honest primary and MAE the secondary. See
  ``docs/methodology.md``.
* Report WER on every row. Without it a poor MAE is unattributable — recognition
  failure and timing failure look identical.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from fabench.schema import Interval


class ASRError(Exception):
    """Adapter failed on a specific item (logged; item marked failed, run continues)."""


@dataclass
class ASROutput:
    """One utterance's recognition result.

    ``words`` is populated only by adapters with ``emits_timestamps = True``;
    a pure transcript source leaves it None and contributes ``text`` alone.
    """

    text: str
    words: list[Interval] | None = None
    meta: dict = field(default_factory=dict)


class ASRAdapter(ABC):
    #: True if the adapter returns word intervals, not just text.
    emits_timestamps: bool = False
    #: Native timestamp resolution in seconds, when the architecture bounds it
    #: (e.g. Whisper's encoder is 50 fps => 0.020). None if not applicable or
    #: unknown. Recorded because it caps what any tolerance below it can show.
    frame_s: float | None = None

    def __init__(self, name: str, params: dict | None = None) -> None:
        self.name = name
        self.params = params or {}
        self._loaded = False

    def load(self) -> None:
        """Load models. Called lazily; must be idempotent."""
        self._loaded = True

    @abstractmethod
    def transcribe(self, audio_path: str) -> ASROutput:
        """Audio -> text (+ word intervals when ``emits_timestamps``)."""
        raise NotImplementedError
