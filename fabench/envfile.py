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

"""Load `.fabench.env` — the machine's settings, in one file both worlds read.

FA-Bench is driven two ways: shell recipes under `evals/`, and the `fabench`
CLI. Environment knobs (`FABENCH_*`) were readable by both and *settable* by
neither — every one had to be exported by hand in whatever shell happened to
launch the run, so a machine's setup lived in someone's history rather than on
disk.

`.fabench.env` is `KEY=value` lines, which is simultaneously valid shell (so
`evals/env.sh` sources it) and trivially parsed here (so the CLI applies it
before any config is loaded). One file, both drivers, no duplication.

Precedence: **an already-set environment variable always wins.** The file is a
default, so a one-off `FABENCH_THREADS=8 ./run_evals.sh` overrides it without
editing anything — the same "more specific statement wins" rule the config
composition uses.

What belongs here: everything that is true of the MACHINE — staged corpus
roots, GPUs, thread budget, where external tool checkouts and micromamba live,
test fixtures. It is the ONLY file `fabench init` writes, because everything a
RUN is (which corpora, on which subset, which systems, how scored) composes
from the tree that owns it — `datasets/languages/<lang>/config.yaml`,
`evals/config.yaml`, `fabench/*/config.yaml`.

A run config remains possible for a deliberate variant, named via `--config` or
`$FABENCH_CONFIG`, and still wins over this file: precedence is run config >
environment > composed defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Looked for beside the repo root, and overridable outright.
ENV_FILE = ".fabench.env"


def parse_env_file(path: Path) -> dict[str, str]:
    """`KEY=value` lines -> a dict. Comments, blanks and `export ` are ignored.

    Quotes around a value are stripped, so the file stays valid shell (where
    `FOO="a b"` needs them) without the quotes leaking into the value here.
    """
    out: dict[str, str] = {}
    try:
        text = path.read_text()
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def find_env_file(start: Path | None = None) -> Path | None:
    """`$FABENCH_ENV_FILE`, else `.fabench.env` in `start` or any parent.

    Walking up means a command run from a subdirectory of the repo still finds
    the machine's settings, which is where most commands are actually typed.
    """
    override = os.environ.get("FABENCH_ENV_FILE")
    if override:
        p = Path(override).expanduser()
        return p if p.is_file() else None
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        p = d / ENV_FILE
        if p.is_file():
            return p
    return None


def load_env_file(start: Path | None = None) -> Path | None:
    """Apply the file to `os.environ` without overriding what is already set.

    Returns the file used, or None. Applied by the CLI before a config is
    loaded; never by the library, so importing fabench cannot silently pick up
    a machine's settings.
    """
    path = find_env_file(start)
    if path is None:
        return None
    for key, val in parse_env_file(path).items():
        os.environ.setdefault(key, val)
    return path
