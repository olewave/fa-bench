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

# Rebuild every cell's leaderboard from the alignments already on disk.
#
# WHY THIS EXISTS. The sweep runs one FA-Bench invocation per (cell, tool) so a
# broken adapter cannot take down a whole cell. But each invocation rewrites
# that cell's report.md with only its own aligner's row, so after a sweep the
# report shows whichever tool happened to run last -- while the per-aligner
# hypotheses all survive side by side under <cell>/hyp/<tool>__<corpus>.jsonl.
#
# `fabench score` reads those hyp files rather than re-aligning, so scoring a
# cell with every tool enabled reassembles the full leaderboard in seconds
# instead of re-running Charsiu over Buckeye for another hour.
#
# Run this after any sweep.
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$HERE")
PY="$ROOT/.venv/bin/python"
CFGS="$HERE/configs"; mkdir -p "$CFGS"

# Systems held back from the PUBLIC leaderboards. Read from
# update_public_tables.py rather than restated here: the curated pages and these
# tables must suppress the SAME set, and two lists would drift the moment one is
# edited. Today it is olign's ablation sweep -- the variant names alone disclose
# a proprietary system's tunable axes, and the scores beside them say which
# setting won.
read -r SUPPRESS_PREFIX SUPPRESS_KEEP <<EOF2
$("$PY" - <<'PYEOF'
import importlib.util, pathlib
p = pathlib.Path("evals/update_public_tables.py")
s = importlib.util.spec_from_file_location("upt", p)
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(",".join(sorted(m.SUPPRESS_PREFIX)), ",".join(sorted(m.SUPPRESS_KEEP)))
PYEOF
)
EOF2

# Cells are DISCOVERED from the alignments on disk, never listed. A hardcoded
# list silently left all 16 noise-augmented cells holding one tool's row each --
# the same patchwork this script exists to repair, in the cells nobody thought
# to enumerate. A cell is <corpus>/<subset>/<condition>, with `origin` for the
# un-augmented run.
mapfile -t CELLS < <(find "$ROOT/evals" -name hyp.jsonl -path "*/en/*" 2>/dev/null \
  | sed -E 's|.*/en/||; s|/hyp\.jsonl$||; s|/| |g' | sort -u)
echo "== ${#CELLS[@]} cells"

for cell in "${CELLS[@]}"; do
  set -- $cell; corpus=$1; subset=$2; cond=$3

  # TRACK 1 AND TRACK 2 ARE SCORED SEPARATELY. Aligners are given the reference
  # transcript; timestamp_asrs decode their own words, so a track-2 row's timing
  # error carries its recognition error too and the two must not be ranked
  # head-to-head (fabench/paths.py::KINDS). They used to be accumulated into ONE
  # tool list and scored into one leaderboard -- whose system column is even
  # called `aligner` -- leaving a hand-written section in the curated pages as
  # the only thing separating them.
  for kind in aligners timestamp_asrs; do
    tools=""
    # Any depth: <tool>/, <tool>/exps/<name>/, <tool>/v<version>/. The tool NAME
    # is the one the recipe declares, not the directory name -- nested recipes
    # keep names like olign_noisy while living under olign/exps/.
    while IFS= read -r cfg; do
      d=$(dirname "$cfg")
      t=$(sed -n 's/^name: *//p' "$cfg" | head -1); t=${t:-$(basename "$d")}
      [ -f "$d/en/$corpus/$subset/$cond/hyp.jsonl" ] || continue
      # Respect `enabled: false`: discovery keys on config.yaml existing, so a
      # suppressed tool would otherwise be scored back into every leaderboard.
      grep -qE "^enabled: *false" "$cfg" 2>/dev/null && continue
      # Held back from the published tables (see SUPPRESS above). Still scored
      # into its own cell under evals/, which is gitignored -- internal, not lost.
      _skip=no
      for _p in ${SUPPRESS_PREFIX//,/ }; do
        case "$t" in "$_p"|"$_p"_*) _skip=yes ;; esac
      done
      case ",$SUPPRESS_KEEP," in *",$t,"*) _skip=no ;; esac
      [ "$_skip" = yes ] && continue
      tools="${tools:+$tools,}$t"
    done < <(find "$HERE/$kind" -mindepth 2 -maxdepth 4 -name config.yaml 2>/dev/null | sort)
    [ -n "$tools" ] || continue

    # Gold lives under the un-augmented cell -- noise preserves timing, so the
    # clean reference still applies -- while the hyp lives under the condition.
    # So the config is built for the subset and then told the condition, exactly
    # as gen_noisy_configs.py does.
    out="$ROOT/summary/$kind/en/$corpus/$subset/$cond"
    cfg="$CFGS/rescore_${kind}_${corpus}_${subset}_${cond}.yaml"
    "$PY" "$HERE/gen_config.py" --corpus "$corpus" --subset "$subset" \
        --tools "$tools" --out "$cfg" >/dev/null \
      || { echo "[fail] $kind $corpus/$subset/$cond config"; continue; }
    "$PY" - "$cfg" "$cond" "$out" <<'PYEOF'
import pathlib, sys, yaml
cfg, cond, out = sys.argv[1:4]
p = pathlib.Path(cfg); c = yaml.safe_load(p.read_text()) or {}
if cond != "origin":
    c["condition_tag"] = cond          # keeps hyp AND results off the baseline
c.setdefault("paths", {})["results_dir"] = out
p.write_text(yaml.safe_dump(c, sort_keys=False))
PYEOF

    if "$PY" -m fabench score --config "$cfg" >/dev/null 2>&1 \
       && "$PY" -m fabench report --config "$cfg" >/dev/null 2>&1; then
      echo "[ ok ] $kind  $corpus/$subset/$cond  <- $tools"
    else
      echo "[fail] $kind  $corpus/$subset/$cond  ($tools)"
    fi
  done
done
