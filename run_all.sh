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

# FA-Bench top-level driver, kaldi-recipe style.
#
#   stage 0  ACQUIRE   licence notices + verify each corpus is present/usable
#   stage 1  PREP      i)  corpora -> canonical gold (ref.jsonl)
#                      ii) augment: noise mix                        [optional]
#   stage 2  EVAL      i)   install each FA package in its own venv
#                      ii)  run each tool  -> evals/<kind>/<tool>/.../hyp.jsonl
#                      iii) score          -> summary/<kind>/.../<cell>/
#   stage 3  ANALYSE   fabench/analyze/                            [optional]
#
# Usage:
#   ./run_all.sh                        # all stages, defaults
#   ./run_all.sh --stage 2 --stop-stage 2
#   ./run_all.sh --stage 2 --tools "olign mfa whisperx"
#   ./run_all.sh --augment yes          # include stage 1(ii), the noise build
#
# Every stage is re-runnable: acquisition only reads, ingest is cached, the
# noise build skips cells marked .done, and a tool with a hyp.jsonl is skipped
# unless --force. Nothing here aborts a sweep -- a failing cell is RECORDED and
# the run carries on, because a 4-hour matrix should not be lost to one bad
# adapter.
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$HERE"
PY="$HERE/.venv/bin/python"

stage=0
stop_stage=3
nj=24
augment=no
force=false
corpora="timit buckeye"
tools=""                     # default: whatever run_evals.sh finds installed
analyzers="tail_stats_report silence_edge_split"

# WHERE GOLD GOES.
# References sit beside the split list that selects them:
#     datasets/languages/<lang>/<corpus>/split/<subset>.phone.ref.jsonl
#     datasets/languages/<lang>/<corpus>/split/<subset>.word.ref.jsonl
# Phone and word are separate files because they are separate evaluations --
# a word-only system has no phone reference to score against.
#
# They are GITIGNORED. These files are TIMIT's .PHN and Buckeye's .phones
# reformatted, i.e. the licensed annotation itself; LDC and OSU both forbid
# redistribution, and git history is hard to retract. The path is in-repo for
# locality, the ignore rule keeps the content out of the history.
WORK=${WORK:-data/work}   # point at fast scratch on real runs

