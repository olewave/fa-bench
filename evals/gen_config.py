#!/usr/bin/env python3
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

"""Emit a FA-Bench config for ONE (corpus, subset) evaluation cell.

Emits only what a per-cell run must CHOOSE; scope, seeds, scoring protocol and
every other default compose from their owning subsystem when the config is
loaded, so they stay exactly as the benchmark defines them.

Three overrides, each for a reason:

  * one corpus enabled per run -- otherwise `ingest` stages a corpus this cell
    will not score, and TIMIT's and Buckeye's subset names collide (`dev` means
    a different thing in each).
  * clean condition only -- every published number here is the clean cell, and
    the noise matrix would multiply a run by 13 for numbers nobody reports.
  * aligners come from evals/<tool>/config.yaml -- the installed environments are
    described there, so a run cannot silently disagree with what was installed.

Usage:
    ./gen_config.py --corpus timit --subset core_test --out /tmp/c.yaml
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fabench.paths import cell_dir, tool_dir

# Staged corpus roots — machine-specific and licensed, so they come from the
# environment. TIMIT is the NIST tree (TRAIN/ + TEST/); Buckeye is the
# flattened sNN/ tree produced by unpacking both zip layers. Left unset, the
# generated config carries a null root and ingest fails loud with the
# acquisition instructions (never a download).
ROOTS = {
    "timit": os.environ.get("FABENCH_TIMIT_ROOT"),
    "buckeye": os.environ.get("FABENCH_BUCKEYE_ROOT"),
}

SUBSETS = {
    "timit": ("train", "dev", "core_test"),
    "buckeye": ("train", "dev", "test"),
}


def build(corpus: str, subset: str, tools: list[str],
          device: str | None = None, condition: str = "") -> dict:
    # Built from NOTHING, not from a template: scope, seeds, paths, scoring,
    # normalization and the noise sources all compose at load time from the
    # subsystem that owns them. A cell config therefore holds only what this
    # cell chooses — its corpus, its conditions, its tools, its results dir —
    # which is also what makes it readable as a record of the run.
    cfg: dict = {}

    # ONE corpus per cell, stated for every corpus explicitly. The template no
    # longer lists corpora (the selection composes from
    # datasets/languages/<lang>/config.yaml at load time, where both are enabled), so
    # naming only the target would leave the other one enabled by default and
    # silently ingest a corpus this cell does not score. The corpus list is
    # discovered the same way load_config() discovers it.
    from fabench.paths import languages_dir
    corpora = sorted({p.parent.name
                      for p in languages_dir(ROOT).glob("*/*/config.yaml")})
    cfg.setdefault("datasets", {})["gold"] = {
        name: (
            {"enabled": True, "root": ROOTS[corpus], "subset": subset}
            if name == corpus
            else {"enabled": False}
        )
        for name in (corpora or [corpus])
    }

    # Clean-only cell. Assigned wholesale: the template carries no conditions
    # block anymore (defaults compose from fabench/noise/config.yaml at load
    # time), so there may be no key to index into.
    cfg["conditions"] = {"noise_types": [], "snr_db": [], "include_clean": True}

    entries = []
    for t in tools:
        # Tools are grouped by contract: evals/aligners/ vs evals/timestamp_asrs/ (fabench.paths).
        # Search every tool family (fabench.paths.KINDS): aligners and
        # timestamp_asrs both contribute rows to the same leaderboard.
        # Resolved through fabench.paths, the one index that knows the
        # layout: a recipe may sit at <tool>/, <tool>/exps/<name>/ or
        # <tool>/v<version>/, and is found by the name it declares.
        p = tool_dir(ROOT, t) / "config.yaml"
        if not p.exists():
            raise SystemExit(f"no config for {t!r}: {p} missing. Install it "
                             f"with evals/aligners/{t}/download_and_install.sh first.")
        e = yaml.safe_load(p.read_text())
        # Resolve tool-relative paths against the tool's OWN directory.
        #
        # config.yaml used to hardcode absolute paths to things inside the tool
        # dir (venv, repo/env, repo/mamba, worker.py). Moving evals/<tool>/ to
        # evals/<kind>/<tool>/ therefore broke five tools at once, and silently:
        # every clean sweep had already run, so nothing failed until the next
        # re-run. A tool naming its own subdirectory absolutely cannot survive
        # a move, a clone, or another machine.
        #
        # Relative values are resolved here, at generation time, so the config
        # still carries absolute paths for the runner. The `exists()` guard is
        # what makes this safe to apply blindly: `model: nvidia/parakeet-tdt`
        # is a HuggingFace id, not a path, and does not resolve to a real file.
        recipe_dir = p.parent
        for k, v in list((e.get("params") or {}).items()):
            if isinstance(v, str) and v and not v.startswith("/"):
                cand = recipe_dir / v
                if cand.exists():
                    e["params"][k] = str(cand.resolve())
        e["enabled"] = True
        # Bind this tool to a specific card when asked. All four GPUs are left
        # VISIBLE by default (evals/env.sh sets no device list unless
        # FABENCH_CUDA_DEVICES asks) so nothing is artificially hidden;
        # without an explicit index every concurrently-swept tool would
        # default to cuda:0 and pile onto one card while three sat idle.
        if device and e.get("params", {}).get("device", "").startswith("cuda"):
            e["params"]["device"] = device
        entries.append(e)
    cfg["aligners"] = entries

    # The cell's own directory, ABSOLUTE: a relative results_dir resolves
    # against the config file's location, and this config now LIVES in the cell,
    # so a relative value would nest a results dir inside it.
    #
    # Naming it here is what removed the `.stage3.yaml` copy. A cell config used
    # to point at the cross-tool tree, so scoring had to rewrite that one key
    # into a second file; a config that already names its own directory scores
    # in place. The cross-tool tree is assembled separately by rescore_all.sh,
    # which has its own configs listing every tool.
    tool = str(entries[0]["name"]) if entries else tools[0]
    cfg.setdefault("paths", {})["results_dir"] = str(
        cell_dir(ROOT, tool, corpus, subset, condition=condition).resolve())
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=sorted(ROOTS))
    ap.add_argument("--subset", required=True)
    ap.add_argument("--tools", default="mfa,charsiu,maps,bfa")
    ap.add_argument("--device", default=None,
                    help="bind cuda tools to a specific card, e.g. cuda:2")
    ap.add_argument("--out", default=None,
                    help="where to write it; default is the cell's own "
                         "<tool>/<lang>/<corpus>/<subset>/<condition>/config.yaml")
    a = ap.parse_args()

    if a.subset not in SUBSETS[a.corpus]:
        raise SystemExit(f"{a.corpus} has no subset {a.subset!r}; "
                         f"choose from {', '.join(SUBSETS[a.corpus])}")

    tools = [t.strip() for t in a.tools.split(",") if t.strip()]
    cfg = build(a.corpus, a.subset, tools, a.device)
    # The config lives IN the cell it describes, beside the hyp it will produce
    # and the scores of that hyp -- so `ls` on a cell answers what ran, on what,
    # and how it did, without cross-referencing a second tree.
    out = Path(a.out) if a.out else (
        cell_dir(ROOT, tools[0], a.corpus, a.subset) / "config.yaml")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"{out}  [{a.corpus}/{a.subset}]  aligners: {', '.join(tools)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
