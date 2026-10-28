# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""BFA adapter — real-audio smoke (skipped unless bournemouth_aligner installed)."""

import os
from pathlib import Path

import pytest

from fabench.aligners import get_adapter
from fabench.config import AlignerSpec

# Any staged LJSpeech clip works; the test self-skips when nothing is staged.
LJ = Path(os.environ.get("FABENCH_TEST_LJ_WAV", "data/LJSpeech-1.1/wavs/LJ001-0002.wav"))


def _spec():
    return AlignerSpec(
        name="bfa", adapter="bfa", enabled=True, modes=["A"],
        granularity=["word", "phone"], emits_confidence=True,
        params={"device": "cpu"},
    )


def test_bfa_registered():
    a = get_adapter(_spec())
    assert a.name == "bfa" and a.source == "ipa"


@pytest.mark.skipif(
    not LJ.exists(), reason="LJSpeech sample not staged"
)
def test_bfa_real_audio():
    pytest.importorskip("bournemouth_aligner")
    a = get_adapter(_spec())
    out = a.align(str(LJ), "in being comparatively modern", mode="A")
    # phone-level with onset/offset + confidence, IPA labels
    assert len(out.phones) >= 8
    assert len(out.words) >= 3
    for p in out.phones:
        assert 0 <= p.start <= p.end
        assert p.conf is not None
