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

# Build the four Kaldi noise conditions for TIMIT and Buckeye.
#
# Follows Kaldi's egs/voxceleb/v2/run.sh exactly -- same scripts, same
# parameters -- so these conditions match what the field trains on rather than
# an invented SNR sweep:
#   https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh
#
#   reverb   simulated RIRs 0.5 smallroom + 0.5 mediumroom, rvb-prob 1,
#            pointsource/isotropic noise probability 0  (reverb ONLY)
#   noise    MUSAN noise,  --fg-interval 1  --fg-snrs 15:10:5:0
#   music    MUSAN music,  --bg-snrs 15:10:8:5      --num-bg-noises 1
#   babble   MUSAN speech, --bg-snrs 20:17:15:13    --num-bg-noises 3:4:5:6:7
#
# REUSES the kaldi data dirs the gold-prep recipe already built
# (<recipe>/data/golden/<split>), because their wav.scp already encodes the
# exact ffmpeg pipeline -- including the `adelay` pad -- that produced the audio
# the GOLD ALIGNMENTS were made against. Rebuilding them here would risk a
# different pad and silently shift every boundary.
#
# Output: real .wav files under
#   /scratch/data/speech/english/{TIMIT,Buckeye}/noisy/<type>/<utt_id>.wav
# so the existing split lists index them unchanged.
set -uo pipefail

REF=${REF:-}                      # a Kaldi-style egs dir with path.sh
FB=${FB:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}
MUSAN=${MUSAN:-/scratch/data/speech/audio/musan}
RIRS=${RIRS:-/scratch/data/speech/audio/RIRS_NOISES}
OUT=${OUT:-/scratch/data/speech/english}
WORK=${WORK:-data/noisy_work}
NJ=${NJ:-16}
# No timit_full_test: removed as a strict superset of dev + core_test.
SPLITS=${SPLITS:-"timit_train timit_dev timit_core_test buckeye_train buckeye_dev buckeye_test"}
# TYPES was hardcoded in the `for` below; parameterised so this and
# make_noisy.py expose the same knobs (the equivalence test drives both).
TYPES=${TYPES:-"reverb noise music babble"}

# Runs from a staging tree built around VENDORED kaldi scripts
# (fabench/dataprep/noisemix/kaldi -- see its PROVENANCE.md for the upstream commit and the
# single Python-3.12 patch). Vendored rather than symlinked so a rebuild months
# from now produces the same audio: the shared checkout can move, and did
# contain committed merge conflicts.
#
# The stage still exists for two reasons that are properties of the recipe, not
# of the checkout:
#   * reverb commands reference RIRS_NOISES/... RELATIVELY, so cwd must contain
#     that symlink;
#   * kaldi scripts resolve `utils/` and `steps/` relative to cwd.
# `utils/` stays a symlink to the live tree -- large, shared, and its
# fix_data_dir.sh conflict is now fixed upstream, so pinning it would refreeze
# a bug.
mkdir -p "$WORK"
STAGE="$WORK/stage"
mkdir -p "$STAGE"
ln -sfn "$FB/fabench/dataprep/noisemix/kaldi/steps" "$STAGE/steps"
ln -sfn "$REF/../../pkaldi/egs/wsj/s5/utils" "$STAGE/utils" 2>/dev/null || true
# the tools/kaldi submodule ships the same wsj utils
[ -e "$STAGE/utils" ] || ln -sfn "$FB/tools/kaldi/egs/wsj/s5/utils" "$STAGE/utils"
ln -sfn "$RIRS" "$STAGE/RIRS_NOISES"
# cd BEFORE sourcing path.sh: path.sh ends with
#   for _d in steps utils; do [ -e "$_d" ] || ln -sfn $KALDI_ROOT/egs/wsj/s5/$_d "$_d"; done
# so sourcing it from the caller's cwd dropped `steps`/`utils` symlinks into
# the FA-Bench repo root. A later `git mv ... utils/` then wrote THROUGH that
# link into pkaldi and git committed the link instead of the files. The stage
# is where those symlinks are actually wanted.
cd "$STAGE"
. "$REF/path.sh"

# ---- MUSAN as kaldi dirs (once) --------------------------------------------
if [ ! -f "$WORK/musan_noise/wav.scp" ]; then
  echo "== preparing MUSAN"
  "$STAGE"/steps/data/make_musan.sh --sampling-rate 16000 "$MUSAN" "$WORK" || exit 1
  # Same reason as the corpus dirs: get_utt2dur.sh is broken in this checkout.
  # MUSAN wav.scp holds bare paths, so utt2dur.py reads the headers directly.
  for n in speech noise music; do
    "$FB/.venv/bin/python" "$FB/fabench/dataprep/noisemix/utt2dur.py" \
        "$WORK/musan_$n/wav.scp" "$WORK/musan_$n/reco2dur"
  done
fi

