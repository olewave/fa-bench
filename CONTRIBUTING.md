# Contributing to FA-Bench

FA-Bench is built from **registries + contracts** — add a component by dropping a
file and registering it, no core edits. Each subsystem's README carries the
full recipe with code. In short:

- **Add an aligner** → `fabench/aligners/<name>/adapter.py` + one line in
  `fabench/aligners/__init__.py::_REGISTRY`.
- **Add a data processor** → `fabench/dataprep/<lang>/<corpus>/processor.py` + one
  `elif` in `dataprep/__init__.py::_dispatch` + its canonical config in
  `datasets/languages/<lang>/<corpus>/config.yaml`.
- **Add a metric** → `fabench/metrics/<name>.py` with `register(<Class>())`.
- **Add an analytic** → `fabench/analyze/<name>.py` with `register(Analytic(...))`.

**Looking for something to work on?** NeuFA (`evals/aligners/neufa/`) is wired
end to end but has no trained checkpoint — the authors published none. The
benchmark already defines the splits to train it on, held out of every scored
cell for exactly this purpose: `datasets/languages/en/{timit,buckeye}/split/
train.list`. Train, drop the checkpoint at `repo/neufa.pt`, flip `enabled: true`,
and it joins the leaderboard. See the notes in its `config.yaml`, including how
a corpus-trained system is marked so it is not read against pretrained ones.
One legal note specific to this ask: a trained checkpoint is a Contribution
like any other, but it also *derives from
licensed corpora* — before submitting one, confirm your own TIMIT (LDC) and
Buckeye licences permit redistributing a model trained on them. The code
agreement cannot grant what the corpus licence withholds.

## Dev setup

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[test]"
.venv/bin/python -m pytest        # must be green before a PR
```

## CI

Every pull/merge request runs the same four gates — full `pytest`, the
synthetic-oracle `fabench selftest`, and an advisory
`ruff check` — from `.github/workflows/ci.yml` on GitHub and `.gitlab-ci.yml`
on GitLab. Optional-dep and staged-data tests self-skip, so the gates pass on
a clean runner. Make them blocking via branch protection (GitHub: required
status checks; GitLab: "Pipelines must succeed").

## License

FA-Bench is **PolyForm Noncommercial 1.0.0** (see [LICENSE](LICENSE));
Copyright (C) 2026 Olewave, LLC. Any noncommercial purpose is permitted --
research, teaching, personal study, and work by charitable, educational,
public-safety, environmental or government organisations. **Commercial use
requires a separate licence from Olewave, LLC.**

## Contributions

By submitting a contribution you agree that it is provided under the same
[PolyForm Noncommercial 1.0.0](LICENSE) terms as the rest of FA-Bench, and you
additionally grant Olewave, LLC a perpetual, irrevocable right to license your
contribution under other terms of its choosing, including commercially. You
keep your copyright. If you cannot agree to that, say so in the pull request
rather than staying silent. If you are contributing as part of your job, your
employer may own the code — confirm they agree before submitting.

New source files should carry the standard header:

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

It goes below a shebang if there is one, above the module docstring. Vendored
trees keep their own headers and must never carry this one.

Note this is **not** an OSI-approved open-source licence: the noncommercial
restriction is what makes it not one. GitHub will not show a recognised licence
badge, and it cannot be published to PyPI under an open-source classifier.

## Restricted data

TIMIT and Buckeye are licensed/registration-gated. FA-Bench never downloads them;
new data processors for restricted corpora must fail loudly with acquisition
instructions rather than fetch anything.
