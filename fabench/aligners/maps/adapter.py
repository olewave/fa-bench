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

"""MAPS — Mason-Alberta Phonetic Segmentor (Kelley et al. 2024, arXiv:2310.15425).

Neural (DNN + interpolation) aligner shipped as a TensorFlow CLI needing its own
Python 3.11 env. This is a **batch** adapter: it lays out audio/ + text/ dirs and
a per-run pronunciation dictionary (generated from the corpus vocab via g2p_en),
runs `python maps.py` in the MAPS env, and parses the emitted TextGrids
(ARPABET+stress phones -> canonical via the `arpabet` source).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from fabench.aligners.base import (
    AlignerAdapter,
    AlignerError,
    AlignerOutput,
    BatchItem,
    clamp_intervals,
)
from fabench.schema import Interval

# Machine-specific; override via env or params (repo_path/python).
_DEFAULT_REPO = os.environ.get("FABENCH_MAPS_REPO", "tools/MAPS")
_DEFAULT_PY = os.environ.get("FABENCH_MAPS_PYTHON", "tools/maps_env/bin/python")


class MAPS(AlignerAdapter):
    source = "arpabet"  # ARPABET + stress
    emits_confidence = False  # basic CLI TextGrid has no per-phone confidence
    granularity = ("word", "phone")
    batch = True

    def load(self) -> None:
        if self._loaded:
            return
        self.repo = Path(self.params.get("repo_path", _DEFAULT_REPO))
        self.python = self.params.get("python", _DEFAULT_PY)
        self.model = self.params.get("model", str(self.repo / "timbuck_eng.tf"))
        if not self.repo.exists() or not Path(self.python).exists():
            raise AlignerError(
                "MAPS unavailable. Clone github.com/MasonPhonLab/MAPS, create a "
                "Python 3.11 env with its requirements (tensorflow==2.12.1), and "
                "set aligners.maps.params.repo_path / python."
            )
        try:
            from g2p_en import G2p

            self._g2p = G2p()
        except Exception as e:  # pragma: no cover
            raise AlignerError(f"MAPS needs g2p_en for the dictionary. ({e})") from e
        self._loaded = True

    def _unpronounceable(self, transcripts) -> set[str]:
        """Tokens g2p_en cannot pronounce, which MAPS cannot represent at all.

        MAPS requires every transcript word to have a dictionary entry AND a
        real pronunciation. Buckeye's test split contains a single `?` token
        and there is no way to give it one:

          omit it from the dict  -> "words were not found in the dictionary",
                                    the WHOLE cell is refused
          map it to SPN          -> KeyError('spn'); not in MAPS's phone set
                                    (AA AH AO B D ER G HH IH K L M N NG P S
                                     SIL T UW ...)
          map it to SIL          -> IndexError in MAPS's make_word_tier

        So the token is removed from the transcript instead. That word then has
        no hypothesis and scores as a DELETION, which is honest -- the aligner
        genuinely cannot place it -- and the other 4,512 utterances in the cell
        become scoreable rather than all 4,513 being lost.
        """
        bad = set()
        for w in sorted({w for t in transcripts for w in t.split()}):
            if not [p for p in self._g2p(w) if p and p[0].isalpha()]:
                bad.add(w)
        return bad

    def _write_dict(self, transcripts, path: Path) -> None:
        vocab = sorted({w for t in transcripts for w in t.split()})
        with open(path, "w") as f:
            for w in vocab:
                phones = [p for p in self._g2p(w) if p and p[0].isalpha()]
                if phones:
                    f.write(f"{w.upper()}  {' '.join(phones)}\n")

    def align_corpus(self, items: list[BatchItem]) -> dict[str, AlignerOutput]:
        self.load()
        import soundfile as sf

        from fabench.audio import load_resample

        results: dict[str, AlignerOutput] = {}
        with tempfile.TemporaryDirectory(dir=self.params.get("tmp_dir")) as td:
            td = Path(td)
            adir, tdir = td / "audio", td / "text"
            adir.mkdir()
            tdir.mkdir()
            idx2item: dict[str, tuple[str, float]] = {}
            # Computed BEFORE the write loop, which consumes it.
            self._drop_tokens = self._unpronounceable(
                [it.transcript or "" for it in items])
            if self._drop_tokens:
                print(f"  [maps] dropping {len(self._drop_tokens)} unpronounceable "
                      f"token(s) {sorted(self._drop_tokens)!r} -- MAPS cannot "
                      f"represent them and would refuse the entire cell")
            for i, it in enumerate(items):
                name = f"u{i:06d}"
                x, sr = load_resample(it.audio_path, 16000)
                sf.write(str(adir / f"{name}.wav"), x, sr, subtype="PCM_16")
                # Strip tokens MAPS cannot represent; see _unpronounceable.
                txt = " ".join(w for w in (it.transcript or "").split()
                               if w not in self._drop_tokens)
                (tdir / f"{name}.txt").write_text(txt)
                idx2item[name] = (it.item_id, len(x) / sr)
            dpath = td / "dict.txt"
            self._write_dict(
                [" ".join(w for w in (it.transcript or "").split()
                          if w not in self._drop_tokens) for it in items], dpath)

            cmd = [
                self.python, "maps.py",
                "--audio", str(adir), "--text", str(tdir),
                "--model", self.model, "--dict", str(dpath),
                "--quiet", "--overwrite", "--sil", "true",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.repo),
                                   timeout=self.params.get("timeout", 7200), check=False)
            except subprocess.TimeoutExpired as e:
                raise AlignerError(f"MAPS timed out: {e}") from e
            if r.returncode != 0:
                raise AlignerError(f"MAPS failed (rc={r.returncode}): {r.stderr[-500:]}")

            for tg in adir.glob("*.TextGrid"):
                if tg.stem in idx2item:
                    item_id, dur = idx2item[tg.stem]
                    results[item_id] = self._parse_tg(tg, dur)
        return results

    def align(self, audio_path, transcript, phone_seq=None, mode="A") -> AlignerOutput:
        out = self.align_corpus([BatchItem("single", audio_path, transcript)])
        return out.get("single", AlignerOutput())

    def _parse_tg(self, tg_path: Path, dur: float) -> AlignerOutput:
        from praatio import textgrid

        tg = textgrid.openTextgrid(str(tg_path), includeEmptyIntervals=True)
        names = {n.lower(): n for n in tg.tierNames}

        def read(tier):
            if tier not in names:
                return []
            return [
                Interval(str(e[2]).strip(), float(e[0]), float(e[1]))
                for e in tg.getTier(names[tier]).entries
                if str(e[2]).strip()
            ]

        words = read("words")
        for w in words:
            w.label = w.label.lower()
        return AlignerOutput(
            words=clamp_intervals(words, dur), phones=clamp_intervals(read("phones"), dur)
        )
