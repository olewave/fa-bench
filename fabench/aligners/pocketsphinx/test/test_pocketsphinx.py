# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0


"""PocketSphinx adapter: registry, and real alignment through its own venv.

The audio is the "go forward ten meters" clip from PocketSphinx's own test
data, so the smoke tests need nothing but the tool's install. They skip until
evals/aligners/pocketsphinx/download_and_install.sh has been run.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from fabench.aligners import get_adapter
from fabench.config import AlignerSpec

REC = Path(__file__).resolve().parents[4] / "evals" / "aligners" / "pocketsphinx"
RAW = REC / "repo" / "pocketsphinx" / "test" / "data" / "goforward.raw"
built = pytest.mark.skipif(
    not (REC / "venv" / "bin" / "python").exists() or not RAW.exists(),
    reason="PocketSphinx venv not built")


def _adapter():
    return get_adapter(AlignerSpec(
        name="pocketsphinx", adapter="pocketsphinx", enabled=True, modes=["A"],
        granularity=["word", "phone"], emits_confidence=False,
        params={"venv": str(REC / "venv"), "model": "en-us"}))


@pytest.fixture
def clip(tmp_path):
    wav = tmp_path / "goforward.wav"
    sf.write(wav, np.fromfile(RAW, dtype="<i2"), 16000, subtype="PCM_16")
    return str(wav)


def test_registered():
    a = _adapter()
    assert a.source == "arpabet" and a.batch and not a.emits_confidence


@built
def test_words_and_phones_come_back_in_order_without_fillers(clip):
    out = _adapter().align(clip, "go forward ten meters")
    assert [w.label for w in out.words] == ["go", "forward", "ten", "meters"]
    starts = [w.start for w in out.words + out.phones]
    assert all(0 <= s for s in starts)
    assert [w.start for w in out.words] == sorted(w.start for w in out.words)
    # SIL and +NSN+ style fillers are dropped, and no variant suffix leaks
    assert out.phones and all(p.label.isalpha() for p in out.phones)
    assert not any("(" in w.label for w in out.words)


@built
def test_a_word_cmudict_lacks_is_aligned_through_g2p(clip):
    out = _adapter().align(clip, "go forwerd ten meters")
    assert [w.label for w in out.words] == ["go", "forwerd", "ten", "meters"]
    assert out.meta.get("n_g2p_words") == 1


@built
def test_an_unpronounceable_token_is_dropped_and_counted(clip):
    # A `?` gets no phones from g2p_en. Added to the dictionary empty, it
    # crashed the worker with a segfault on every Buckeye test cell.
    out = _adapter().align(clip, "go forward ? ten meters")
    assert [w.label for w in out.words] == ["go", "forward", "ten", "meters"]
    assert out.meta.get("n_unpronounceable") == 1