# Kaldi-style: every knob above is set by `--knob value`, dashes mapping to
# underscores. Shared with evals/run_evals.sh so both drivers parse alike, and
# an unknown option is an error rather than a silently ignored flag.
. "$(dirname "$0")/evals/parse_options.sh" || exit 1
[ $# -eq 0 ] || { echo "$0: unexpected argument '$1'" >&2; exit 1; }

[ -x "$PY" ] || { echo "$0: no venv at $PY -- create it first" >&2; exit 1; }
say() { echo; echo "=== $*"; }

# ------------------------------------------------------------------ stage 0
# Nothing is fetched: TIMIT is an LDC purchase, Buckeye needs OSU's permission,
# L2-ARCTIC a request form. Each download.py prints how to obtain the corpus
# and then verifies a copy you already have, so a wrong root fails HERE with a
# per-probe report rather than deep inside an ingest.
if [ "$stage" -le 0 ] && [ "$stop_stage" -ge 0 ]; then
  say "stage 0: acquire (notices + layout verification)"
  miss=0
  for c in $corpora; do
    dl="fabench/dataprep/datasets/en/$c/download.py"
    [ -f "$dl" ] || { echo "  no download.py for $c"; continue; }
    root=$("$PY" - "$c" <<'EOF' 2>/dev/null
import sys, glob
from fabench.config import load_config
cfgs = sorted(glob.glob("evals/configs/*.yaml"))
for f in cfgs:
    try:
        spec = load_config(f).datasets.get("gold", {}).get(sys.argv[1])
    except Exception:
        continue
    if isinstance(spec, dict) and spec.get("root"):
        print(spec["root"]); break
EOF
)
    if [ -z "$root" ]; then
      echo "  $c: no root configured -- printing acquisition notice"
      "$PY" "$dl" || true
      miss=$((miss+1)); continue
    fi
    if "$PY" "$dl" --quiet "$root"; then
      echo "  $c: usable at $root"
    else
      echo "  $c: NOT usable -- full notice follows" >&2
      "$PY" "$dl" || true
      miss=$((miss+1))
    fi
  done
  [ "$miss" -eq 0 ] || echo "  $miss corpus/corpora unusable; later stages will skip them"
fi

# ------------------------------------------------------------------ stage 1
if [ "$stage" -le 1 ] && [ "$stop_stage" -ge 1 ]; then
  say "stage 1(i): prep -- corpora -> gold references"
  # NO --config. It used to grab `ls evals/configs/*.yaml | head -1`, i.e. an
  # arbitrary generated CELL config -- which pinned ingest to whatever corpus
  # and subset that cell happened to name, and today would pick a cross-tool
  # rescore config or, with the directory empty, pass `--config ""`. Every
  # setting ingest needs composes from datasets/languages/ and fabench/.
  for c in $corpora; do
    echo "  ingesting $c"
    "$PY" -m fabench ingest --corpus "$c" 2>&1 | sed 's/^/    /'
  done
  # Materialise gold as an artefact, not just an in-memory dict, so the
  # reference side of every published number is diffable and checksummable.
  for c in $corpora; do
    "$PY" fabench/dataprep/datasets/export_refs.py \
        --corpus "$c" --repo-root "$HERE" 2>&1 | sed 's/^/  /'
  done
  echo "  refs under datasets/languages/*/*/split/*.ref.jsonl  (gitignored -- licensed gold)"

  if [ "$augment" = yes ]; then
    say "stage 1(ii): prep -- augment (MUSAN/RIRS noise mix)"
    # Four kaldi conditions over every split. Skips any cell already marked
    # .done, so this is safe to re-enter.
    NJ=$nj "$PY" fabench/dataprep/noisemix/make_noisy.py 2>&1 | sed 's/^/    /'
  else
    echo "  stage 1(ii) augment: SKIPPED (--augment yes to build the noise matrix)"
  fi
fi

# ------------------------------------------------------------------ stage 2
if [ "$stage" -le 2 ] && [ "$stop_stage" -ge 2 ]; then
  say "stage 2(i): eval -- install FA packages"
  # Each tool gets its OWN venv, and that is load-bearing, not tidiness:
  # installing whisperx into the shared env moved transformers 5.14.1 -> 4.57.6
  # and torch 2.13 -> 2.8 for Charsiu and BFA, so their published numbers were
  # set by a different tool's dependency resolution. See
  # fabench/aligners/subprocess_aligner.py for the full account.
  n_inst=0
  for kind in aligners timestamp_asrs; do
    # -maxdepth 4 so a historical version (<tool>/v<version>/) or an
    # experiment (<tool>/exps/<name>/) with its own installer is found too.
    while IFS= read -r ins; do
      d=$(dirname "$ins"); t=${d#evals/$kind/}
      if [ -d "$d/venv" ] || [ -d "$d/repo/env" ]; then
        [ "$force" = true ] || { echo "  $kind/$t: already installed"; continue; }
      fi
      echo "  installing $kind/$t"
      ( cd "$d" && bash download_and_install.sh ) > "$d/install.log" 2>&1 \
        && { echo "    ok"; n_inst=$((n_inst+1)); } \
        || echo "    FAILED (see $d/install.log)"
    done
  done
  echo "  newly installed: $n_inst"

  say "stage 2(ii): eval -- run tools -> hyp.jsonl"
  # run_evals.sh already does one FA-Bench run per (corpus, subset, tool) so a
  # dying adapter cannot take a whole cell's results with it.
  ./evals/run_evals.sh $tools 2>&1 | tail -40

  say "stage 2(iii): eval -- score -> summary/<kind>/<lang>/<corpus>/<cell>/"
  ./evals/rescore_all.sh 2>&1 | tail -20
fi

# ------------------------------------------------------------------ stage 3
if [ "$stage" -le 3 ] && [ "$stop_stage" -ge 3 ]; then
  say "stage 3: post-analysis (fabench/analyze/)"
  for a in $analyzers; do
    f="fabench/analyze/$a.py"
    [ -f "$f" ] || { echo "  no analyzer $a"; continue; }
    echo "  running $a"
    "$PY" "$f" 2>&1 | sed 's/^/    /' || echo "    FAILED $a"
  done
fi

echo
echo "FABENCH_RUN_DONE  (stages $stage..$stop_stage)"
