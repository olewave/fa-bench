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

# Run-environment knobs for the eval drivers — sourced, never executed.
#
# The one place that decides how a sweep uses the BOX, as opposed to what it
# measures. Every value here is machine-specific, so every one is overridable
# from the environment and nothing is baked into a driver script.
#
#   FABENCH_CUDA_DEVICES   which GPUs a sweep may use, e.g. "0,1" or "2"
#                          UNSET (default) = leave CUDA alone, i.e. all of them
#                          EMPTY = expose none of them, i.e. run on CPU
#   FABENCH_THREADS        BLAS/OMP threads per aligner process (default 1)
#
# Usage in a driver:  . "$HERE/env.sh"

# The machine's settings, from the same file the CLI reads (KEY=value lines are
# valid shell, which is the point). Sourced first so anything already exported
# still wins: `set -a` exports each assignment, and `${VAR:=default}` below
# only fills what is still unset.
_env_file="${FABENCH_ENV_FILE:-}"
if [ -z "$_env_file" ]; then
  _d=$(pwd)
  while [ -n "$_d" ]; do
    [ -f "$_d/.fabench.env" ] && { _env_file="$_d/.fabench.env"; break; }
    [ "$_d" = "/" ] && break
    _d=$(dirname "$_d")
  done
fi
if [ -n "$_env_file" ] && [ -f "$_env_file" ]; then
  # Fill only what is NOT already set, for EVERY key.
  #
  # This used to be `set -a; . file` with two variables stashed and restored by
  # hand, which meant the documented rule -- an exported variable always wins --
  # held for exactly FABENCH_CUDA_DEVICES and FABENCH_THREADS and silently
  # failed for every other one. `FABENCH_NOISY_ROOT=/x ./augment.sh` was
  # overridden by the file. The Python loader (fabench/envfile.py) has always
  # used os.environ.setdefault, i.e. this rule, for all keys.
  #
  # ${VAR+x} tests SET-ness, not emptiness, so an exported empty
  # FABENCH_CUDA_DEVICES (= run on CPU) is not mistaken for "unset".
  while IFS= read -r _line || [ -n "$_line" ]; do
    _line=${_line#"${_line%%[![:space:]]*}"}          # ltrim
    case "$_line" in ''|'#'*) continue ;; esac
    _line=${_line#export }
    case "$_line" in *=*) ;; *) continue ;; esac
    _k=${_line%%=*}; _v=${_line#*=}
    _k=${_k%"${_k##*[![:space:]]}"}                   # rtrim key
    case "$_k" in ''|*[!A-Za-z0-9_]*) continue ;; esac
    eval "_isset=\${$_k+x}"
    [ -n "$_isset" ] && continue
    _v=${_v#"${_v%%[![:space:]]*}"}; _v=${_v%"${_v##*[![:space:]]}"}
    case "$_v" in
      \"*\") _v=${_v#\"}; _v=${_v%\"} ;;
      \'*\') _v=${_v#\'}; _v=${_v%\'} ;;
    esac
    export "$_k=$_v"
  done < "$_env_file"
  unset _line _k _v _isset
fi

# GPUs. Deliberately NOT defaulted to a device list: an explicit default like
# "0,1,2,3" silently caps a box that has more, and claims devices that do not
# exist on a box that has fewer or none (where a tool then fails confusingly
# rather than running on CPU). Unset means "whatever CUDA finds", which is the
# correct answer on every machine; set it to pin a sweep to specific cards.
#
# To put ONE tool on ONE card, pass --device cuda:N through gen_config.py (see
# run_evals_parallel.sh) instead of hiding cards from the whole sweep.
#
# ${VAR+x} tests SET-ness, not emptiness: an empty value is the documented way
# to tell CUDA to expose no device at all, so `-n "${VAR:-}"` would quietly
# turn a deliberate CPU-only setting back into "use every GPU".
if [ -n "${FABENCH_CUDA_DEVICES+x}" ]; then
  export CUDA_VISIBLE_DEVICES="$FABENCH_CUDA_DEVICES"
fi

# Threads. Pinned to 1 by default: without it each aligner spawns threads
# across every core and a multi-tool sweep thrashes -- measured 40x throughput
# loss on a 48-core box. Raise it only when running ONE tool at a time.
FABENCH_THREADS="${FABENCH_THREADS:-1}"
export OMP_NUM_THREADS="$FABENCH_THREADS"
export MKL_NUM_THREADS="$FABENCH_THREADS"
export OPENBLAS_NUM_THREADS="$FABENCH_THREADS"
