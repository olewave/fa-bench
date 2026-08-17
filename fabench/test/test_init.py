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

"""`fabench init` — sets a machine up, and refuses to guess.

The one irreducible setup step is saying where the licensed corpora are, so
init's job is to find them, *verify* what it found, and record the answer in
`.fabench.env` — the only file it writes, because everything a RUN is already
composes from the tree that owns it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytest

from fabench.config import load_config
from fabench.envfile import parse_env_file
from fabench.init import cmd_init, find_corpus, gpu_answer_to_devices, known_corpora, looks_staged

REPO = Path(__file__).resolve().parents[2]   # fabench/test/ -> repo root


def _args(**kw):
    return argparse.Namespace(
        root=kw.get("root"), search=kw.get("search"),
        non_interactive=kw.get("non_interactive", False),
    )


def _stage(tmp_path):
    """A fake staged tree: enough structure to match each corpus's markers."""
    (tmp_path / "d/TIMIT/TRAIN").mkdir(parents=True)
    (tmp_path / "d/TIMIT/TEST").mkdir()
    (tmp_path / "d/Buckeye/s01").mkdir(parents=True)
    (tmp_path / "d/Buckeye/s01/s0101a.phones").touch()
    return tmp_path / "d"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """A throwaway .fabench.env, and no machine settings leaking either way.

    init writes through $FABENCH_ENV_FILE, the same handle the CLI and
    evals/env.sh resolve, so pointing it at tmp_path both isolates the test and
    exercises the real path.

    os.environ is snapshotted rather than left to monkeypatch: load_env_file()
    writes to it directly, which monkeypatch cannot know about and therefore
    cannot undo -- a leaked FABENCH_TIMIT_ROOT failed an unrelated config test
    two files away.
    """
    saved = dict(os.environ)
    for var in ("FABENCH_TIMIT_ROOT", "FABENCH_BUCKEYE_ROOT", "FABENCH_CUDA_DEVICES"):
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / "machine.env"
    monkeypatch.setenv("FABENCH_ENV_FILE", str(env))
    monkeypatch.setattr("fabench.init.detect_gpus", lambda: 4)
    yield env
    os.environ.clear()
    os.environ.update(saved)


def _tty(monkeypatch, answers):
    """Pretend to be a terminal and feed canned answers to input()."""
    it = iter(answers)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# --------------------------------------------------------------------------
# Finding, and verifying what was found
# --------------------------------------------------------------------------
def test_markers_come_from_each_dataset_folder():
    corpora = known_corpora(REPO)
    assert {"timit", "buckeye"} <= set(corpora)
    # Markers live with the corpus, so a new dataset teaches init about itself.
    assert corpora["timit"] and corpora["buckeye"]


def test_looks_staged_verifies_rather_than_guesses(tmp_path):
    data = _stage(tmp_path)
    markers = known_corpora(REPO)
    assert looks_staged(data / "TIMIT", markers["timit"])
    assert looks_staged(data / "Buckeye", markers["buckeye"])
    # An empty directory named right is still not a staged corpus.
    (tmp_path / "empty/TIMIT").mkdir(parents=True)
    assert not looks_staged(tmp_path / "empty/TIMIT", markers["timit"])
    assert find_corpus("timit", markers["timit"], [str(tmp_path / "empty")]) is None


# --------------------------------------------------------------------------
# What it writes: one file, and a run that resolves from it
# --------------------------------------------------------------------------
def test_writes_roots_to_the_machine_file(tmp_path, _isolate):
    data = _stage(tmp_path)
    assert cmd_init(_args(search=[str(data)])) == 0

    got = parse_env_file(_isolate)
    assert got["FABENCH_TIMIT_ROOT"] == str(data / "TIMIT")
    assert got["FABENCH_BUCKEYE_ROOT"] == str(data / "Buckeye")
    # Started from the tracked template, so each setting keeps its explanation
    # rather than landing in a bare two-line file.
    assert "BLAS/OMP threads" in _isolate.read_text()


def test_the_composed_run_picks_those_roots_up(tmp_path, monkeypatch, _isolate):
    """The point of writing the file is that `fabench run` needs no config: the
    roots must reach load_config through the environment, and the corpora and
    systems must come from the tree."""
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))

    from fabench.envfile import load_env_file
    load_env_file(_isolate.parent)

    cfg = load_config(None)
    assert cfg.datasets["gold"]["timit"]["root"] == str(data / "TIMIT")
    assert cfg.datasets["gold"]["buckeye"]["root"] == str(data / "Buckeye")
    assert [a.name for a in cfg.aligners(enabled_only=True)] == ["torchaudio_fa"]


def test_writes_no_run_config_anywhere(tmp_path, monkeypatch, _isolate):
    """There is no configs/local.yaml any more, and init must not resurrect one:
    a file picked up because of where it sits makes a command mean different
    things in different checkouts."""
    data = _stage(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(_args(search=[str(data)]))
    assert not list(tmp_path.glob("**/*.yaml"))


def test_unfound_corpus_is_left_unset_not_invented(tmp_path, _isolate):
    """A corpus that cannot be located gets no root at all — never a
    plausible-looking guess, which would fail later and further from the
    cause. The run then skips it with acquisition instructions."""
    assert cmd_init(_args(search=[str(tmp_path / "nothing")])) == 0
    got = parse_env_file(_isolate) if _isolate.is_file() else {}
    assert "FABENCH_TIMIT_ROOT" not in got
    assert "FABENCH_BUCKEYE_ROOT" not in got


def test_rerun_keeps_a_root_it_can_no_longer_find(tmp_path, _isolate):
    """A corpus on an unmounted disk must not be silently un-configured: the
    re-run that cannot see it would otherwise erase a setting that is right."""
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))

    import shutil
    shutil.rmtree(data / "TIMIT")
    assert cmd_init(_args(search=[str(data)])) == 0
    assert parse_env_file(_isolate)["FABENCH_TIMIT_ROOT"] == str(data / "TIMIT")


