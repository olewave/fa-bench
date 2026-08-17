#!/usr/bin/env bash
# Prove the submodule-built wav-reverberate is equivalent to the one that
# produced the current datasets, BEFORE switching the pipeline over.
#
# Runs one real augmented command with each binary and compares the output
# bytes. Same source (verified identical to upstream) and same inputs should
# give the same samples.
#
# EXPECT A DIFFERENCE IF THE BLAS DIFFERS. The reference binary on this host
# links MKL; build_wav_reverberate.sh now defaults to OpenBLAS for portability
# (MKL is Intel-specific and separately licensed). Different BLAS libraries
# reorder floating-point operations, so bytes may differ by ulps even though
# both are correct. To compare like for like, build with MATHLIB=MKL.
#
# So read the result as: IDENTICAL -> switch freely. DIFFERS -> check whether
# the difference is numerical noise (compare RMS of the difference signal)
# before concluding anything is broken.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
NEW=${NEW:-$ROOT/tools/kaldi/src/featbin/wav-reverberate}
# OLD = a reference wav-reverberate to diff against (any trusted Kaldi build).
OLD=${OLD:-}
WORK=${WORK:-data/noisy_work}
STAGE="$WORK/stage"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

[ -x "$NEW" ] || { echo "no new binary at $NEW (build not finished?)" >&2; exit 1; }
[ -x "$OLD" ] || { echo "no reference binary at $OLD" >&2; exit 1; }

fail=0
for cond in reverb noise music babble; do
  scp="$WORK/timit_core_test_$cond/wav.scp"
  [ -f "$scp" ] || { echo "  $cond: no wav.scp, skipped"; continue; }
  cmd=$(head -1 "$scp" | cut -d' ' -f2- | sed 's/|[[:space:]]*$//')
  for tag in old new; do
    bin=$OLD; [ "$tag" = new ] && bin=$NEW
    # put the chosen binary first on PATH so the pipe picks it up
    ( cd "$STAGE" && PATH="$(dirname "$bin"):$PATH" bash -c "$cmd" ) > "$TMP/$cond.$tag.wav" 2>/dev/null
  done
  a=$(sha256sum < "$TMP/$cond.old.wav" | cut -d' ' -f1)
  b=$(sha256sum < "$TMP/$cond.new.wav" | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then
    echo "  $cond: IDENTICAL ($(stat -c%s "$TMP/$cond.new.wav") bytes)"
  else
    echo "  $cond: DIFFERS  old=${a:0:12} new=${b:0:12}"; fail=1
  fi
done
[ $fail -eq 0 ] && echo "  -> submodule binary is byte-equivalent; safe to switch" \
                || echo "  -> NOT equivalent; do NOT switch without understanding why"
exit $fail
