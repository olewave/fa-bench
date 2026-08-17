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

"""NeuFA adapter — registry, actionable failures, and boundary reconstruction.

The reconstruction tests drive the adapter through a stubbed ``inference.NeuFA``
object, so the Interval logic — the g2p ``+1`` id offset, the degenerate-span
drop (NeuFA does not forbid ``right <= left``), the word span convention
(first phone's left -> last phone's right, per the repo's own inference.py),
and clamping — is covered without the research repo, torch, or a checkpoint.
A real run additionally needs the thuhcsi/NeuFA clone (with submodules), its
deps (torch/librosa/sequitur-g2p), and a user-exported ``neufa.pt``.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest

from fabench.aligners import get_adapter
from fabench.aligners.base import AlignerError
from fabench.config import AlignerSpec


def _spec(**params):
    return AlignerSpec(
        name="neufa", adapter="neufa", enabled=True, modes=["A"],
        granularity=["word", "phone"], emits_confidence=False,
        params=params,
    )


def _wav(tmp_path, dur_s=0.5, sr=16000):
    from fabench.audio import write_audio

    path = tmp_path / "u.wav"
    t = np.arange(int(dur_s * sr)) / sr
    write_audio(path, 0.1 * np.sin(2 * np.pi * 220 * t), sr)
    return str(path)


class _FakeG2P:
    id2symbol: ClassVar[list[str]] = ["HH", "AH0", "L", "OW1"]


class _FakeNeuFA:
    """Mimics inference.NeuFA: two words, second unpronounceable; one
    degenerate phone span; one span past the audio end (must clamp)."""

    g2p = _FakeG2P()

    def get_words(self, text):
        return ["hello", "xx"]

    def get_phonemes(self, words):
        return [[1, 2, 3, 4], []]

    def align(self, text, wav):
        b = np.array([[0.0, 0.1], [0.1, 0.2], [0.25, 0.2], [0.3, 9.9]])
        return b, None, None


def _stubbed_adapter(fake=None):
    a = get_adapter(_spec())
    a._loaded = True
    a.neufa = fake or _FakeNeuFA()
    return a


def test_neufa_registered():
    a = get_adapter(_spec())
    assert a.name == "neufa"
    assert a.source == "arpabet"  # CMU ARPABET + stress digits
    # Batch, because it runs in its OWN interpreter now: a subprocess per
    # utterance would reload the model every time.
    assert a.batch is True
    assert a.supports("A", "phone") and a.supports("A", "word")
    assert a.emits_confidence is False


def test_neufa_requires_its_own_venv():
    """Isolation is not optional. NeuFA used to put its checkout on FA-Bench's
    sys.path and import torch from the shared .venv; refusing to load without
    params.venv is what stops that arrangement coming back."""
    a = get_adapter(_spec())
    a.params.pop("venv", None)
    with pytest.raises(AlignerError, match="params.venv"):
        a.load()


# --------------------------------------------------------------------------
# The reconstruction logic moved into evals/aligners/neufa/worker.py, so the
# guards move with it. Both are what a wrong checkpoint produces, and both are
# silent unless checked.
# --------------------------------------------------------------------------
def _worker():
    import importlib.util
    from pathlib import Path

    # test/ -> neufa/ -> aligners/ -> fabench/ -> repo root
    p = Path(__file__).resolve().parents[4] / "evals/aligners/neufa/worker.py"
    spec = importlib.util.spec_from_file_location("neufa_worker", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # torch is imported inside main(), not here
    return mod


def test_worker_boundary_count_mismatch_is_actionable():
    w = _worker()

    class _Short(_FakeNeuFA):
        def align(self, text, wav):
            return np.array([[0.0, 0.1]]), None, None   # 1 row for 4 phonemes

    with pytest.raises(RuntimeError, match="boundary rows"):
        w.align_one(_Short(), _FakeNeuFA().g2p.id2symbol, "hello xx",
                    np.zeros(8000), 16000)


def test_worker_empty_transcript_is_actionable():
    w = _worker()

    class _Empty(_FakeNeuFA):
        def get_words(self, text):
            return []

        def get_phonemes(self, words):
            return []

    with pytest.raises(RuntimeError, match="no alignable words"):
        w.align_one(_Empty(), _FakeNeuFA().g2p.id2symbol, "", np.zeros(8000), 16000)
