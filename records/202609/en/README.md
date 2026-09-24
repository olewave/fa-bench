# Results

**September 2026** — 16 forced aligners on Track 1 and 29 systems on Track 2,
TIMIT and Buckeye, phone and word tiers, clean plus four degradations. Of the
Track 2 rows, 13 decode their own words in one step and 16 re-align an ASR
transcript with a Track 1 aligner. Six of the one-step rows are commercial
endpoints rather than open-weight models, and they are marked as such. The
numbers sit with their corpus below; this page is how they were made and how to
read them.

A dated snapshot: fabench protocol, 10 ms grid, bootstrap 95% CI. MAE in ms,
lower better.

## Per-corpus results

Phone-level results live with their corpus, because the failure modes are
corpus-specific and the edit columns are **not** comparable across the two (see
the note under Buckeye). Everything below this section is cross-corpus by
construction.

| Corpus | Tier | Core results | Detailed results |
|---|---|---|---|
| TIMIT (read) | word | [MAE and F1, clean vs noisy](gold/word/timit/README.md) | [Every metric, by condition](gold/word/timit/Details.md) |
| TIMIT (read) | phone | [MAE and F1, clean vs noisy](gold/phone/timit/README.md) | [Every metric, by condition](gold/phone/timit/Details.md) |
| Buckeye (spontaneous) | word | [MAE and F1, clean vs noisy](gold/word/buckeye/README.md) | [Every metric, by condition](gold/word/buckeye/Details.md) |
| Buckeye (spontaneous) | phone | [MAE and F1, clean vs noisy](gold/phone/buckeye/README.md) | [Every metric, by condition](gold/phone/buckeye/Details.md) |

## Word-level

Word results live with their corpus, next to the phone tables:
[TIMIT](gold/word/timit/README.md) · [Buckeye](gold/word/buckeye/README.md).
Every split is in that one table — the word tier has four metrics, so it needs no
separate detailed view.

The word tier uses the same two matching rules as the phone tables below, with
the same opposite blind spots:

| Metrics | Matched to gold by | What that rule cannot charge for |
|---|---|---|
| `MAE (ms)` | **label first** — the same monotonic aligner as the phone tier, then times | a dropped or misrecognised word. It matches nothing, so it exits the average rather than worsening it |
| `P/R`, `F1` | **time only** — within 20 ms, labels ignored | the wrong word. A boundary at the right moment on the wrong word is free |

**No one-step Track 2 system emits a phone tier**, and neither do WhisperX,
Parakeet-TDT or Qwen3-ASR, so the word table is the only one those can appear in
at all. The two-step cascades do emit phones, because the aligner doing the
re-timing has a phone tier of its own.

**Each corpus page splits the word results into two tracks.** Track 1 is forced
alignment on the reference transcript — the system is handed the words and only
its timing is measured. Track 2 is forced alignment on an ASR result: the system
decodes its own words, so its numbers carry recognition error as well, and a
misrecognised word leaves the matched path entirely.

Membership is inferred from where each recipe lives (`evals/timestamp_asrs/`)
rather than declared, so a tool cannot be filed as one thing and installed as
another. Track 2 splits again into one-step rows, where the recognizer times its
own words, and two-step cascades written `<aligner>_on_<asr>`, where a Track 1
aligner re-times an ASR transcript. A cascade's Track 1 counterpart is in the
other table, so the pair measures what the recognition step costs.

**Six one-step rows are commercial endpoints**, not open-weight models:
AssemblyAI, Deepgram, ElevenLabs, Google, IBM and Speechmatics, alongside Olign
on Track 1. They are reported apart from the open-weight rows because the model
behind an endpoint can change without a version number, so a row is a claim
about what a service returned on a date rather than about a checkpoint anyone
can re-run. ElevenLabs was run on the clean cells only, because its prepaid
credit ran out, and its noisy cells are absent rather than failed.

The coverage block below names exactly who was scored, on both tracks: a system
absent from it has not been run, which is a different statement from having done
badly.

The pair of CrisperWhisper rows -- track 2 and track 1 -- is the
**same model** either way — one decoding, one given the reference — so the gap
between them is what the recognition step costs. See `evals/README.md`.

## Phone-level: two metrics, two blind spots — read both

Nothing can be measured until each phone the system produced is matched to a
phone in the gold. The tables use **two different matching rules**, and they
fail in opposite directions:

