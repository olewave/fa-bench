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

"""`.fabench.env` — the one place a machine's FABENCH_* settings live.

Both the CLI and the shell drivers read this file, so the rules that matter are
that it parses like shell, that an exported variable beats it, and that merely
importing fabench never applies it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fabench.envfile import find_env_file, load_env_file, parse_env_file


@pytest.fixture(autouse=True)
def _restore_environ():
    """load_env_file() writes to os.environ directly, which monkeypatch cannot
    know about and therefore cannot undo -- a leaked FABENCH_WORK_DIR failed an
    unrelated config test. Snapshot and restore around every test here."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_parses_the_shell_forms(tmp_path):
    p = tmp_path / ".fabench.env"
    p.write_text(
        "# a comment\n"
        "\n"
        "FABENCH_THREADS=6\n"
        'FABENCH_CUDA_DEVICES="1,2"\n'          # quoted: needed by shell, stripped here
        "export FABENCH_WORK_DIR=/fast/wd\n"    # `export ` prefix is shell-valid
        "  FABENCH_RESULTS_DIR = /out \n"       # tolerant of spacing
        "not_an_assignment\n"
    )
    got = parse_env_file(p)
    assert got == {
        "FABENCH_THREADS": "6",
        "FABENCH_CUDA_DEVICES": "1,2",
        "FABENCH_WORK_DIR": "/fast/wd",
        "FABENCH_RESULTS_DIR": "/out",
    }


def test_exported_environment_wins(tmp_path, monkeypatch):
    """The file is a default. A one-off `FABENCH_THREADS=8 ./run_evals.sh`
    must override it without anyone editing a file."""
    (tmp_path / ".fabench.env").write_text("FABENCH_THREADS=6\nFABENCH_WORK_DIR=/from/file\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FABENCH_ENV_FILE", raising=False)
    monkeypatch.setenv("FABENCH_THREADS", "8")
    monkeypatch.delenv("FABENCH_WORK_DIR", raising=False)

    load_env_file()
    assert os.environ["FABENCH_THREADS"] == "8"          # already set: untouched
    assert os.environ["FABENCH_WORK_DIR"] == "/from/file"  # unset: filled in


def test_found_from_a_subdirectory(tmp_path, monkeypatch):
    """Commands get typed from wherever, so the file is searched up the tree."""
    (tmp_path / ".fabench.env").write_text("FABENCH_THREADS=3\n")
    deep = tmp_path / "evals" / "aligners" / "mfa"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    monkeypatch.delenv("FABENCH_ENV_FILE", raising=False)
    assert find_env_file() == tmp_path / ".fabench.env"


def test_env_file_override_points_anywhere(tmp_path, monkeypatch):
    elsewhere = tmp_path / "machine.env"
    elsewhere.write_text("FABENCH_THREADS=4\n")
    monkeypatch.setenv("FABENCH_ENV_FILE", str(elsewhere))
    assert find_env_file() == elsewhere


def test_missing_file_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FABENCH_ENV_FILE", raising=False)
    assert find_env_file() is None
    assert load_env_file() is None


def test_the_tracked_template_documents_every_variable():
    """.fabench.env.example is the reference for these knobs, so a variable the
    code reads must appear in it -- otherwise a machine setting is discoverable
    only by grepping the source."""
    import re

    repo = Path(__file__).resolve().parents[2]
    example = (repo / ".fabench.env.example").read_text()
    src = ""
    for pat in ("fabench/**/*.py", "evals/*.sh", "evals/*.py"):
        for f in repo.glob(pat):
            if "/test" not in str(f):
                src += f.read_text(errors="ignore")
    read = {v for v in re.findall(r"FABENCH_[A-Z_]+", src)}
    # Internal markers, not user-facing settings.
    read -= {"FABENCH_ENV_FILE", "FABENCH_DEVICE", "FABENCH_RUN_DONE"}
    missing = sorted(v for v in read if v not in example)
    assert not missing, f"undocumented in .fabench.env.example: {missing}"


def test_the_shell_loader_agrees_with_this_one(tmp_path):
    """`evals/env.sh` and `fabench/envfile.py` read the SAME file, so they must
    read it the same way — including the rule that an exported variable always
    wins.

    env.sh used to `set -a; . file` with two variables stashed and restored by
    hand, so the rule held for FABENCH_CUDA_DEVICES and FABENCH_THREADS and
    silently failed for every other key: `FABENCH_NOISY_ROOT=/x ./augment.sh`
    was overridden by the file.
    """
    import subprocess

    repo = Path(__file__).resolve().parents[2]
    envf = tmp_path / "m.env"
    envf.write_text(
        "# a comment\n"
        "\n"
        "FABENCH_NOISY_ROOT=/from/file\n"
        'export FABENCH_WORK_DIR="/q u"\n'      # quoted + `export`
        "  FABENCH_RESULTS_DIR = /sp \n"        # tolerant spacing
        "not_an_assignment\n"
    )
    want = parse_env_file(envf)
    assert want["FABENCH_RESULTS_DIR"] == "/sp"   # both must trim, not keep " /sp "

    keys = sorted(want)
    script = (f'. "{repo}/evals/env.sh"\n'
              + "".join(f'printf "%s=%s\\n" {k} "${k}"\n' for k in keys))
    env = {"PATH": os.environ["PATH"], "FABENCH_ENV_FILE": str(envf),
           "FABENCH_NOISY_ROOT": "/exported"}       # already set: must survive
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                         env=env, cwd=tmp_path, check=False).stdout
    got = dict(ln.split("=", 1) for ln in out.splitlines() if "=" in ln)

    assert got["FABENCH_NOISY_ROOT"] == "/exported"          # export beats file
    for k in keys:
        if k != "FABENCH_NOISY_ROOT":
            assert got[k] == want[k], f"{k}: shell {got[k]!r} != python {want[k]!r}"
