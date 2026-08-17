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

"""Pipeline guards: no noise fetch before a corpus is confirmed staged."""

import os
import types
from pathlib import Path

CONFIG = None   # composed defaults; see fabench.config.load_config


def test_run_no_gold_does_not_construct_provider(tmp_path, monkeypatch):
    """Regression: `fabench run` with nothing staged must not touch the noise
    provider (which would fetch ~11 GB of MUSAN).

    "Nothing staged" has to be enforced, not assumed: FABENCH_TIMIT_ROOT points
    at a real corpus on any machine set up to run the benchmark, and gold then
    loads for real -- the test found 192 utterances and the premise was gone.
    """
    for k in [k for k in os.environ if k.startswith("FABENCH_")]:
        monkeypatch.delenv(k, raising=False)

    import fabench.noise.provider as prov

    called = {"n": 0}

    def boom(cfg):
        called["n"] += 1
        raise AssertionError("NoiseProvider.from_config must not run without gold")

    monkeypatch.setattr(prov.NoiseProvider, "from_config", staticmethod(boom))

    # point summary/work at tmp so we don't write into the repo
    from fabench import pipeline
    from fabench.config import load_config

    cfg = load_config(CONFIG)
    monkeypatch.setattr(cfg, "raw", {**cfg.raw,
                                     "paths": {"work_dir": str(tmp_path / "w"),
                                               "results_dir": str(tmp_path / "r")}})

    # cmd_run loads its own config; patch load_config to return our tmp-pathed cfg
    monkeypatch.setattr(pipeline, "load_config", lambda _p: cfg)

    args = types.SimpleNamespace(config=str(CONFIG), limit=None)
    rc = pipeline.cmd_run(args)
    assert rc == 1              # nothing staged
    assert called["n"] == 0     # provider never constructed
    assert (Path(cfg.results_dir()) / "report.md").exists()
