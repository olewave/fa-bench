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

# Kaldi-style option parsing, sourced by the driver scripts.
#
# The idiom (utils/parse_options.sh in any Kaldi recipe): a script declares its
# knobs as plain shell variables with defaults, sources this, and then
# `--some-option value` on the command line has assigned `some_option=value`.
# Options must be declared first, so a typo is an error instead of a silently
# ignored flag. Anything that is not an option is left in "$@" as a positional.
#
#     stage=1
#     stop_stage=3
#     . "$HERE/parse_options.sh" || exit 1
#
#     if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then ... fi
#
# Dashes map to underscores (`--stop-stage 2` sets `stop_stage=2`), so both
# spellings work for the caller while the script reads one name.
#
# ONE DELIBERATE EXTENSION over Kaldi's version: a variable whose current value
# is `true` or `false` may be given as a bare flag (`--use-noisy-dataset`),
# which sets it true, as well as in Kaldi's explicit form
# (`--use-noisy-dataset true`). The explicit form is what a recipe should use
# in scripts; the bare form exists because a human typing a switch expects it
# to work.

# `[ $# -gt 0 ]` rather than `while true`: a driver running under `set -u`
# (run_all.sh does) aborts on "$1: unbound variable" the moment the options
# run out, which is every invocation that passes no positional arguments.
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      # A driver documents itself in its own header comment.
      sed -n '2,40p' "$0"; exit 0
      ;;
    --*=*)
      echo "$0: options take a space, not '=' (got '$1')" >&2; exit 1
      ;;
    --*)
      name=$(echo "${1#--}" | sed 's/-/_/g')
      if ! eval "[ \"\${${name}+set}\" = set ]"; then
        echo "$0: invalid option '$1' (no such variable '${name}')" >&2
        exit 1
      fi
      old=$(eval echo "\$${name}")
      # Bare boolean. A boolean consumes the NEXT token only when that token
      # is literally true/false; anything else is a positional argument, not a
      # value. (`--use-noisy-dataset mfa` must set the flag and leave `mfa` as
      # the tool, not assign use_noisy_dataset=mfa.)
      if { [ "$old" = true ] || [ "$old" = false ]; } &&
         { [ $# -eq 1 ] || { [ "$2" != true ] && [ "$2" != false ]; }; }; then
        eval "${name}=true"
        shift
      else
        [ $# -ge 2 ] || { echo "$0: option '$1' needs a value" >&2; exit 1; }
        eval "${name}=\$2"
        shift 2
      fi
      ;;
    *)
      break
      ;;
  esac
done

# "$@" now holds the positional arguments only.
true
