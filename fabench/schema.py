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

"""Canonical data schemas (Plan Section 3).

Two record types flow through the whole benchmark:

* :class:`Utterance` — one gold *or* hypothesis alignment (Plan 3.1). Times are
  floats in **seconds**. ``conf`` is ``None`` for gold and populated by aligner
  adapters where the system emits a per-boundary confidence.
* :class:`MixItem` — one row of the condition/mix manifest (Plan 3.3). Fully
  reproducible from ``(utt, noise_source, offset, scale, seed)``.

Everything is plain dataclasses with explicit ``to_dict`` / ``from_dict`` so the
on-disk form is stable JSON (leaderboards must be diffable and deterministic).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Default tolerance for boundary bookkeeping (seconds). One sample at 16 kHz is
# 62.5 us; 1e-4 s (0.1 ms) comfortably absorbs float round-trips without hiding
# real gaps/overlaps.
EPS_S = 1e-4

# Duration-reconstruction tolerance (Plan S1 acceptance: match audio ±20 ms).
DURATION_TOL_S = 0.020


@dataclass
class Interval:
    """A single labelled segment: ``[start, end)`` in seconds."""

    label: str
    start: float
    end: float
    conf: float | None = None

    def __post_init__(self) -> None:
        self.start = float(self.start)
        self.end = float(self.end)
        if self.conf is not None:
            self.conf = float(self.conf)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        d = {"label": self.label, "start": self.start, "end": self.end}
        # Always emit conf (even null) for phones so gold/hyp files are same shape.
        d["conf"] = self.conf
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Interval:
        return cls(
            label=d["label"],
            start=d["start"],
            end=d["end"],
            conf=d.get("conf"),
        )


@dataclass
class Utterance:
    """One utterance's alignment (Plan 3.1)."""

    utt_id: str
    source_corpus: str
    register: str  # "read" | "spontaneous" | ...
    speaker_id: str
    audio_path: str
    sample_rate: int
    duration_s: float
    words: list[Interval] = field(default_factory=list)
    phones: list[Interval] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "utt_id": self.utt_id,
            "source_corpus": self.source_corpus,
            "register": self.register,
            "speaker_id": self.speaker_id,
            "audio_path": self.audio_path,
            "sample_rate": self.sample_rate,
            "duration_s": self.duration_s,
            "words": [w.to_dict() for w in self.words],
            "phones": [p.to_dict() for p in self.phones],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Utterance:
        return cls(
            utt_id=d["utt_id"],
            source_corpus=d["source_corpus"],
            register=d["register"],
            speaker_id=d["speaker_id"],
            audio_path=d["audio_path"],
            sample_rate=int(d["sample_rate"]),
            duration_s=float(d["duration_s"]),
            words=[Interval.from_dict(x) for x in d.get("words", [])],
            phones=[Interval.from_dict(x) for x in d.get("phones", [])],
        )

    # -- boundaries -------------------------------------------------------
    def phone_boundaries(self) -> list[float]:
        """Onset+offset boundary times for phones, in order (with duplicates at
        shared edges collapsed only if exactly equal)."""
        return _boundaries(self.phones)

    def word_boundaries(self) -> list[float]:
        return _boundaries(self.words)


def _boundaries(intervals: list[Interval]) -> list[float]:
    bs: list[float] = []
    for iv in intervals:
        bs.append(iv.start)
        bs.append(iv.end)
    return bs


@dataclass
class MixItem:
    """One eval item = one utterance under one channel condition (Plan 3.3).

    For the ``clean`` condition the noise fields are ``None`` and
    ``mixed_audio_path`` points at the (resampled) clean audio.
    """

    item_id: str
    utt_id: str
    condition: str  # "clean" | "<noise_type>_snr<snr>"
    noise_type: str | None  # None for clean
    snr_db: float | None  # None for clean
    noise_source_file: str | None
    noise_offset_s: float | None
    noise_scale: float | None
    seed: int
    mixed_audio_path: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MixItem:
        return cls(
            item_id=d["item_id"],
            utt_id=d["utt_id"],
            condition=d["condition"],
            noise_type=d.get("noise_type"),
            snr_db=d.get("snr_db"),
            noise_source_file=d.get("noise_source_file"),
            noise_offset_s=d.get("noise_offset_s"),
            noise_scale=d.get("noise_scale"),
            seed=int(d["seed"]),
            mixed_audio_path=d["mixed_audio_path"],
        )


