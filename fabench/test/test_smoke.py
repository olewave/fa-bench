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

"""S0 smoke: package imports, CLI parser builds, config loads and validates."""

import os
from pathlib import Path

import fabench
from fabench.cli import build_parser
from fabench.config import load_config

REPO = Path(__file__).resolve().parents[2]   # fabench/test/ -> repo root
CONFIG = None   # compose the defaults; a run config only carries overrides


def test_version():
    assert fabench.__version__


def test_parser_builds_and_help():
    p = build_parser()
    # argparse exits(0) on --help; catch it.
    import pytest

    with pytest.raises(SystemExit) as e:
        p.parse_args(["--help"])
    assert e.value.code == 0


def test_config_loads_and_conditions():
    cfg = load_config(CONFIG)
    conds = cfg.conditions()
    names = {c.name for c in conds}
    # clean + 4 noise types x 3 SNRs = 13 conditions.
    assert "clean" in names
    assert "babble_snr10" in names
    assert len(conds) == 1 + 4 * 3
    # The comparison set composes from evals/config.yaml, so `fabench run`
    # with no config means something rather than "compare nothing".
    names = [a.name for a in cfg.aligners()]
    assert "torchaudio_fa" in names and "mfa" in names
    # Only what a bare `uv pip install -e .` can actually run is ON: every
    # other tool needs its own environment built first, and enabling one by
    # default would fail the out-of-the-box command with a missing-tool error.
    assert [a.name for a in cfg.aligners(enabled_only=True)] == ["torchaudio_fa"]


def test_aligner_entry_composes_from_its_folder(tmp_path):
    """A run config lists aligners by name; the full definition composes from
    the tool's canonical evals/<kind>/<tool>/config.yaml. A pinned copy once
    drifted silently — losing phoneme_model turned the phone tier off — so a
    slim entry resolving to the complete spec is the property that matters.
    The config is written OUTSIDE the repo to prove the package-anchored
    lookup works for generated/local configs anywhere."""
    run = tmp_path / "run.yaml"
    run.write_text("aligners:\n  - { name: torchaudio_fa, enabled: true }\n")

    spec = load_config(run).aligner("torchaudio_fa")
    assert spec.enabled is True                     # run-scoped, from the entry
    assert spec.adapter == "torchaudio_fa"          # from the tool folder
    assert spec.modes == ["A", "B"]
    assert spec.emits_confidence is True
    assert spec.params["phoneme_model"] == "facebook/wav2vec2-lv-60-espeak-cv-ft"


def _no_ambient_fabench_env(monkeypatch):
    """Compose the config from FILES ONLY.

    These two tests assert what the committed defaults resolve to, and every
    FABENCH_* override is by design allowed to change that -- FABENCH_TIMIT_ROOT
    fills in the root they assert is None. The repo ships .fabench.env for
    exactly that purpose, so anyone who has sourced it (or exported a corpus
    root, which is the normal way to work here) saw two failures that said
    nothing about their change. CI passes only because its runner is bare.
    """
    for k in [k for k in os.environ if k.startswith("FABENCH_")]:
        monkeypatch.delenv(k, raising=False)


def test_dataset_config_composes_from_dataset_folders(monkeypatch):
    _no_ambient_fabench_env(monkeypatch)
    """Every subsystem's defaults compose from the folder that owns them, so a
    run with NO config file at all (load_config(None)) must still resolve to a
    complete, runnable configuration. This is the load-bearing property behind
    there being no committed run template."""
    cfg = load_config(CONFIG)
    tim = cfg.datasets["gold"]["timit"]
    bck = cfg.datasets["gold"]["buckeye"]
    # corpus selection, from the language layer datasets/languages/en/config.yaml
    assert tim["enabled"] is True and bck["enabled"] is True
    assert tim["subset"] == "core_test" and bck["subset"] == "dev"
    # corpus-intrinsic defaults, from datasets/languages/en/<corpus>/config.yaml
    assert tim["merge_closures"] is False
    assert bck["protocol"] == "paper"
    assert tim["root"] is None and bck["root"] is None
    # noise-source defaults, from fabench/noise/config.yaml
    musan = cfg.datasets["noise"]["musan"]
    assert musan["enabled"] is True
    assert musan["cache_dir"] == "data/musan"
    assert musan["babble_min_sources"] == 6
    # normalize defaults, from fabench/normalize/en/config.yaml
    assert cfg.normalize["canonical"] == "timit39"
    assert cfg.normalize["max_unmapped_rate"] == 0.01
    # scoring defaults, from fabench/score/config.yaml
    assert cfg.scoring["protocol"] == "fabench"
    assert cfg.scoring["manner_match"] is True
    assert cfg.scoring["mfa_paper"]["onset_only_aligners"] == ["bfa"]
    # the frozen scope contract, from fabench/config.yaml
    assert cfg.scope["channel"] == "additive_noise_only"
    assert cfg.scope["language"] == "english"
    assert cfg.scope["gold_policy"] == "reuse_existing"
    # seeds, each from the subsystem it drives
    assert cfg.seeds["global"] == 20240607          # fabench/config.yaml
    assert cfg.seeds["noise_split"] == 1317         # fabench/noise/config.yaml
    assert cfg.seeds["mix"] == 8675309
    # output paths, from fabench/config.yaml
    assert cfg.work_dir() == Path("data/work")
    # summary/local, not results: a run must not write the PUBLISHED tree.
    # With one shared directory, `fabench run` on a fresh clone overwrote 40
    # tracked files; regenerating the published numbers is now deliberate
    # (FABENCH_RESULTS_DIR=results, or paths.results_dir in a run config).
    assert cfg.results_dir() == REPO / "summary" / "local"


