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

"""Generate eval configs that point at the noise-augmented shadow roots.

Takes an existing clean config for a (corpus, subset, tool) cell and rewrites
only the gold ``root:`` to the matching shadow root, leaving every other
setting identical. That is the whole trick: the shadow root looks like the
corpus but its audio is noisy, so ingest, utterance slicing, split lists and
gold all work unmodified (see fabench/dataprep/noisemix/shadow_root.py).

Because the noise pipeline preserves duration to the millisecond, the clean
gold stays valid for every condition -- the same reference scores all five.

Scope is a parameter, not a policy: pass --subsets to run the cheap held-out
comparison or the full matrix.

    gen_noisy_configs.py --tools mfa olign --subsets timit:core_test buckeye:test
    gen_noisy_configs.py --tools ALL --subsets ALL --conditions noise babble
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fabench.paths import ORIGIN, cell_dir

# Machine-specific roots come from the environment (see evals/gen_config.py).
SHADOW = Path(os.environ.get("FABENCH_SHADOW", "data/shadow"))
CLEAN_ROOT = {"timit": os.environ.get("FABENCH_TIMIT_ROOT"),
              "buckeye": os.environ.get("FABENCH_BUCKEYE_ROOT")}
CONDITIONS = ("reverb", "noise", "music", "babble")
DEFAULT_SUBSETS = ("timit:core_test", "buckeye:test")


def installed_tools() -> list[str]:
    """Tools that have actually produced clean results.

    NOT a venv/ probe. That was the first cut and it under-detected badly --
    7 of 13, missing mfa and mfa2 (micromamba root), olign/olign_b/olign_t (a
    running server, no local env), crisperwhisper_fa and torchaudio_fa (shared
    venv). All six have clean results, so excluding them would have silently
    shrunk the noisy sweep to half the table with no error.

    Having a clean hyp.jsonl is the property that actually matters here: it
    means the tool ran to completion on this cell, so a noisy counterpart is
    both runnable and comparable.
    """
    # From the shared index, so nested recipes (<tool>/exps/<name>/,
    # <tool>/v<version>/) are found and reported under the name they declare
    # -- a flat glob returned the directory name and missed them entirely.
    sys.path.insert(0, str(ROOT))
    from fabench.paths import ORIGIN, tool_index

    # en/<corpus>/<subset>/<condition>/hyp.jsonl -- FOUR levels, and the
    # condition must be ORIGIN. The glob counted three, from before a cell
    # became its own directory, so it matched nothing and this returned an
    # empty tool list: `--tools ALL` then wrote 0 configs and exited 0, which
    # reads exactly like "nothing needed regenerating". Spelling ORIGIN rather
    # than `*` also keeps a noisy-only result from qualifying a tool as having
    # produced the clean baseline this compares against.
    return sorted(name for name, (_k, d) in tool_index(ROOT).items()
                  if any(d.glob(f"en/*/*/{ORIGIN}/hyp.jsonl")))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tools", nargs="+", required=True,
                    help='tool names, or ALL for every installed tool')
    ap.add_argument("--subsets", nargs="+", default=list(DEFAULT_SUBSETS),
                    help='corpus:subset pairs, or ALL')
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    # Default None = write beside each tool, in evals/<kind>/<tool>/configs/.
    # A flat directory accumulated every corpus x subset x condition x tool and
    # stopped being readable; --out-dir still forces one place when a caller
    # wants the whole sweep collected.
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    tools = installed_tools() if a.tools == ["ALL"] else a.tools
    subsets = (["timit:dev", "timit:core_test",
                "buckeye:dev", "buckeye:test"]
               if a.subsets == ["ALL"] else a.subsets)

    out_dir = Path(a.out_dir) if a.out_dir else None
    made = skipped = 0
    for pair in subsets:
        corpus, subset = pair.split(":")
        for tool in tools:
            # Each tool's configs sit with the tool, so the name drops it. A
            # forced --out-dir keeps the old flat naming, which is the only way
            # names stay unique once everything shares one directory.
            # The clean cell's own config is the template; its noisy siblings
            # are written into the sibling condition directories.
            base = (out_dir / f"{corpus}_{subset}_{tool}.yaml" if out_dir
                    else cell_dir(ROOT, tool, corpus, subset) / "config.yaml")
            if not base.is_file():
                print(f"  no clean config for {corpus}/{subset}/{tool} "
                      f"-- run gen_config.py first", file=sys.stderr)
                skipped += 1
                continue
            src = base.read_text()
            for cond in a.conditions:
                shadow = SHADOW / f"{corpus}_{cond}"
                if not shadow.is_dir():
                    print(f"  no shadow root {shadow}", file=sys.stderr)
                    skipped += 1
                    continue
                text = src.replace(CLEAN_ROOT[corpus], str(shadow))
                # condition_tag keeps hyp AND results off the clean baseline:
                # without it `name: mfa` under reverb overwrites
                # evals/aligners/mfa/en/timit/core_test/hyp.jsonl.
                text = f"condition_tag: {cond}\n" + text
                # results_dir ends in the CONDITION directory, because a cell is
                # <tool>/en/<corpus>/<subset>/<condition>/. The old rewrite
                # targeted `summary/en/<corpus>/<subset>` -- a layout that
                # predates both the results->summary rename and cells becoming
                # directories -- so it silently matched nothing and every noisy
                # config kept pointing at the CLEAN cell. A noisy run then wrote
                # its report over origin/report.md, i.e. the baseline it is meant
                # to be compared against. Anchored on the trailing component so
                # it cannot quietly stop matching again.
                text, n_sub = re.subn(
                    rf"(?m)^(\s*results_dir:\s*\S+/){re.escape(ORIGIN)}\s*$",
                    rf"\g<1>{cond}", text)
                if not n_sub:
                    print(f"  WARNING: results_dir not rewritten for "
                          f"{corpus}/{subset}/{tool}/{cond} -- it would write "
                          f"over the clean cell", file=sys.stderr)
                    skipped += 1
                    continue
                if text == src:
                    print(f"  WARNING: root not substituted in {base.name} "
                          f"-- clean root not found in it", file=sys.stderr)
                    skipped += 1
                    continue
                dst = (out_dir / f"noisy_{cond}_{corpus}_{subset}_{tool}.yaml" if out_dir
                       else cell_dir(ROOT, tool, corpus, subset, condition=cond) / "config.yaml")
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not a.dry_run:
                    dst.write_text(text)
                made += 1
    print(f"  {made} configs {'would be ' if a.dry_run else ''}written"
          + (f", {skipped} skipped" if skipped else ""))
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
