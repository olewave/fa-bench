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

"""S4 aligner adapters: contract, registry, gated deps, real-audio smoke."""

import os
from pathlib import Path

import pytest

from fabench.aligners import get_adapter
from fabench.aligners.base import AlignerError, clamp_intervals
from fabench.config import AlignerSpec
from fabench.schema import Interval

# Any staged LJSpeech clip works; the test self-skips when nothing is staged.
LJ = Path(os.environ.get("FABENCH_TEST_LJ_WAV", "data/LJSpeech-1.1/wavs/LJ001-0002.wav"))
LJ_TEXT = "in being comparatively modern"


def _spec(name, adapter, **kw):
    return AlignerSpec(name=name, adapter=adapter, enabled=True,
                       modes=kw.get("modes", ["A"]),
                       granularity=kw.get("granularity", ["word"]),
                       emits_confidence=kw.get("conf", False),
                       params=kw.get("params", {}))


def test_clamp_intervals():
    ivs = [Interval("a", -0.1, 0.5), Interval("b", 0.5, 2.0)]
    out = clamp_intervals(ivs, duration_s=1.0)
    assert out[0].start == 0.0 and out[1].end == 1.0


def test_registry_resolves_all_four():
    for adapter in ("torchaudio_fa", "charsiu", "whisperx", "mfa"):
        a = get_adapter(_spec(adapter, adapter))
        assert a.name == adapter


def test_supports_mode_granularity():
    ta = get_adapter(_spec("torchaudio_fa", "torchaudio_fa", granularity=["word", "phone"]))
    assert ta.supports("A", "word")
    wx = get_adapter(_spec("whisperx", "whisperx", granularity=["word"]))
    assert wx.supports("A", "word")
    assert not wx.supports("B", "phone")  # word-only


@pytest.mark.parametrize("adapter", ["whisperx"])
def test_gated_adapters_fail_with_actionable_error(adapter):
    # deps absent in a clean env -> actionable AlignerError on load.
    a = get_adapter(_spec(adapter, adapter))
    with pytest.raises(AlignerError) as e:
        a.load()
    msg = str(e.value).lower()
    assert any(k in msg for k in ("install", "pip", "conda", "path", "clone", "wired"))


def test_mfa_is_batch_aligner():
    a = get_adapter(_spec("mfa", "mfa"))
    assert a.batch is True and a.source == "mfa"


def test_mfa_version_selects_env():
    """`version` is an optional knob picking the MFA build's conda env; `env`
    overrides it, and version_envs remaps it. (env is resolved before load()'s
    micromamba-existence check, so this holds even where MFA isn't installed.)"""
    from fabench.aligners.mfa import MFA

    def env_of(params):
        a = MFA("m", params)
        try:
            a.load()
        except AlignerError:
            pass
        return a.env

    assert env_of({}) == "mfa"                                  # default 3.4 -> mfa
    assert env_of({"version": "3.0"}) == "mfa30"                # 3.0 -> mfa30
    assert env_of({"version": "3.0", "env": "custom"}) == "custom"          # env wins
    assert env_of({"version": "3.0", "version_envs": {"3.0": "x"}}) == "x"  # remap


def test_mfa_finds_the_micromamba_its_recipe_installs(tmp_path, monkeypatch):
    """download_and_install.sh puts micromamba at <mamba_root>/bin/micromamba.
    That copy must be found with nothing else set; an explicit param or
    $FABENCH_MICROMAMBA still wins when it exists."""
    from fabench.aligners.mfa.adapter import find_micromamba

    monkeypatch.delenv("FABENCH_MICROMAMBA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root = tmp_path / "mamba"
    (root / "bin").mkdir(parents=True)
    recipe_mm = root / "bin" / "micromamba"
    recipe_mm.write_text("")
    assert find_micromamba({}, str(root)) == str(recipe_mm)

    env_mm = tmp_path / "env_mm"
    env_mm.write_text("")
    monkeypatch.setenv("FABENCH_MICROMAMBA", str(env_mm))
    assert find_micromamba({}, str(root)) == str(env_mm)

    param_mm = tmp_path / "param_mm"
    param_mm.write_text("")
    assert find_micromamba({"micromamba": str(param_mm)}, str(root)) == str(param_mm)

    # a named path that does not exist falls through to one that does
    assert find_micromamba({"micromamba": str(tmp_path / "nope")}, str(root)) == str(env_mm)


def test_charsiu_bfa_registered():
    for adapter, src in (("charsiu", "arpabet"), ("bfa", "ipa")):
        a = get_adapter(_spec(adapter, adapter))
        assert a.source == src


@pytest.mark.skipif(not LJ.exists(), reason="LJSpeech sample not staged")
def test_torchaudio_real_audio_smoke():
    torch = pytest.importorskip("torch")
    from fabench.aligners.torchaudio_fa import TorchaudioFA
    from fabench.audio import read_audio

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    a = TorchaudioFA("torchaudio_fa", {"device": dev})
    out = a.align(str(LJ), LJ_TEXT, mode="A")
    x, sr = read_audio(LJ)
    dur = len(x) / sr
    assert len(out.words) >= 3
    # schema-valid: in-bounds, ordered, has confidence
    for i, w in enumerate(out.words):
        assert 0.0 <= w.start <= w.end <= dur + 1e-3
        assert w.conf is not None
        if i:
            assert out.words[i - 1].start <= w.start


def test_one_step_recognizer_words_are_saved_as_written():
    """A forced aligner's words go back onto the tokens it was handed; a
    one-step recognizer was handed none, so it keeps its own spelling (issue 21:
    an API's `boats` used to be saved as the reference's `boat's`)."""
    from fabench.aligners.runner import _words_to_save
    words = [Interval("boats", 0.0, 0.4), Interval("can", 0.4, 0.6), Interval("not", 0.6, 0.8)]
    given = ["boat's", "cannot"]

    def saved(name, **params):
        spec = AlignerSpec(name=name, adapter="x", enabled=True, modes=["A"],
                           granularity=["word"], emits_confidence=False, params=params)
        return [w["label"] for w in _words_to_save(spec, given, words)]

    assert saved("deepgram") == ["boats", "can", "not"]           # one-step ASR
    assert saved("mfa") == ["boat's", "cannot"]                   # forced aligner
    assert saved("olign_on_chirp2", transcript_hyp="x") == ["boat's", "cannot"]  # cascade
