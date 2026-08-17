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
