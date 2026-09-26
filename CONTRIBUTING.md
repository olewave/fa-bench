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
- to **add a metric**, write `fabench/metrics/<name>.py` with
  `register(<Class>())`.
- to **add an analytic**, write `fabench/analyze/<name>.py` with
  `register(Analytic(...))`.

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
```

## CI

Every pull or merge request runs three jobs, from `.github/workflows/ci.yml`
on GitHub and `.gitlab-ci.yml` on GitLab. They are the full `pytest`, the
synthetic `fabench selftest`, and an advisory `ruff check`. Tests that need an
optional dependency or staged data skip themselves, so the jobs pass on a
clean runner. Make them blocking through branch protection, with required
status checks on GitHub and "Pipelines must succeed" on GitLab.

## License

FA-Bench is **PolyForm Noncommercial 1.0.0** (see [LICENSE](LICENSE)).
Copyright (C) 2026 Olewave, LLC. Any noncommercial purpose is permitted, which
covers research, teaching, personal study, and work by charitable,
educational, public-safety, environmental or government organisations.
**Commercial use requires a separate licence from Olewave, LLC.**

## Contributions

By submitting a contribution you agree that it is provided under the same
[PolyForm Noncommercial 1.0.0](LICENSE) terms as the rest of FA-Bench, and you
additionally grant Olewave, LLC a perpetual, irrevocable right to license your
contribution under other terms of its choosing, including commercially. You
keep your copyright. If you cannot agree to that, say so in the pull request
rather than staying silent. If you are contributing as part of your job, your
employer may own the code. Confirm they agree before submitting.

New source files should carry the standard header.

```python
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
```

It goes below a shebang if there is one, and above the module docstring.
Vendored trees keep their own headers and must never carry this one.

Note that this is **not** an OSI-approved open-source licence. The
noncommercial restriction is what disqualifies it. GitHub will not show a
recognised licence badge, and it cannot be published to PyPI under an
open-source classifier.

## Restricted data

TIMIT and Buckeye are licensed and registration-gated. FA-Bench never
downloads them. A new data processor for a restricted corpus must fail loudly
with acquisition instructions rather than fetch anything.