def test_directory_env_overrides(tmp_path, monkeypatch):
    """The three machine-specific directories — staged corpus roots, bulk
    intermediates, results — can be set once in the environment instead of in
    every config. Precedence is run config > environment > composed defaults:
    a sweep must not change meaning because a shell exported something."""
    monkeypatch.setenv("FABENCH_TIMIT_ROOT", "/data/TIMIT")
    monkeypatch.setenv("FABENCH_WORK_DIR", "/scratch/fb")
    monkeypatch.setenv("FABENCH_RESULTS_DIR", "/out/results")

    env_only = load_config()
    assert env_only.datasets["gold"]["timit"]["root"] == "/data/TIMIT"
    assert env_only.work_dir() == Path("/scratch/fb")
    assert env_only.results_dir() == Path("/out/results")

    run = tmp_path / "run.yaml"
    run.write_text("datasets: {gold: {timit: {root: /explicit/TIMIT}}}\n"
                   "paths: {work_dir: /explicit/work}\n")
    stated = load_config(run)
    assert stated.datasets["gold"]["timit"]["root"] == "/explicit/TIMIT"
    assert stated.work_dir() == Path("/explicit/work")
    assert stated.results_dir() == Path("/out/results")   # unstated -> env

    monkeypatch.delenv("FABENCH_TIMIT_ROOT")
    monkeypatch.delenv("FABENCH_WORK_DIR")
    monkeypatch.delenv("FABENCH_RESULTS_DIR")
    bare = load_config()
    assert bare.datasets["gold"]["timit"]["root"] is None    # fails loud at ingest
    assert bare.work_dir() == Path("data/work")


def test_cli_config_resolution(tmp_path, monkeypatch):
    """--config > $FABENCH_CONFIG > composed defaults, and NO magic filename.

    A config picked up because it happens to sit in the working directory would
    make the same command mean different things in different checkouts, so a
    run config is only ever named explicitly."""
    from fabench.cli import _resolve_config

    _no_ambient_fabench_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert _resolve_config(None) is None                    # nothing anywhere

    # A file sitting in the old magic location is NOT picked up.
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "local.yaml").write_text("{}\n")
    assert _resolve_config(None) is None

    monkeypatch.setenv("FABENCH_CONFIG", "/from/env.yaml")
    assert _resolve_config(None) == "/from/env.yaml"
    assert _resolve_config("/explicit.yaml") == "/explicit.yaml"   # flag wins

    # The library never applies the convention, even standing in that directory.
    assert load_config(None).datasets["gold"]["timit"]["root"] is None


def test_excluded_gold_guard():
    from fabench.config import is_excluded_gold

    excl = ["libritts", "librispeech-alignments", "commonvoice"]
    assert is_excluded_gold("/data/english/LibriTTS-R/x", excl) == "libritts"
    assert is_excluded_gold("/data/timit/TEST", excl) is None


def test_a_run_never_writes_the_published_results_tree(tmp_path, monkeypatch):
    """`summary/` is tracked — it is what a reader sees on GitHub without
    running anything. A plain run therefore writes `summary/local/`, so a
    clone-and-reproduce leaves `git status` clean and a partial sweep cannot
    overwrite a published table with the one row it has produced so far.

    (That is not hypothetical: regenerating the tables mid-sweep once collapsed
    an 18-aligner table to a single row.)
    """
    monkeypatch.delenv("FABENCH_RESULTS_DIR", raising=False)
    default = load_config(CONFIG).results_dir()
    assert default == REPO / "summary" / "local"
    assert default.is_relative_to(REPO / "summary")   # same tier, one level in

    # Writing the published tree stays possible — deliberately, by naming it.
    monkeypatch.setenv("FABENCH_RESULTS_DIR", str(REPO / "summary"))
    assert load_config(CONFIG).results_dir() == REPO / "summary"
