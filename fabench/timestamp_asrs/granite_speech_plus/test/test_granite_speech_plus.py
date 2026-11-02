# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Granite Speech: registry, the worker's tag parser, and a real decode.

The parser is tested by loading the worker from its recipe directory, which
imports nothing heavy at module level. The smoke test decodes the
LJSpeech clip the aligner tests use, and skips until it is staged and
evals/timestamp_asrs/granite_speech_plus/download_and_install.sh has been run.
"""

import importlib.util
import os
from pathlib import Path

import pytest
import soundfile as sf

from fabench.aligners import get_adapter
from fabench.config import AlignerSpec

REC = Path(__file__).resolve().parents[4] / "evals" / "timestamp_asrs" / "granite_speech_plus"
LJ = Path(os.environ.get("FABENCH_TEST_LJ_WAV", "data/LJSpeech-1.1/wavs/LJ001-0002.wav"))
LJ_TEXT = "in being comparatively modern"
built = pytest.mark.skipif(not (REC / "venv" / "bin" / "python").exists(),
                           reason="Granite Speech Plus venv not built")


def _worker():
    spec = importlib.util.spec_from_file_location("granite_worker", REC / "worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _adapter(**params):
    return get_adapter(AlignerSpec(
        name="granite_speech_plus", adapter="granite_speech_plus", enabled=True, modes=["A"],
        granularity=["word"], emits_confidence=False,
        params={"venv": str(REC / "venv"), **params}))


def test_registered_as_a_timestamp_asr():
    a = _adapter()
    assert a.ignores_transcript and a.granularity == ("word",)
    assert a._extra_argv() == ["4"]
    assert _adapter(num_beams=1)._extra_argv() == ["1"]


def test_each_word_starts_where_the_token_before_it_ended():
    words = _worker()._parse("hello [T:45] _ [T:60] world [T:82]")
    assert words == [["hello", 0.0, 0.45], ["world", 0.60, 0.82]]


def test_a_tag_that_goes_backwards_is_a_ten_second_rollover():
    words = _worker()._parse("a [T:950] b [T:20] c [T:990] d [T:5]")
    assert [w[2] for w in words] == pytest.approx([9.5, 10.2, 19.9, 20.05])
    assert words[1][1] == pytest.approx(9.5)


def test_text_after_the_last_tag_has_no_time_and_is_dropped():
    assert _worker()._parse("go [T:30] forward") == [["go", 0.0, 0.30]]
    assert _worker()._parse("") == []


@built
@pytest.mark.skipif(not LJ.exists(), reason="LJSpeech sample not staged")
def test_decodes_the_words_in_order_inside_the_clip():
    out = _adapter(num_beams=1).align(str(LJ), "")
    assert [w.label for w in out.words] == LJ_TEXT.split()
    dur = sf.info(str(LJ)).duration
    starts = [w.start for w in out.words]
    assert starts == sorted(starts)
    assert all(0 <= w.start <= w.end <= dur + 0.05 for w in out.words)