def test_rerun_leaves_unrelated_settings_alone(tmp_path, _isolate):
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))
    _isolate.write_text(_isolate.read_text() + "FABENCH_THREADS=8\nFABENCH_MAPS_REPO=/my/MAPS\n")

    assert cmd_init(_args(search=[str(data)])) == 0
    got = parse_env_file(_isolate)
    assert got["FABENCH_THREADS"] == "8"
    assert got["FABENCH_MAPS_REPO"] == "/my/MAPS"


def test_explicit_root_beats_the_search(tmp_path, _isolate):
    data = _stage(tmp_path)
    assert cmd_init(_args(search=[str(data)],
                          root=[f"timit={tmp_path}/elsewhere/TIMIT"])) == 0
    assert parse_env_file(_isolate)["FABENCH_TIMIT_ROOT"] == f"{tmp_path}/elsewhere/TIMIT"


def test_unknown_corpus_in_root_is_rejected(tmp_path, _isolate):
    assert cmd_init(_args(root=["nosuch=/x"])) == 1


# --------------------------------------------------------------------------
# Interactive setup
# --------------------------------------------------------------------------
def test_prompts_default_to_what_is_already_set(tmp_path, monkeypatch, _isolate):
    """The point of re-running interactively is confirmation, not re-typing:
    what the machine file already says must be offered as the default, and it
    must outrank a fresh guess from the filesystem search."""
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))
    _isolate.write_text(_isolate.read_text().replace(str(data / "TIMIT"), "/deliberate/TIMIT"))

    seen: list[str] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda p="": seen.append(p) or "")

    assert cmd_init(_args(search=[str(data)])) == 0
    timit_prompt = next(p for p in seen if "timit" in p)
    assert "[/deliberate/TIMIT]" in timit_prompt
    assert str(data / "TIMIT") not in timit_prompt
    # The default IS the example. A made-up path beside it is noise, and the
    # two disagree on exactly the machines where the search got it right.
    assert "e.g." not in timit_prompt


def test_accepting_every_default_changes_nothing(tmp_path, monkeypatch, _isolate):
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))
    before = _isolate.read_text()

    _tty(monkeypatch, ["", "", ""])                   # buckeye, timit, gpus
    assert cmd_init(_args(search=[str(data)])) == 0
    assert _isolate.read_text() == before


def test_a_changed_answer_replaces_the_root(tmp_path, monkeypatch, _isolate):
    data = _stage(tmp_path)
    cmd_init(_args(search=[str(data)]))

    _tty(monkeypatch, ["", "/elsewhere/TIMIT", ""])   # buckeye keeps, timit moves
    assert cmd_init(_args(search=[str(data)])) == 0

    got = parse_env_file(_isolate)
    assert got["FABENCH_TIMIT_ROOT"] == "/elsewhere/TIMIT"
    assert got["FABENCH_BUCKEYE_ROOT"] == str(data / "Buckeye")


def test_a_blank_answer_leaves_a_corpus_unstaged(tmp_path, monkeypatch, _isolate):
    """"I have not downloaded that one yet" must be expressible, and must not
    invent a root that fails later and further from the cause."""
    _tty(monkeypatch, ["", "", ""])
    assert cmd_init(_args(search=[str(tmp_path / "nothing")])) == 0
    got = parse_env_file(_isolate) if _isolate.is_file() else {}
    assert "FABENCH_TIMIT_ROOT" not in got


def test_gpu_answer_reaches_the_env_file(tmp_path, monkeypatch, _isolate):
    _tty(monkeypatch, ["", "", "2"])
    cmd_init(_args(search=[str(tmp_path / "nothing")]))
    assert parse_env_file(_isolate)["FABENCH_CUDA_DEVICES"] == "0,1"

    # "all" must UNSET it, not write a device list: a pinned "0,1,2,3" would
    # silently cap a machine that later grows a fifth card.
    _tty(monkeypatch, ["", "", "all"])
    cmd_init(_args(search=[str(tmp_path / "nothing")]))
    assert "FABENCH_CUDA_DEVICES" not in parse_env_file(_isolate)

    # CPU-only is a real answer and must round-trip as an EMPTY value, which is
    # how CUDA is told to expose nothing -- not as "unset", which means all.
    _tty(monkeypatch, ["", "", "0"])
    cmd_init(_args(search=[str(tmp_path / "nothing")]))
    assert parse_env_file(_isolate)["FABENCH_CUDA_DEVICES"] == ""


def test_gpu_answers_people_actually_type():
    assert gpu_answer_to_devices("4", 4) == "0,1,2,3"      # a count
    assert gpu_answer_to_devices("2", 4) == "0,1"
    assert gpu_answer_to_devices("0,2", 4) == "0,2"        # explicit indices
    assert gpu_answer_to_devices("all", 4) is None         # unset == every GPU
    assert gpu_answer_to_devices("", 4) is None
    # "0 GPUs" is the OPPOSITE of "all", so it must not fall through to None.
    assert gpu_answer_to_devices("0", 4) == ""
    assert gpu_answer_to_devices("cpu", 4) == ""


def test_never_prompts_without_a_terminal(tmp_path, monkeypatch, _isolate):
    """CI, an agent, a nohup sweep: stdin is not a terminal, so init must
    complete on what it can find rather than block forever on a question
    nobody is there to answer."""
    data = _stage(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: pytest.fail("prompted"))

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert cmd_init(_args(search=[str(data)])) == 0

    # --non-interactive is the escape hatch from a real terminal.
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert cmd_init(_args(non_interactive=True, search=[str(data)])) == 0
