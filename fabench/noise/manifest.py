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

"""Condition matrix + mix manifest (Plan 3.3 / S3).

For each (utterance x condition) we produce one :class:`MixItem` and one 16 kHz
WAV. Everything derives from ``(utt, noise_source, offset, scale, seed)`` so the
manifest and the audio are byte-reproducible (Plan gate #6).
"""

from __future__ import annotations

import hashlib
import pathlib
from pathlib import Path

from fabench.audio import load_resample, write_audio
from fabench.config import Config
from fabench.noise.mixer import mix_at_snr
from fabench.noise.provider import NoiseProvider
from fabench.schema import MixItem, Utterance

TARGET_SR = 16000


def _item_seed(mix_seed: int, item_id: str) -> int:
    h = hashlib.sha256(f"{mix_seed}::{item_id}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def _audio_key(audio_path) -> str:
    """Short, stable discriminator for the audio ROOT an utterance came from.

    Two runs over the same corpus at different shadow roots must not share a
    materialised-audio directory. Derived from the path above the corpus tree,
    so the clean corpus and each shadow root get their own.
    """
    import hashlib
    return "a" + hashlib.sha1(str(pathlib.Path(audio_path).parent)
                              .encode()).hexdigest()[:8]


def build_manifest(
    utts: list[Utterance],
    cfg: Config,
    provider: NoiseProvider,
    out_dir: Path,
    *,
    mix_method: str = "p56",
) -> list[MixItem]:
    conditions = cfg.conditions()
    mix_seed = int(cfg.seeds.get("mix", 0))
    out_dir = Path(out_dir)
    items: list[MixItem] = []

    for utt in utts:
        clean, sr = load_resample(utt.audio_path, TARGET_SR)
        n = len(clean)
        # Keyed by the AUDIO SOURCE, not just the utterance. A shadow-root run
        # is entirely the `clean` branch -- its audio is already degraded on
        # disk, so nothing is mixed in-process and every condition resolved to
        # one work/mix/<utt>/clean.wav. Four shadow roots wrote that single
        # path; two concurrent runs overwrote each other and both aligners
        # aligned whichever landed last, producing alignments identical in
        # every field but `rtf`.
        #
        # This is the same failure `_root_tag` fixed for the canonical cache and
        # the mix manifest. Both of those keyed the INDEX; the audio the index
        # points at was still shared, so the collision survived the fix. The
        # mixed branch below was always correct -- it writes <cond>.wav.
        udir = out_dir / _audio_key(utt.audio_path) / utt.utt_id
        clean_path = udir / "clean.wav"
        write_audio(clean_path, clean, sr)

        for cond in conditions:
            item_id = f"{utt.utt_id}__{cond.name}"
            seed = _item_seed(mix_seed, item_id)
            if cond.is_clean:
                items.append(
                    MixItem(
                        item_id=item_id,
                        utt_id=utt.utt_id,
                        condition="clean",
                        noise_type=None,
                        snr_db=None,
                        noise_source_file=None,
                        noise_offset_s=None,
                        noise_scale=None,
                        seed=seed,
                        mixed_audio_path=str(clean_path),
                    )
                )
                continue
            seg, src, off = provider.segment(cond.noise_type, n, seed)
            mixed, scale, _meta = mix_at_snr(clean, seg, cond.snr_db, sr, method=mix_method)
            mixed_path = udir / f"{cond.name}.wav"
            write_audio(mixed_path, mixed, sr)
            items.append(
                MixItem(
                    item_id=item_id,
                    utt_id=utt.utt_id,
                    condition=cond.name,
                    noise_type=cond.noise_type,
                    snr_db=cond.snr_db,
                    noise_source_file=src,
                    noise_offset_s=round(off, 6),
                    noise_scale=round(scale, 8),
                    seed=seed,
                    mixed_audio_path=str(mixed_path),
                )
            )
    return items