| Metrics | Matched to gold by | What that rule cannot charge for |
|---|---|---|
| `MAE (ms)`, `t=10`, `S`/`D`/`PER` | **label first** — Levenshtein over phone labels, then the times of whichever pairs it found | a phone the system never emitted. It matches nothing, so it leaves the average entirely instead of worsening it |
| `P/R`, `F1`, `OS`, `R-val` | **time only** — a gold boundary counts as found if some hypothesis boundary lands within 20 ms, whatever it is labelled | a wrong label. A substitution at the right moment is free here |

**MAE is computed on the matched path only**, so skipped phones leave a
system's average rather than being charged for; `Del%` charges for exactly what
MAE drops. **A lower MAE at a higher `Del%` is not necessarily better.**

`P/R`/`F1` use **strict** matching, one hypothesis boundary per reference
boundary (Strgar & Harwath, SLT 2022 — the lenient variant moves precision 3–7
points). `R-val` (Räsänen et al. 2009) separates the over- from
under-segmentation F1 scores identically.

### How each system's phones reach TIMIT-39

Systems do not agree on an alphabet, so every phone is folded into the shared
**TIMIT-39** inventory (Lee & Hon 1989, General American) before anything is
compared. Each system declares a `source`, and that selects the mapping table —
so a Charsiu label and an MFA label become the same symbol, or they are not
comparable at all.

Counts below are the distinct labels each system actually emitted on TIMIT dev,
clean, before folding.

| System | `source` | Mapping | Labels emitted |
|---|---|---|---|
| BFA | `ipa` | `IPA_TO_39` | 60 |
| Charsiu | `arpabet` | `ARPABET_TO_39` | 40 |
| FALCON | `arpabet` | `ARPABET_TO_39` | 39 |
| MAPS | `arpabet` | `ARPABET_TO_39` | 65 |
| MFA 2.0 · MFA 3.4 | `mfa` | `ARPABET_TO_39` | 68 |
| Olign | `arpabet` | `ARPABET_TO_39` | 39 |
| TorchAudio | `ipa` | `IPA_TO_39` | 59 |

Every other scored system emits words only and never enters a phone table. They
are not listed here, because the list grows with every word-tier system added
and the table above already says which systems have a phone tier at all.

**A note on where TorchAudio's phones come from.** Its phone tier is aligned by
`wav2vec2-lv-60-espeak-cv-ft`, whose vocabulary is 392 eSpeak IPA symbols, and
the sequence it aligns is one **it derives itself from the transcript** with
eSpeak G2P — the same phonemizer that model was trained against. That is the
same contract as every other aligner here: words in, phones worked out, phone
boundaries out.

It is worth saying plainly because an earlier revision of this benchmark got it
wrong. TorchAudio was the only system passed the reference phone sequence as its
alignment target, which meant it could not substitute or insert a phone — its
`S` and `I` columns were 0.0 by construction rather than by merit, and its tier
was withheld from publication once that was found. Deriving the sequence from
the transcript is what makes the row comparable. The effect is confined to which
phones are proposed, not where they land: boundary MAE moved 31.2 → 32.0 ms on
TIMIT dev clean, while PER went 20.0 → 33.9 %.

Two properties were checked before the numbers were trusted: every token eSpeak
emits is present in the model vocabulary (100 % over 400 transcripts from both
corpora — stress marks are suppressed, since eSpeak's stressed forms `ˈiː`,
`ˈaɪ`, `ˈoʊ` are absent from that vocabulary), and every one folds through
`IPA_TO_39` into TIMIT-39 (0 unmapped of 16,176 tokens). Its sequence is
naturally shorter than the reference — a median 0.83 of the gold phone count on
TIMIT — because eSpeak emits no closures or silences where the corpus marks
`h#`, `dcl`, `gcl`. Those show up honestly as deletions.

The two corpora pull the count in opposite directions, and both are honest.
TIMIT gold is TIMIT-61, of which 19% is silence and stop closures (`h#`, `tcl`,
`kcl`, `dcl`, `pcl`, `bcl`, `gcl`, `epi`) that have no acoustic target and are
correctly proposed by nobody — so a G2P sequence runs a median **0.83** of the
gold count there. Buckeye marks no closures but transcribes spontaneous speech
*as reduced*, while eSpeak proposes the canonical form, so the same system runs
**1.04** of gold. The first shows up as deletions, the second as insertions and
substitutions; neither is the aligner mis-timing anything.

Two guards sit under this. `gate#10` fails any published phone tier covering
less than 65% of the reference, and the worker refuses an utterance whose G2P it
can map to under 95% of the model vocabulary, naming the tokens it could not —
a safety net rather than a routine path, since measured coverage is 100%.

### Sub% / Del% / Ins% / PER% — why a phone left the matched path

A count of unmatched gold phones cannot say **why**. A **substitution** still
puts a boundary near the right place with the wrong label; a **deletion**
contributes none at all.