# --------------------------------------------------------------------------
# Validation (Plan S1 acceptance / sanity gate #2 prerequisites)
# --------------------------------------------------------------------------
@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_bad(self, context: str = "") -> None:
        if not self.ok:
            prefix = f"[{context}] " if context else ""
            raise ValueError(prefix + "; ".join(self.errors))


def validate_intervals(
    intervals: list[Interval],
    duration_s: float,
    *,
    eps: float = EPS_S,
    require_no_gaps: bool = False,
    overlap_is_error: bool = True,
    label: str = "intervals",
) -> ValidationReport:
    """Structural checks on one interval list.

    Always checked: ``0 <= start < end <= duration + eps``. Gaps are only
    forbidden when ``require_no_gaps`` (e.g. TIMIT phones, which tile the whole
    signal). Overlaps are errors by default, but TIMIT *word* boundaries
    legitimately overlap at co-articulated junctions (e.g. "carry an"), so word
    overlaps are downgraded to warnings via ``overlap_is_error=False``.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not intervals:
        warnings.append(f"{label}: empty")
        return ValidationReport(ok=True, warnings=warnings)

    prev_end: float | None = None
    for i, iv in enumerate(intervals):
        if iv.start < -eps:
            errors.append(f"{label}[{i}] start<0 ({iv.start:.6f})")
        if iv.end > duration_s + eps:
            errors.append(
                f"{label}[{i}] end>{duration_s:.6f} ({iv.end:.6f})"
            )
        if iv.end <= iv.start - eps:
            errors.append(
                f"{label}[{i}] non-positive dur ({iv.start:.6f}..{iv.end:.6f})"
            )
        elif iv.end < iv.start:
            errors.append(f"{label}[{i}] end<start")
        if prev_end is not None:
            if iv.start < prev_end - eps:
                msg = f"{label}[{i}] overlaps prev ({iv.start:.6f}<{prev_end:.6f})"
                (errors if overlap_is_error else warnings).append(msg)
            elif require_no_gaps and iv.start > prev_end + eps:
                errors.append(
                    f"{label}[{i}] gap after prev ({prev_end:.6f}->{iv.start:.6f})"
                )
        prev_end = iv.end

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


def validate_utterance(
    utt: Utterance,
    *,
    duration_tol_s: float = DURATION_TOL_S,
    require_phone_no_gaps: bool = False,
) -> ValidationReport:
    """Full structural validation of a gold/hyp utterance (Plan S1)."""
    errors: list[str] = []
    warnings: list[str] = []

    if utt.duration_s <= 0:
        errors.append(f"duration_s must be >0 (got {utt.duration_s})")

    for name, ivs, no_gaps in (
        ("words", utt.words, False),
        ("phones", utt.phones, require_phone_no_gaps),
    ):
        rep = validate_intervals(
            ivs, utt.duration_s, require_no_gaps=no_gaps,
            overlap_is_error=(name == "phones"),  # TIMIT words overlap legitimately
            label=name,
        )
        errors.extend(rep.errors)
        warnings.extend(rep.warnings)

    # Reconstruct span from phone intervals; must match declared duration ±tol.
    if utt.phones:
        span = utt.phones[-1].end - utt.phones[0].start
        # phones typically tile [0, duration]; compare the covered extent's end.
        covered_end = max(p.end for p in utt.phones)
        if abs(covered_end - utt.duration_s) > duration_tol_s:
            warnings.append(
                f"phone coverage end {covered_end:.4f}s vs duration "
                f"{utt.duration_s:.4f}s exceeds ±{duration_tol_s*1000:.0f}ms"
            )
        del span

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)


# --------------------------------------------------------------------------
# JSON / JSONL IO
# --------------------------------------------------------------------------
def dump_utterance(utt: Utterance, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(utt.to_dict(), f, indent=2, sort_keys=True)


def load_utterance(path: str | Path) -> Utterance:
    with open(path) as f:
        return Utterance.from_dict(json.load(f))


def dump_jsonl(records: Iterable, path: str | Path) -> None:
    """Write dataclass records (with ``to_dict``) as one JSON object per line,
    keys sorted so output is byte-deterministic (Plan gate #6)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written to a sibling and renamed, never truncated in place. A reader --
    # rescore_all.sh, a gate, the noisy-vs-clean check -- can run while a sweep
    # is writing, and open(path, "w") gives it a file that is empty, then
    # half-written, then correct. os.replace is atomic within a directory, so a
    # reader sees either the previous alignment or the new one and never a
    # prefix of one.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w") as f:
            for rec in records:
                d = rec.to_dict() if hasattr(rec, "to_dict") else rec
                f.write(json.dumps(d, sort_keys=True) + "\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
