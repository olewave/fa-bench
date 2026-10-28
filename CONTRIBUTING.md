# Contributing to FA-Bench

FA-Bench is built from registries and contracts. You add a component by
dropping in a file and registering it, with no core edits. Each subsystem's
README carries the full recipe with code. In short,

- to **add an aligner**, write `fabench/aligners/<name>/adapter.py` and add
  one line to `fabench/aligners/__init__.py::_REGISTRY`.
- to **add a data processor**, write it under
  `fabench/dataprep/datasets/<lang>/<corpus>/`, add one `elif` to
  `fabench/dataprep/datasets/__init__.py::_dispatch`, and give it a canonical
  config in `datasets/languages/<lang>/<corpus>/config.yaml`.

**Looking for something to work on?** NeuFA's rows come from a checkpoint its
authors trained and have not released, so nobody outside can reproduce them.
The recipe in `evals/aligners/neufa/` is wired end to end and waits for a
public checkpoint. The benchmark already defines the splits to train one on,
held out of every scored cell for this purpose,
`datasets/languages/en/{timit,buckeye}/split/train.list`. Train, drop the
checkpoint at `repo/neufa.pt`, point `params.model_path` at it, and it joins
the leaderboard. The notes in its `config.yaml` say how a corpus-trained system is
marked so it is not read against pretrained ones. One legal note specific to
this ask. A trained checkpoint is a Contribution as any other, but it also
*derives from licensed corpora*. Before submitting one, confirm that your own
TIMIT (LDC) and Buckeye licences permit redistributing a model trained on
them. The code agreement cannot grant what the corpus licence withholds.

## Dev setup

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[test]"
.venv/bin/python -m pytest        # must be green before a PR
tools/ci.sh                       # the three CI jobs, as the pipelines run them
```

## CI

Every pull or merge request runs three jobs, the full `pytest`, the synthetic
`fabench selftest`, and an advisory `ruff check`. Both pipelines,
`.github/workflows/ci.yml` on GitHub and `.gitlab-ci.yml` on GitLab, run them
through `tools/ci.sh`, so the same script checks your work before you push.

```bash
tools/ci.sh                 # all three jobs on a clean export of HEAD
tools/ci.sh lint            # one job
tools/ci.sh --worktree      # the working tree, uncommitted edits included
```

It runs them in `.venv-ci`, a Python 3.12 environment holding only what CI
installs, and exits non-zero when any job fails, lint included. Ruff is pinned
in the script, so a new ruff release cannot fail an unchanged tree. Tests that
need an optional dependency or staged data skip themselves, so the jobs pass
on a clean runner. Make them blocking through branch protection, with required
status checks on GitHub and "Pipelines must succeed" on GitLab.

## License

FA-Bench is licensed under the **Apache License 2.0** from release 2.0.0 (see
[LICENSE](LICENSE) and [NOTICE](NOTICE)). Copyright 2026 Olewave, LLC.
Releases up to 1.1.3 were published under PolyForm Noncommercial and are no
longer distributed. The name FA-Bench stays with Olewave, as the README
explains.

## Contributions

You license your contribution under the Apache License 2.0, the licence of the
project, in the way section 5 of that licence describes. You keep your
copyright. Submit only work you have the right to license this way. If you
contribute as part of your job, your employer may own the code, so confirm
that they agree before you open the pull request.

New source files carry this header, below a shebang if there is one and above
the module docstring.

```python
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0
```

Vendored trees keep their own headers and never carry this one. Code ported
from another project keeps its original copyright line, and its licence is
named in [NOTICE](NOTICE).

## Restricted data

TIMIT and Buckeye are licensed and registration-gated. FA-Bench never
downloads them. A new data processor for a restricted corpus must fail loudly
with acquisition instructions rather than fetch anything.