Every gold phone is matched, substituted or deleted, so on the gold side the
decomposition is exact:

```
matched% + Sub% + Del% = 100%      (to rounding)
```

`Ins%` has no gold counterpart — it is normalised by the gold count, per the
PER/WER convention — so it sits **outside** that identity, and
`PER% ≠ 100 − matched%` by exactly `Ins%`. `PER% = Sub% + Del% + Ins%`.

**Why most systems repeat the same S/D/I in all five conditions.** In the
Details tables these columns are usually flat across clean and the four
degradations, and that is correct rather than a copied cell. A forced aligner
that emits exactly the phone sequence it derived from the transcript makes no
label decision the audio can influence — noise moves *where* the boundaries
land, not *which* phones were proposed. So its edit columns are a property of
its lexicon or G2P against the corpus's transcription conventions, and its
degradation shows up in MAE, F1 and the threshold accuracies instead. MFA is the
exception, and instructively so: it carries pronunciation variants and chooses
between them acoustically, which is why its `S` drifts (14.0 → 14.4 on Buckeye
dev) as conditions worsen.

## Noise robustness

Every table on a corpus page already spans the degraded conditions, so there is
no separate noise section: **Clean** against a single **Noisy** mean, the
per-condition breakdown in Details. Same ground truth, same splits, same tools;
only the acoustics differ. All four reproduce Kaldi's
[`egs/voxceleb/v2/run.sh`](https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh)
exactly, not an invented SNR sweep.

### What the four conditions are

