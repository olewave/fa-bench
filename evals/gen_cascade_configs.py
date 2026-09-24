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

"""Generate per-cell configs for a CASCADE: an aligner fed an ASR transcript.

    gen_cascade_configs.py --aligner mfa --asr qwen3_asr --name mfa3_on_qwen3asr \
        --cells "timit core_test" "buckeye test"

Each cell config is the base aligner's own cell config with three changes:

  aligners[0].name        the cascade's name, so results are attributed to it
  params.transcript_hyp   the ASR's hypothesis FOR THAT EXACT CELL
  paths.results_dir       the cascade's own cell directory

That third one is not incidental. The base config carries an absolute
results_dir pointing at the base aligner's cell; copying a config without
rewriting it makes the scorer overwrite the gold-transcript leaderboard with
cascade numbers. That happened twice by hand before this script existed, and it
is silent -- hyp.jsonl is untouched, so only the derived table is wrong.

The upstream hypothesis must match corpus, split AND condition. Pairing a clean
transcript with noisy audio would flatter the cascade, so a missing upstream is
an error here rather than a fallback to gold.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONDS = ("origin", "reverb", "noise", "music", "babble")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--aligner", required=True, help="base aligner tool name, e.g. mfa")
    ap.add_argument("--asr", default="qwen3_asr", help="upstream ASR tool name")
    ap.add_argument("--name", required=True, help="cascade tool name")
    ap.add_argument("--cells", nargs="+", required=True, help='"<corpus> <subset>" ...')
    ap.add_argument("--conditions", nargs="+", default=list(CONDS))
    a = ap.parse_args(argv)

    # Resolve tool directories by DECLARED NAME, not by assuming
    # evals/<kind>/<name>. A variant recipe lives nested -- mfa2 is
    # evals/aligners/mfa/v2.0.6 -- so guessing the path silently reports
    # "no base config" for a tool whose cells are all present.
    sys.path.insert(0, str(ROOT))
    from fabench.paths import tool_index
    idx = tool_index(ROOT)
    for who in (a.aligner, a.asr):
        if who not in idx:
            print(f"unknown tool {who!r} -- no recipe declares that name",
                  file=sys.stderr)
            return 2
    base_dir = idx[a.aligner][1]
    asr_dir = idx[a.asr][1]

    # THE RECIPE CONFIG, not just the cells. rescore_all.sh -- the only thing
    # that pools per-cell scores into summary/, and so into every published
    # table -- discovers tools by finding evals/<kind>/<tool>/config.yaml. The
    # per-cell configs sit four levels deeper and are never seen. Without this
    # a cascade runs, scores, and is silently absent from the leaderboards.
    recipe = ROOT / "evals/timestamp_asrs" / a.name / "config.yaml"
    if not recipe.exists():
        spec = yaml.safe_load((base_dir / "config.yaml").read_text()) or {}
        spec["name"] = a.name
        prm = spec.setdefault("params", {})
        prm.pop("transcript_hyp", None)      # per cell, never in the recipe
        prm["requires_transcript_hyp"] = True
        # Relative tool paths are resolved against the BASE tool's directory;
        # from the cascade's own directory they would point at nothing.
        for key, val in list(prm.items()):
            if isinstance(val, str) and ("/" in val) and not val.startswith("/") \
                    and (base_dir / val).exists():
                prm[key] = str((base_dir / val).resolve())
        recipe.parent.mkdir(parents=True, exist_ok=True)
        recipe.write_text(
            f"# CASCADE RECIPE: {a.aligner} aligning what {a.asr} decoded.\n"
            "#\n"
            "# Track 2 by construction -- the words were recognised, not given --\n"
            "# so this belongs beside the timestamped ASRs. Scoring still uses the\n"
            "# reference gold, so recognition error costs this row exactly what it\n"
            "# costs a one-step ASR and the two are directly comparable.\n"
            "#\n"
            "# transcript_hyp is set PER CELL, never here: a cascade is only\n"
            "# meaningful when the upstream hypothesis came from the matching\n"
            "# corpus, split and condition. requires_transcript_hyp makes running\n"
            "# this recipe directly an error rather than a silent gold run.\n"
            "# Generated by evals/gen_cascade_configs.py -- do not hand-edit.\n"
            + yaml.safe_dump(spec, sort_keys=False))
        print(f"  recipe written: {recipe.relative_to(ROOT)}")

    written = skipped = 0
    for cell in a.cells:
        corpus, subset = cell.split()
        for cond in a.conditions:
            base = base_dir / f"en/{corpus}/{subset}/{cond}/config.yaml"
            up = asr_dir / f"en/{corpus}/{subset}/{cond}/hyp.jsonl"
            if not base.is_file():
                print(f"  skip {corpus}/{subset}/{cond}: no base config for {a.aligner}",
                      file=sys.stderr); skipped += 1; continue
            if not up.is_file() or up.stat().st_size == 0:
                print(f"  skip {corpus}/{subset}/{cond}: no {a.asr} hypothesis upstream",
                      file=sys.stderr); skipped += 1; continue

            cfg = yaml.safe_load(base.read_text())
            al = cfg["aligners"][0]
            al["name"] = a.name
            al.setdefault("params", {})["transcript_hyp"] = str(up.relative_to(ROOT))
            out = ROOT / f"evals/timestamp_asrs/{a.name}/en/{corpus}/{subset}/{cond}"
            out.mkdir(parents=True, exist_ok=True)
            cfg.setdefault("paths", {})["results_dir"] = str(out)
            # The adapter takes these paths as given -- it does not resolve
            # them against the tool dir -- and its micromamba default is
            # ~/micromamba/bin/micromamba, which exists on no machine here.
            # Absolutise, and derive the binary, or the cascade dies with
            # "MFA not available" forty lines into the run.
            prm = al.setdefault("params", {})
            mr = prm.get("mamba_root")
            if mr and not str(mr).startswith("/"):
                mr = str((base_dir / mr).resolve())
                prm["mamba_root"] = mr
            if mr and not prm.get("micromamba"):
                prm["micromamba"] = str(pathlib.Path(mr) / "bin" / "micromamba")
            (out / "config.yaml").write_text(
                f"# CASCADE: {a.aligner} aligning the transcript {a.asr} decoded for\n"
                f"# this cell ({corpus}/{subset}/{cond}). Generated -- do not hand-edit.\n"
                + yaml.safe_dump(cfg, sort_keys=False))
            written += 1
    print(f"{written} cascade configs written, {skipped} skipped")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
