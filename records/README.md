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
has heard those speakers before. The leaderboard answers four questions for
every Track 1 row, from what each system's authors published. The table below
gives the answers, and the four columns are explained under it.

| Answer | Mark | What it tells you |
|---|---|---|
| Yes | dark yellow triangle | The authors say the system used that audio in that way |
| Not disclosed | light yellow triangle | The authors do not list the data, or do not say which part of TIMIT or Buckeye they used |
| No | green check mark | The authors list the data, or rule out both corpora, and show no such use |

| System | Training recipe released? | Used training set for training? | Used dev set for training? | Used test set for training or tuning? | Why |
|---|---|---|---|---|---|
| BFA | No | No* | No* | Not disclosed | A LibriSpeech model whose default setting was chosen on TIMIT and Buckeye, part not named |
| Charsiu | Yes | No | No | No | LibriSpeech only |
| CrisperWhisper | No | Not disclosed | Not disclosed | Not disclosed | Used TIMIT for its word timing and to choose its alignment heads, without naming the part |
| ElevenLabs-FA | No | Not disclosed | Not disclosed | Not disclosed | Not stated |
| MAPS | Yes | Yes | Yes | Yes | Trained on TIMIT's training set and on most Buckeye speakers, 7 of the 8 test speakers included, and picked its model on the eighth |
| Meta MMS-FA | No | No* | No* | No* | Itemized, and neither corpus is in it |
| Meta UnitY2 | No | Not disclosed | Not disclosed | Not disclosed | Internet speech, not itemized |
| Montreal-FA | Yes | No | No | No | LibriSpeech only |
| NeuFA | Yes | Yes | Yes | Yes | Trained on 22 of the 24 Buckeye train speakers, 7 of the 8 dev speakers and 7 of the 8 test speakers |
| NVIDIA NeMo-FA | Yes | No | No | No | Itemized, and neither corpus is in it |
| nyra-FA | No | No* | No* | Not disclosed | Not trained on either corpus. Its paper chose parts of its design by results on TIMIT and Buckeye, with no separate dev set, and does not name the parts |
| PocketSphinx | No | Not disclosed | Not disclosed | Not disclosed | Its en-us model names no corpus |
| Qwen3-FA | No | Not disclosed | Not disclosed | Not disclosed | Not itemized |
| rumblex | No | Not disclosed | Not disclosed | Not disclosed | Its speech model states no data. Its own boundary head saw LibriSpeech only |
| stable-ts | No | Not disclosed | Not disclosed | Not disclosed | Whisper's web audio, not itemized |
| TorchAudio | Yes | No | No | No | LibriSpeech only |
| WhisperX | Yes | No | No | No | LibriSpeech only |
| Zyphra FuseAlign | No | No* | No* | No* | Zyphra states that no TIMIT or Buckeye audio is in it |
| Olewave Olign v1 (unranked) | No | Not disclosed | Not disclosed | Not disclosed | Olewave does not disclose Olign's training data. The row is unranked |

\* Self-claimed. The training recipe is not released, so this No rests on the
authors' own statement, and nobody outside can check it.

| Column | What it asks |
|---|---|
| Training recipe released? | Are the code and configuration that trained the released model public, so anyone can check what data it used? |
| Used training set for training? | Was the system trained on TIMIT's training set, or on FA-Bench's 24 Buckeye train speakers? |
| Used dev set for training? | Was the system trained on TIMIT's 50 dev speakers, or on FA-Bench's 8 Buckeye dev speakers? |
| Used test set for training or tuning? | Was the system trained or tuned on TIMIT's core test, or on FA-Bench's 8 Buckeye test speakers? |

Tuning means choosing a checkpoint, a design or a default setting by its score.
The dev set exists for tuning, so only the last column counts it.

Every answer is for the version on the leaderboard, as checked in November
2026. FA-Bench checks a system again whenever that version changes.
The quotes and links behind every answer are in
[timit_buckeye_use.md](timit_buckeye_use.md), and the full research is in
[info_research.md](info_research.md).

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
