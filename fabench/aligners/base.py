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

"""Aligner adapter contract (Plan 3.2).

Each adapter maps ``(audio, transcript, optional gold phone sequence, mode)`` to
normalized word/phone intervals (schema 3.1), emitting a per-boundary confidence
where the system provides one. Two input modes:

* **Mode A (from text):** feed the word transcript; the aligner uses its own
  lexicon/G2P. Exercises recall/insertion.
* **Mode B (from gold phones):** feed the gold phone string; the aligner only
  places boundaries for a known 1:1 sequence — the cleanest boundary number.
  Adapters that cannot consume phones raise :class:`ModeUnsupported`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from fabench.schema import Interval


class ModeUnsupported(Exception):
    """Raised when an adapter cannot run a requested (mode, granularity)."""


class AlignerError(Exception):
    """Adapter failed on a specific item (logged; item marked failed, run continues)."""


@dataclass
class AlignerOutput:
    words: list[Interval] = field(default_factory=list)
    phones: list[Interval] = field(default_factory=list)
    #: per-item diagnostics an adapter wants to survive into hyp.jsonl.
    #: Added because crisperwhisper's duration guard reported how many words it
    #: dropped as out-of-audio, and that count was lost here -- the guard ran
    #: (the 11 bad utterances vanished, mean 223.9 -> 31.0 ms) but nothing in
    #: the artefact said so, only a line in the worker log. A correction the
    #: output does not record is a correction nobody can audit later.
    meta: dict = field(default_factory=dict)


@dataclass
class BatchItem:
    """One unit of work for a batch aligner."""

    item_id: str
    audio_path: str
    transcript: str
    speaker: str = "spk"
    phone_seq: list[str] | None = None
    mode: str = "A"


class AlignerAdapter(ABC):
    #: normalization source key (fabench.normalize.SOURCES) for this adapter's phones
    source: str = "arpabet"
    #: does the system emit a usable per-boundary confidence?
    emits_confidence: bool = False
    #: which granularities this adapter can produce
    granularity: tuple[str, ...] = ("word",)
    #: batch aligners (MFA, MAPS) amortize heavy startup over a whole corpus;
    #: the runner calls align_corpus() instead of per-item align().
    batch: bool = False

    def __init__(self, name: str, params: dict | None = None):
        self.name = name
        self.params = params or {}
        self._loaded = False

    def load(self) -> None:
        """Lazily load models/resources. Idempotent."""
        self._loaded = True

    @abstractmethod
    def align(
        self,
        audio_path: str,
        transcript: str,
        phone_seq: list[str] | None = None,
        mode: str = "A",
    ) -> AlignerOutput:
        ...

    def align_corpus(self, items: list[BatchItem]) -> dict[str, AlignerOutput]:
        """Batch alignment for batch aligners. Returns {item_id: output}; items
        that fail are simply absent from the dict."""
        raise NotImplementedError

    def supports(self, mode: str, granularity: str) -> bool:
        if granularity not in self.granularity:
            return False
        if mode == "B" and granularity == "phone":
            return "phone" in self.granularity
        return True


def clamp_intervals(ivs: list[Interval], duration_s: float) -> list[Interval]:
    """Clip any interval to [0, duration] (Plan S4 acceptance: no times outside
    the audio)."""
    out = []
    for iv in ivs:
        s = min(max(iv.start, 0.0), duration_s)
        e = min(max(iv.end, 0.0), duration_s)
        e = max(e, s)
        out.append(Interval(iv.label, s, e, iv.conf))
    return out
