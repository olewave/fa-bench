#!/usr/bin/env bash
# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

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
# READS the kaldi data dirs under <ref>/data/golden/<split>, whose wav.scp
# encodes the exact ffmpeg pipeline, `adelay` pad included, and whose line
# order is part of the seed. datadirs.py writes them from the tracked split
# lists, byte for byte as the published build had them.
#
# Output: real .wav files under
#   $OUT/{TIMIT,Buckeye}/noisy/<type>/<utt_id>.wav   (OUT defaults to data/noisy)
# so the existing split lists index them unchanged.
#
# THE OUTPUT IS PADDED AND MUST NOT BE SCORED AS IT IS: every file is its clean
# source plus 475 ms at EACH end, noise included. shadow_root.py cuts it back to
# the clean samples and length, and every noisy evaluation reads through that.
# See make_noisy.py for the whole story, including why the pad stays here.
set -uo pipefail

REF=${REF:-}                      # holds data/golden/<split>/
FB=${FB:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}
MUSAN=${MUSAN:-data/musan/musan}
RIRS=${RIRS:-data/RIRS_NOISES}
OUT=${OUT:-data/noisy}
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
# Kaldi's wsj utils, from the tools/kaldi submodule unless UTILS names others
ln -sfn "${UTILS:-$FB/tools/kaldi/egs/wsj/s5/utils}" "$STAGE/utils"
ln -sfn "$RIRS" "$STAGE/RIRS_NOISES"
# cd BEFORE sourcing path.sh: path.sh ends with
#   for _d in steps utils; do [ -e "$_d" ] || ln -sfn $KALDI_ROOT/egs/wsj/s5/$_d "$_d"; done
# so sourcing it from the caller's cwd dropped `steps`/`utils` symlinks into
# the FA-Bench repo root. A later `git mv ... utils/` then wrote THROUGH that
# link into the Kaldi checkout and git committed the link instead of the
# files. The stage is where those symlinks are actually wanted.
cd "$STAGE"
[ -f "$REF/path.sh" ] && . "$REF/path.sh"

# ---- MUSAN as kaldi dirs (once) --------------------------------------------
if [ ! -f "$WORK/musan_noise/wav.scp" ]; then
  echo "== preparing MUSAN"
  "$STAGE"/steps/data/make_musan.sh --sampling-rate 16000 "$MUSAN" "$WORK" || exit 1
  # Same reason as the corpus dirs: get_utt2dur.sh is broken in this checkout.
  # MUSAN wav.scp holds bare paths, so utt2dur.py reads the headers directly.
  for n in speech noise music; do
    "${FABENCH_PY:-$FB/.venv/bin/python}" "$FB/fabench/dataprep/noisemix/utt2dur.py" \
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
    "${FABENCH_PY:-$FB/.venv/bin/python}" "$FB/fabench/dataprep/noisemix/utt2dur.py" "$src/wav.scp" "$src/utt2dur"
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
    "${FABENCH_PY:-$FB/.venv/bin/python}" "$FB/fabench/dataprep/noisemix/materialise.py" \
        "$dst/wav.scp" "$final" "$STAGE" "$NJ"
    made=$(ls "$final" 2>/dev/null | wc -l)
    echo "   $made files in $final"
    touch "$dst/.done"
  done
done
echo "NOISY_BUILD_DONE"