Three mix in
[MUSAN](https://www.openslr.org/17/) (Snyder, Chen & Povey,
[arXiv:1510.08484](https://arxiv.org/abs/1510.08484)), ~109 hours of **recorded
audio** rather than a synthetic spectral profile; the fourth convolves room
impulse responses and adds nothing.

| Condition | Source | What It Actually Is |
|---|---|---|
| Reverb | Simulated RIRs, 0.5 smallroom + 0.5 mediumroom | Convolution, not mixing — energy smears forward in time, so a boundary's label time is unchanged but the acoustic evidence for it has moved |
| Noise | MUSAN noise, 930 recordings, 6 h 07 m | Technical and ambient sound: DTMF tones, cellphone button presses and vibration, dialtones, plus thunder, clapping, car horns, animal calls, and ambient scenes such as walking through a city |
| Music | MUSAN music, 660 tracks | Western art music and popular genres, annotated for vocals |
| Babble | MUSAN speech, 60 h 26 m | LibriVox recordings and US-government archives — an overlay of **real talkers**, not shaped noise |

## Which subset the numbers cover

**These are held-out splits, not whole-corpus passes** — a change from the
previous version of this page.

<!-- BEGIN GENERATED: coverage -->
All **16** aligner-track systems are scored on all **4** splits (Buckeye Dev, Buckeye Test, TIMIT Dev, TIMIT Core-test):

BFA, Charsiu, CrisperWhisper, FALCON, MAPS, MFA 2.0, MFA 3.4, MMS-FA, NeMo-FA 40 ms, NeMo-FA 80 ms, Olign 1.0, Qwen3-FA, stable-ts, TorchAudio, UnitY2, WhisperX.

Scored separately in **track 2** — timestamped ASRs, which decode their own words rather than being given the transcript, so the two tracks never share a leaderboard: Amazon Transcribe, AssemblyAI Universal 3.5, Azure AI Speech, CrisperWhisper, Deepgram Nova-3, ElevenLabs Scribe v2, Google Chirp 2, Google Chirp 2 → Olign 1.0, IBM Watson Large, Parakeet-TDT, Parakeet-TDT → MFA 3.4, Parakeet-TDT → Olign 1.0, Qwen3 → BFA, Qwen3 → Charsiu, Qwen3 → CrisperWhisper, Qwen3 → MAPS, Qwen3 → MFA 2.0, Qwen3 → MFA 3.4, Qwen3 → MMS-FA, Qwen3 → NeMo-FA 40 ms, Qwen3 → NeMo-FA 80 ms, Qwen3 → Olign 1.0, Qwen3 → Qwen3-FA, Qwen3 → stable-ts, Qwen3 → TorchAudio, Qwen3 → UnitY2, Qwen3 → WhisperX, Speechmatics enhanced, TorchAudio (ASR), Whisper large-v3, Whisper → WhisperX, Whisper-timestamped.
<!-- END GENERATED: coverage -->

Two changes make the old numbers incomparable rather than merely superseded:

1. **TIMIT's SA sentences are now excluded everywhere.** The corpus documentation
   states they must not be used for training or test. `full_test` therefore means
   **1,344**, not the 1,680 previously reported, and the old `all` (6,300) cell
   no longer exists.
2. **Buckeye is re-split.** The previous stride rule put **4 young and 0 old**
   speakers in test — it measured a single age group. The split is now stratified
   on the corpus's own sex × age design: 24/8/8 speakers, cells 6/6/6/6 in train
   and 2/2/2/2 in each of dev and test.

Membership is committed in `datasets/languages/en/{timit,buckeye}/split/*.list`, one
`<speaker_id> <utterance_id>` per line.

## Aligner provenance

### Versions as evaluated

Read from the installed environment, not typed by hand: lock files,
conda-meta, and the git checkouts. Release dates are PyPI `upload_time` for the
exact pinned version, or the commit date for git-installed tools. Regenerate
with `evals/gen_provenance.py`.

<!-- BEGIN GENERATED: provenance -->
**FA-Bench release:** commit `ed5306da44a3`, branch `paper` (2026-09-16) + uncommitted changes

| System | Version | Commit | Released |
|---|---|---|---|
| BFA | 1.1.5 | — | 2026-06-05 |
| Charsiu | (git) | `13a69f2a22ca` | 2022-09-18 |
| CrisperWhisper-FA | 2.0.2 | — | 2026-08-06 |
| MAPS | (git) | `bf797f434b83` | 2026-02-23 |
| MFA 2.0 | 2.0.6 | — | 2022-08-08 |
| MFA 3.4 | 3.4.1 | — | 2026-07-11 |
| Olign | v1.0.0 | — | undisclosed |
| Parakeet-TDT | 2.7.3 | — | 2026-04-23 |
| Qwen3 | 0.0.6 | — | 2026-01-30 |
| stable-ts | (git) | `e312072cc024` | — |
| TorchAudio | 2.8.0 | — | 2025-08-06 |
| WhisperX | 3.8.6 | — | 2026-05-25 |
<!-- END GENERATED: provenance -->

### Training data and overlap

| System | Paradigm | Training data | Overlap with these splits |
|---|---|---|---|
| MFA 3.4 | HMM-GMM (Kaldi) | LibriSpeech 982 h | none |
| MFA 2.0.6 | HMM-GMM (Kaldi) | LibriSpeech | none |
| Charsiu | wav2vec2 frame classifier | Common Voice etc. | none |
| BFA | CUPE + CTC | LibriSpeech-1000 | none |
| WhisperX | wav2vec2 CTC alignment | LibriSpeech 960 h | none |
| MAPS | DNN + interpolation | TIMIT + Buckeye | ⚠ **Buckeye only**, see below |
| Olign | Undisclosed | Undisclosed | none |

⚠ **MAPS is not on equal footing with the rest, on Buckeye.** Its `timbuck`
models are trained on TIMIT and Buckeye, and its
[model card](https://github.com/MasonPhonLab/MAPS) states the split exactly:
Buckeye speaker 4 held out for validation, speakers 27, 38, 39 and 40 for test,
plus the TIMIT test set. Buckeye ships no official split, so FA-Bench chose a
different one and the two disagree. Seven of the eight speakers in each of our
Buckeye splits are in its training set, so those rows are not held-out results.
Its TIMIT rows are: both our TIMIT splits are carved from TIMIT `TEST/`, which
it did not train on.

This is two projects splitting an unsplit corpus differently, not a
disclosure failure. The overlap is quantified here only because MAPS stated
its split; for a system that does not, the same table would have to say
"undisclosed".

Every other row, Olign included, is held out: no system was trained on the
splits it is scored on. One distinction the table cannot show is that MFA,
Charsiu, BFA and WhisperX never saw either corpus in any form, while a
same-corpus-trained system meets familiar channel, recording conditions and
annotation conventions even on speakers it has never heard. That is worth a
reader's attention; it is not an overlap.

Beyond its input/output contract — audio plus a reference transcript in, word and
phone boundaries with confidence out — **Olign is undisclosed**: architecture,
training data, and configuration alike. Its row reports the shipped system, as
any system would be entered.

## Reproducing

Every alignment is persisted with the tool that produced it, at
`evals/<kind>/<tool>/en/<corpus>/<subset>/<condition>/hyp.jsonl`, so a metric
change is a **rescore, not a re-run**:

```
evals/run_evals.sh [tool ...]     # align + score, one run per (cell, tool)
evals/rescore_all.sh              # rebuild every leaderboard from the saved hyp
evals/publish_records.py          # snapshot the current numbers into records/
```

Per-tool environments and the exact parameters are in `evals/<kind>/<tool>/`.
