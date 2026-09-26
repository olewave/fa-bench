#!/usr/bin/env bash
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

# The CI jobs, defined once. .github/workflows/ci.yml and .gitlab-ci.yml both
# call this script, and so can you before a push.
#
#   tools/ci.sh                lint, test and selftest on a clean export of HEAD
#   tools/ci.sh lint test      only the jobs named
#   tools/ci.sh --worktree     the working tree as it is, uncommitted edits included
#   tools/ci.sh --fresh        rebuild the local environment first
#
# In a pipeline (CI is set, as GitHub and GitLab both do) each job installs into
# the runner's Python and runs in the checkout. Run by hand, the jobs share
# .venv-ci, a Python 3.12 environment holding only what CI installs, so a test
# cannot pass here on a package that only the development .venv has. --fresh
# rebuilds it, which also picks up the dependency versions a new runner gets.
#
# The exit status is non-zero when any job fails, lint included. The pipelines
# keep lint advisory on their side (continue-on-error, allow_failure).

set -euo pipefail

RUFF_VERSION="0.16.9"   # pinned, so a new ruff release cannot fail an unchanged tree
PYTHON_VERSION="3.12"   # the python:3.12 image both pipelines run in

jobs=()
worktree=0
fresh=0
for arg in "$@"; do
  case "$arg" in
    lint|test|selftest) jobs+=("$arg") ;;
    --worktree) worktree=1 ;;
    --fresh) fresh=1 ;;
    -h|--help) sed -n '/^# The CI jobs/,/^$/s/^# \{0,1\}//p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg (lint, test, selftest, --worktree, --fresh)" >&2; exit 2 ;;
  esac
done
[ ${#jobs[@]} -gt 0 ] || jobs=(lint test selftest)

export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore

run_lint()     { "$PY" -m pip install -q "ruff==$RUFF_VERSION" && "$PY" -m ruff check . ; }
run_test()     { "$PY" -m pip install -q -e ".[test]" && "$PY" -m pytest -q ; }
run_selftest() { "$PY" -m pip install -q -e . && "$PY" -m fabench selftest ; }

if [ -n "${CI:-}" ]; then
  PY=python
  for job in "${jobs[@]}"; do "run_$job"; done
  exit 0
fi

root=$(git rev-parse --show-toplevel)
env_dir="$root/.venv-ci"
[ "$fresh" = 0 ] || rm -rf "$env_dir"
if [ ! -x "$env_dir/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv -q --seed --python "$PYTHON_VERSION" "$env_dir"
  elif command -v "python$PYTHON_VERSION" >/dev/null 2>&1; then
    "python$PYTHON_VERSION" -m venv "$env_dir"
  else
    echo "tools/ci.sh needs Python $PYTHON_VERSION, through uv or as python$PYTHON_VERSION" >&2
    exit 2
  fi
fi
PY="$env_dir/bin/python"

if [ "$worktree" = 1 ]; then
  src="$root"
  echo "checking the working tree"
else
  src=$(mktemp -d "${TMPDIR:-/tmp}/fabench-ci.XXXXXX")
  trap 'rm -rf "$src"' EXIT
  git -C "$root" archive HEAD | tar -x -C "$src"
  echo "checking $(git -C "$root" rev-parse --short HEAD) in a clean export"
fi

failed=()
for job in "${jobs[@]}"; do
  echo "== $job"
  if (cd "$src" && "run_$job"); then
    echo "== $job passed"
  else
    echo "== $job FAILED"
    failed+=("$job")
  fi
done
if [ ${#failed[@]} -gt 0 ]; then
  echo "failed: ${failed[*]}"
  exit 1
fi
echo "all passed: ${jobs[*]}"
