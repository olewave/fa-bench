# Results

FA-Bench publishes its numbers on the
**[leaderboard](https://olewave.com/en/leaderboard/fa-bench)**. This
repository holds the scorer, the system adapters and the data loaders. The
result tables of each snapshot and the detailed analysis behind them are kept
by Olewave and are no part of the open release.

## Snapshots

| Snapshot | Systems | Splits |
|---|---|---|
| October 2026 | 19 forced aligners on Track 1, 34 systems on Track 2 | TIMIT dev and core test, Buckeye dev and test |
| September 2026 | 17 forced aligners on Track 1, 32 systems on Track 2 | as October |
| August 2026 | 12 systems | earlier splits and rules, so its numbers do not compare with later snapshots |

Each snapshot covers the phone and word tiers, on clean audio and four
degradations, and names the release that produced it. The Track 2 counts
include the cascades, a Track 1 aligner on the words an ASR recognized. From
release 2.0.0 the leaderboard ranks Track 2 among the systems as shipped and
reports each cascade beside its aligner on Track 1, as the cost of
recognition.

## About TIMIT

TIMIT is read speech from 630 American English speakers. What makes it the gold
here is what ships beside the audio. `.PHN` and `.WRD` give time-aligned labels
on **both** the phone and the word tier, hand-corrected rather than produced by
an aligner. Otherwise the benchmark would be scoring aligners against an
aligner. Two annotated tiers are also why one corpus serves the phone and word
tables without either being derived from the other.

Boundaries are used exactly as annotated, and only the *labels* fold into the
shared TIMIT-39 inventory. Scored here are **dev (50 speakers, 400
utterances)**, a Kaldi convention rather than a TIMIT-defined split, and TIMIT's
own **core test (24 speakers, 192 utterances)**. Both are held out.

## About Buckeye

Buckeye is conversational speech, 40 speakers from Columbus, Ohio, in
open-ended interviews. As TIMIT does, it ships **hand-checked time-aligned
labels on both tiers** (`.phones`, `.words`), with the phonetic tier aligned
automatically and then corrected by hand. What it adds is that the labels
describe speech as *produced*. Talkers reduce, delete and merge, and the
annotators transcribed what was said, so these boundaries are genuinely
ambiguous ones.

The interviews are cut into utterance-sized chunks at silences and interviewer
turns, but **boundary times are used exactly as annotated**. Buckeye ships
**no official split**. These are an FA-Bench convention, **dev (8 speakers,
4,456 utterances)** and **test (8 speakers, 4,513 utterances)**, both held out,
with the other 24 speakers reserved for training.

## Use of TIMIT and Buckeye

FA-Bench scores aligners on TIMIT and Buckeye, so it matters whether a system
has heard those speakers before. In November 2026 FA-Bench checked what the
authors of every Track 1 system published about the version on the leaderboard.
These are the findings.

- **Two systems trained on FA-Bench's Buckeye test speakers.** NeuFA and MAPS
  each trained on 7 of the 8 and chose its final model or step count on the
  eighth, so their Buckeye scores come from speakers they have heard. Neither
  trained on TIMIT's test speakers, so their TIMIT scores are clean. Buckeye
  ships no official split, and both chose their speakers years before FA-Bench
  drew its own in August 2026.
- **Half the board cannot be checked.** For 9 of the 18 ranked systems, the
  sources do not say enough to rule out FA-Bench's test sets. Six do not itemize
  their training data. Three used TIMIT or Buckeye to build or tune the system
  without naming which part. These are nyra-FA, BFA and CrisperWhisper.
- **Seven systems are clean on all three questions.** Montreal-FA, Charsiu,
  WhisperX, TorchAudio and NVIDIA NeMo-FA publish the recipe that shows it.
  Zyphra FuseAlign and Meta MMS-FA state it without a public recipe.
- **Most answers rest on trust.** Only 7 of the 18 systems release the code and
  configuration that trained them. For the rest, nobody outside can check what
  went in.

Olewave makes both FA-Bench and Olign. It does not disclose Olign's training
data, and Olign is listed unranked.

FA-Bench asks every system, and every new submission, to keep the test set
clean. Train only on the training set, choose checkpoints and settings on the
dev set, keep the test set for the final score, and publish the recipe.

The answer for every system, with the source behind it, is in
[timit_buckeye_use.md](timit_buckeye_use.md). Every quote, and the speaker
overlaps FA-Bench measured, is in [info_research.md](info_research.md). The
leaderboard shows the same answers beside each row.

## The four conditions

All four reproduce Kaldi's
[`egs/voxceleb/v2/run.sh`](https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh)
exactly rather than an invented SNR sweep. Three mix in
[MUSAN](https://www.openslr.org/17/) (Snyder, Chen & Povey,
[arXiv 1510.08484](https://arxiv.org/abs/1510.08484)), about 109 hours of
**recorded audio** rather than a synthetic spectral profile. The fourth
convolves room impulse responses and adds nothing.

| Condition | Source | What it is |
|---|---|---|
| Reverb | Simulated RIRs, 0.5 smallroom + 0.5 mediumroom | Convolution rather than mixing. Energy smears forward in time, so a boundary's label time is unchanged but the acoustic evidence for it has moved |
| Noise | MUSAN noise, 930 recordings, 6 h 07 m | Technical sounds such as a dial tone or a button press, and ambient ones such as thunder or a city street |
| Music | MUSAN music, 660 tracks | Western art music and popular genres, annotated for vocals |
| Babble | MUSAN speech, 60 h 26 m | LibriVox recordings and US government archives, so the overlay is **real talkers** rather than shaped noise |

**Every degraded file is exactly as long as its clean source.** The recipe pads
each file by 475 ms at both ends before degrading it, and both pads are cut off
before any system hears it. [`datasets/prep/README.md`](../datasets/prep/README.md)
has the exact commands.

## Reproducing a snapshot

`tests/repro/` rebuilds every headline number of the October 2026 snapshot from
the frozen system outputs behind it and checks each row against the sha256 of
the published row, in `tests/repro/202610/headline_sha256.json`. The check is
exact to the last digit while the numbers themselves stay on the leaderboard.
The system outputs carry the corpora's transcripts, so they stay on local disks
and the test skips without them.
