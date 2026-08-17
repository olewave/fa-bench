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

"""L2-ARCTIC ingestion (Plan 1.2) — OPTIONAL, open, off by default.

Only the **manual** annotation subset (``<spk>/annotation/*.TextGrid``, ~150
utts/speaker, hand-annotated ARPABET) is valid gold. The ``<spk>/textgrid/``
folder is MFA-forced and is refused (Plan 1.3).
"""

from __future__ import annotations

from pathlib import Path

from fabench.schema import Interval, Utterance

L2_SR = 16000


def _read_textgrid(path: Path):
    from praatio import textgrid

    tg = textgrid.openTextgrid(str(path), includeEmptyIntervals=True)
    tiers = {name.lower(): name for name in tg.tierNames}

    def entries(tier_key: str) -> list[Interval]:
        if tier_key not in tiers:
            return []
        tier = tg.getTier(tiers[tier_key])
        out = []
        for entry in tier.entries:
            start, end, label = float(entry[0]), float(entry[1]), str(entry[2])
            label = label.strip()
            if not label:
                label = "sil"
            # error-coded L2 labels look like "AH,AA,s" -> take produced phone
            label = label.split(",")[0].strip()
            out.append(Interval(label=label, start=start, end=end))
        return out

    return entries("phones"), entries("words")


def iter_utterances(root: Path, subset: str = "manual"):
    root = Path(root)
    tgs = sorted(root.rglob("annotation/*.TextGrid"))
    if not tgs:
        raise FileNotFoundError(
            f"No annotation/*.TextGrid under {root}. L2-ARCTIC manual gold lives "
            f"in <speaker>/annotation/ (the <speaker>/textgrid/ folder is "
            f"MFA-forced and not valid gold)."
        )
    for tg_path in tgs:
        if "textgrid" in tg_path.parent.name.lower() and tg_path.parent.name.lower() != "annotation":
            continue  # never ingest the forced-alignment folder
        spk = tg_path.parents[1].name
        sent = tg_path.stem
        phones, words = _read_textgrid(tg_path)
        for w in words:
            w.label = w.label.lower()
        wav = tg_path.parents[1] / "wav" / f"{sent}.wav"
        if wav.exists():
            from fabench.audio import read_audio

            try:
                x, sr = read_audio(wav)
                dur = len(x) / sr
            except Exception:
                dur = phones[-1].end if phones else 0.0
            audio_path = str(wav)
        else:
            dur = phones[-1].end if phones else 0.0
            audio_path = str(wav)
        yield Utterance(
            utt_id=f"l2arctic_{spk}_{sent}",
            source_corpus="l2arctic",
            register="read",
            speaker_id=spk,
            audio_path=audio_path,
            sample_rate=L2_SR,
            duration_s=dur,
            words=words,
            phones=phones,
        )