for split in $SPLITS; do
  raw="$REF/data/golden/$split"
  [ -f "$raw/wav.scp" ] || { echo "skip $split (no wav.scp)"; continue; }

  # NORMALISE a copy. The gold-prep recipe writes its data dirs TAB-separated
  # (`f"{utt}\t{cmd}"`), but kaldi splits on whitespace-then-space and produced
  # reco2dur keys like "dr1_felc0_si1386\tffmpeg" -- every lookup then missed.
  # Convert the first tab to a space; leave the gold-prep recipe's own dirs untouched
  # since they work for it.
  src="$WORK/src_$split"
  if [ ! -f "$src/.norm" ]; then
    mkdir -p "$src"
    for f in wav.scp utt2spk spk2utt text segments reco2spk; do
      [ -f "$raw/$f" ] && sed 's/\t/ /' "$raw/$f" > "$src/$f"
    done
    [ -f "$src/spk2utt" ] || "$STAGE"/utils/utt2spk_to_spk2utt.pl "$src/utt2spk" > "$src/spk2utt" 2>/dev/null
    # durations are required by augment_data_dir.py. NOT via
    # utils/data/get_utt2dur.sh: it runs wav-to-duration, which reads the wav
    # header then closes the pipe -- ffmpeg exits nonzero and kaldi treats that
    # as fatal. (That script's split_data.sh --per-utt is also version-mismatched
    # in this checkout.) utt2dur.py derives the duration from the source header
    # plus the adelay/apad values already encoded in the wav.scp command.
    "$FB/.venv/bin/python" "$FB/fabench/dataprep/noisemix/utt2dur.py" "$src/wav.scp" "$src/utt2dur"
    cp "$src/utt2dur" "$src/reco2dur"
    touch "$src/.norm"
  fi
  case "$split" in timit*) corpus=TIMIT;; buckeye*) corpus=Buckeye;; esac

  for type in $TYPES; do
    dst="$WORK/${split}_${type}"
    final="$OUT/$corpus/noisy/$type"
    mkdir -p "$final"
    if [ -f "$dst/.done" ]; then echo "  $split/$type already built"; continue; fi
    echo "== $split / $type"
    rm -rf "$dst"

    case "$type" in
      reverb)
        rvb=(); rvb+=(--rir-set-parameters "0.5, $RIRS/simulated_rirs/smallroom/rir_list")
                rvb+=(--rir-set-parameters "0.5, $RIRS/simulated_rirs/mediumroom/rir_list")
        "$STAGE"/steps/data/reverberate_data_dir.py "${rvb[@]}" \
          --speech-rvb-probability 1 \
          --pointsource-noise-addition-probability 0 \
          --isotropic-noise-addition-probability 0 \
          --num-replications 1 --source-sampling-rate 16000 \
          "$src" "$dst" ;;
      noise)
        "$STAGE"/steps/data/augment_data_dir.py --utt-suffix "" --fg-interval 1 \
          --fg-snrs "15:10:5:0" --fg-noise-dir "$WORK/musan_noise" "$src" "$dst" ;;
      music)
        "$STAGE"/steps/data/augment_data_dir.py --utt-suffix "" --bg-snrs "15:10:8:5" \
          --num-bg-noises "1" --bg-noise-dir "$WORK/musan_music" "$src" "$dst" ;;
      babble)
        "$STAGE"/steps/data/augment_data_dir.py --utt-suffix "" --bg-snrs "20:17:15:13" \
          --num-bg-noises "3:4:5:6:7" --bg-noise-dir "$WORK/musan_speech" "$src" "$dst" ;;
    esac

    # augment_data_dir.py / reverberate_data_dir.py raise on their closing
    # `utils/fix_data_dir.sh` call because TIMIT utt-ids are `dr1_felc0_si1386`
    # while the speaker is `felc0` -- kaldi wants speaker-ids to be utt-id
    # prefixes, which the gold-prep recipe's prep does not do. wav.scp is fully written
    # before that check, so judge success by the artefact.
    if [ ! -s "$dst/wav.scp" ]; then
      echo "   FAILED: no wav.scp for $split/$type" >&2; continue
    fi

    # wav.scp entries are PIPES; realise them as files. One ffmpeg/sox chain per
    # utterance, NJ at a time -- the pipes each spawn a process, so more than a
    # dozen in parallel thrashes.
    n=$(wc -l < "$dst/wav.scp")
    echo "   materialising $n utts -> $final"
    # Run from $STAGE: reverb commands reference RIRS_NOISES/... relatively.
    "$FB/.venv/bin/python" "$FB/fabench/dataprep/noisemix/materialise.py" \
        "$dst/wav.scp" "$final" "$STAGE" "$NJ"
    made=$(ls "$final" 2>/dev/null | wc -l)
    echo "   $made files in $final"
    touch "$dst/.done"
  done
done
echo "NOISY_BUILD_DONE"
