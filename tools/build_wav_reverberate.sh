#!/usr/bin/env bash
# Build ONLY the Kaldi pieces the noise pipeline needs, from the pinned
# submodule at fa-bench/tools/kaldi.
#
# WHY A SUBSET. `fabench/dataprep/noisemix/kaldi/` vendors the Python that decides HOW
# mixing is parameterised, but the actual DSP is `wav-reverberate`, a C++
# binary. Taking that from whatever Kaldi happens to be on PATH leaves the one
# component that touches every sample outside version control -- unacceptable
# for a test set. This closes that gap without carrying a full Kaldi build.
#
# MEASURED SCOPE (why not `make` everything):
#   featbin ADDLIBS  -> hmm feat transform gmm tree util matrix base  = 137 MB
#   a full src build                                                  =  26 GB
#   fst:: symbols in the finished binary                              =   0
#   runtime deps                                                      = MKL only
#
# So the binary is a small corner of Kaldi. OpenFST must still be built first --
# base/, tree/ and hmm/ include `fst/` headers (4 files) even though none of its
# symbols survive into the binary. That header dependency, not the binary, is
# what makes this take a while.
#
# -j4 by default: this box is RAM-bound and heavier parallelism has OOM'd
# compiles here before.
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
KALDI=${KALDI:-$ROOT/tools/kaldi}
NJ=${NJ:-4}
# BLAS selection, auto-detected:
#   * Intel CPU with MKL installed -> MKL   (fastest here, and what the existing
#                                            reference binary links)
#   * anything else                -> OPENBLAS, built in tools/ if absent
#
# MKL is Intel-specific and separately licensed, so it must NOT be a hard
# requirement: a researcher on AMD, or without MKL, has to be able to build
# this. Override with MATHLIB=OPENBLAS or MATHLIB=MKL.
#
# NOTE: a different BLAS reorders floating-point ops, so audio built with
# OpenBLAS may differ from MKL-built audio by ulps. Both are correct; see
# verify_binary.sh before assuming a mismatch is a bug.
if [ -z "${MATHLIB:-}" ]; then
  if grep -qi "GenuineIntel" /proc/cpuinfo 2>/dev/null && \
     { [ -d /opt/intel/mkl ] || [ -n "${MKLROOT:-}" ]; }; then
    MATHLIB=MKL
  else
    MATHLIB=OPENBLAS
  fi
fi

[ -d "$KALDI/src" ] || {
  echo "no kaldi at $KALDI -- run: git submodule update --init --depth 1 tools/kaldi" >&2
  exit 1; }

LIBS="base matrix util tree gmm transform feat hmm"

# OpenFST is NOT linked by wav-reverberate -- the finished binary has zero
# fst:: symbols and no libfst in ldd. It is built only because kaldi's
# src/configure reads $FSTROOT/Makefile for a version string and refuses to
# run without it. Nothing here uses FSTs.
echo "== 1/3 tools (OpenFST) -- ONLY to satisfy src/configure's version probe"
if [ ! -f "$KALDI"/tools/openfst/lib/libfst.a ] && \
   [ ! -f "$KALDI"/tools/openfst/lib/libfst.so ]; then
  make -C "$KALDI/tools" -j"$NJ" openfst
else
  echo "   openfst already built"
fi

echo "== 2/3 configure src"
if [ ! -f "$KALDI/src/kaldi.mk" ]; then
  case "$MATHLIB" in
    OPENBLAS)
      # Build OpenBLAS in tools/ if the system has no usable one.
      if [ ! -d "$KALDI/tools/OpenBLAS/install" ] && \
         ! ls /usr/lib*/libopenblas* /usr/lib/*/libopenblas* >/dev/null 2>&1; then
        echo "   building OpenBLAS in tools/"
        make -C "$KALDI/tools" -j"$NJ" openblas
      fi
      ( cd "$KALDI/src" && ./configure --shared --use-cuda=no --mathlib=OPENBLAS )
      ;;
    MKL)
      ( cd "$KALDI/src" && ./configure --shared --use-cuda=no --mathlib=MKL )
      ;;
    *) echo "unknown MATHLIB=$MATHLIB (want OPENBLAS or MKL)" >&2; exit 1;;
  esac
else
  echo "   already configured (kaldi.mk present)"
fi

echo "== 3/3 build only what featbin/wav-reverberate links"
for l in $LIBS; do
  echo "   -> $l"
  make -C "$KALDI/src/$l" -j"$NJ"
done
make -C "$KALDI/src/featbin" -j"$NJ" wav-reverberate

BIN="$KALDI/src/featbin/wav-reverberate"
[ -x "$BIN" ] || { echo "build produced no binary at $BIN" >&2; exit 1; }
echo
echo "built: $BIN  (mathlib=$MATHLIB)"
"$BIN" 2>&1 | head -2 | sed 's|^|   |'
sha256sum "$BIN" | sed 's|^|   sha256 |'
echo "   BLAS linked:"
ldd "$BIN" 2>/dev/null | grep -iE "blas|mkl|lapack" | sed 's|^|     |' || echo "     (statically linked)"
echo
echo "To use it, put it first on PATH for the noise build:"
echo "   PATH=$KALDI/src/featbin:\$PATH ./fabench/dataprep/noisemix/make_noisy.sh"
