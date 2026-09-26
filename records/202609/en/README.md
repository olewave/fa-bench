# Results

**September 2026.** 17 forced aligners on Track 1 and 32 systems on Track 2,
on TIMIT and Buckeye, phone and word tiers, clean plus four degradations. Of
the Track 2 rows, 13 decode their own words in one step and 19 re-align an ASR
transcript with a Track 1 aligner. Eight of the one-step rows are commercial
endpoints rather than open-weight models, and they are marked as such. The
numbers sit with their corpus below. This page is how they were made and how
to read them.

This is a dated snapshot, scored under the fabench protocol on a 10 ms grid
with bootstrap 95% CIs. MAE is in ms, and lower is better.

## Per-corpus results

Phone-level results live with their corpus, because the failure modes are
corpus-specific and the edit columns are **not** comparable across the two
(see the note under Buckeye). Everything below this section is cross-corpus by
construction.

| Corpus | Tier | Core results | Detailed results |
|---|---|---|---|
| TIMIT (read) | word | [MAE and F1, clean vs noisy](gold/word/timit/README.md) | [Every metric, by condition](gold/word/timit/Details.md) |
| TIMIT (read) | phone | [MAE and F1, clean vs noisy](gold/phone/timit/README.md) | [Every metric, by condition](gold/phone/timit/Details.md) |
| Buckeye (spontaneous) | word | [MAE and F1, clean vs noisy](gold/word/buckeye/README.md) | [Every metric, by condition](gold/word/buckeye/Details.md) |
| Buckeye (spontaneous) | phone | [MAE and F1, clean vs noisy](gold/phone/buckeye/README.md) | [Every metric, by condition](gold/phone/buckeye/Details.md) |

## Word-level

Word results live with their corpus, next to the phone tables, for
[TIMIT](gold/word/timit/README.md) and [Buckeye](gold/word/buckeye/README.md).
Every split is in that one table, and each condition has its own column on
the Details page beside it.

The word tier uses the same matching rules as the phone tables below.

| Metrics | Matched to gold by | What that rule cannot charge for |
|---|---|---|
| `MAE (ms)` | **label first**, through the same monotonic aligner as the phone tier, then times | a dropped or misrecognised word, or an utterance the system returned nothing for. It matches nothing, so it exits the average rather than worsening it |
| `F1` and the F1 sweep | **label and time**. A boundary counts only when the words on both sides of it match the reference and it lies within the width. The two utterance edges count, against silence, and so does every boundary of an utterance the system returned nothing for | nothing either rule alone lets through. A dropped word costs the boundaries beside it, and a boundary at the right moment on the wrong word scores nothing |
| `P/R` and the time-only `F1`, on Details | **time only**, within 20 ms, labels ignored | the wrong word. A boundary at the right moment on the wrong word is free |

**No one-step Track 2 system emits a phone tier.** On Track 1, neither do
CrisperWhisper, MMS-FA, NeMo-FA, Qwen3-FA, stable-ts, UnitY2 or WhisperX, so
the word table is the only one those can appear in at all. The two-step
cascades do emit phones when the aligner doing the re-timing has a phone tier
of its own.

**Each corpus page splits the word results into two tracks.** Track 1 is
forced alignment on the reference transcript. The system is handed the words
and only its timing is measured. Track 2 is forced alignment on an ASR
result. The system decodes its own words, so its numbers carry recognition
error as well, and a misrecognised word leaves the matched path entirely.

Membership is inferred from where each recipe lives (`evals/timestamp_asrs/`)
rather than declared, so a tool cannot be filed as one thing and installed as
another. Track 2 splits again into one-step rows, where the recognizer times
its own words, and two-step cascades written `<aligner>_on_<asr>`, where a
Track 1 aligner re-times an ASR transcript. A cascade's Track 1 counterpart is
in the other table, so the pair measures what the recognition step costs.

**Eight one-step rows are commercial endpoints** rather than open-weight
models. They are Amazon Transcribe, AssemblyAI, Azure AI Speech, Deepgram,
ElevenLabs, Google, IBM and Speechmatics, alongside Olign on Track 1. They are
reported apart from the open-weight rows because the model behind an endpoint
can change without a version number, so a row is a claim about what a service
returned on a date rather than about a checkpoint anyone can re-run.
ElevenLabs ran out of prepaid credit partway. It has all four clean cells and
the four degradations of both test splits, and its dev noisy cells are absent
rather than failed, so the dev pages show a dash for it.

The coverage block below names exactly who was scored, on both tracks. A
system absent from it has not been run, which is a different statement from
having done badly.

The two CrisperWhisper rows, one on each track, are the **same model**. One
decodes and the other is given the reference, so the gap between them is what
the recognition step costs. See `evals/README.md`.

## Phone-level, two metrics with two blind spots

Nothing can be measured until each phone the system produced is matched to a
phone in the gold. The tables use **two different matching rules**, which
fail in opposite directions, and an F1 that applies both. Read both.

| Metrics | Matched to gold by | What that rule cannot charge for |
|---|---|---|
| `MAE (ms)`, `t=10`, `S`/`D`/`PER` | **label first**, Levenshtein over phone labels, then the times of whichever pairs it found | a phone the system never emitted, or an utterance it returned nothing for. It matches nothing, so it leaves the average entirely instead of worsening it |
| `F1` and the F1 sweep | **label and time**. A boundary counts only when the phones on both sides of it match the reference and it lies within the width. The two utterance edges count, against silence, and so does every boundary of an utterance the system returned nothing for | nothing either rule alone lets through. A skipped phone costs the boundaries beside it, and a substitution at the right moment scores nothing |
| `P/R`, time-only `F1`, `OS`, `R-val`, on Details | **time only**. A gold boundary counts as found if some hypothesis boundary lands within 20 ms, whatever it is labelled | a wrong label. A substitution at the right moment is free here |

**MAE is computed on the matched path only**, so skipped phones leave a
system's average rather than being charged for. `Del%` charges for exactly
what MAE drops. **A lower MAE at a higher `Del%` is not necessarily better.**

The comparison pages report the label-checked `F1`, the one the paper uses.
The time-only `P/R` and `F1` use **strict** matching, one hypothesis boundary
per reference boundary (Strgar & Harwath, SLT 2022). The lenient variant moves
precision by 3 to 7 points. `R-val` (Räsänen et al. 2009) separates the over-
from under-segmentation that F1 scores identically.

### How each system's phones reach TIMIT-39

Systems do not agree on an alphabet, so every phone is folded into the shared
**TIMIT-39** inventory (Lee & Hon 1989, General American) before anything is
compared. Each system declares a `source`, and that selects the mapping
table, so a Charsiu label and an MFA label become the same symbol, or they
are not comparable at all.

Counts below are the distinct labels each system emitted on TIMIT dev, clean,
before folding.

| System | `source` | Mapping | Labels emitted |
|---|---|---|---|
| BFA | `ipa` | `IPA_TO_39` | 60 |
| Charsiu | `arpabet` | `ARPABET_TO_39` | 40 |
| FALCON | `arpabet` | `ARPABET_TO_39` | 39 |
| MAPS | `arpabet` | `ARPABET_TO_39` | 65 |
| MFA 2.0 · MFA 3.4 | `mfa` | `ARPABET_TO_39` | 68 |
| NeuFA | `arpabet` | `ARPABET_TO_39` | 67 |
| Olign | `arpabet` | `ARPABET_TO_39` | 39 |
| TorchAudio | `ipa` | `IPA_TO_39` | 59 |

Every other scored system emits words only and never enters a phone table.
They are not listed here, because the list grows with every word-tier system
added, and the table above already says which systems have a phone tier at
all.

**A note on where TorchAudio's phones come from.** Its phone tier is aligned
by `wav2vec2-lv-60-espeak-cv-ft`, whose vocabulary is 392 eSpeak IPA symbols,
and the sequence it aligns is one **it derives itself from the transcript**
with eSpeak G2P, the same phonemizer that model was trained against. That is
the same contract as every other aligner here. Words go in, phones are worked
out, and phone boundaries come out.

It is worth saying plainly because an earlier revision of this benchmark got
it wrong. TorchAudio was the only system passed the reference phone sequence
as its alignment target, which meant it could not substitute or insert a
phone. Its `S` and `I` columns were 0.0 by construction rather than by merit,
and its tier was withheld from publication once that was found. Deriving the
sequence from the transcript is what makes the row comparable. The effect is
confined to which phones are proposed, and where they land barely moves.
Boundary MAE moved 31.2 → 32.0 ms on TIMIT dev clean, while PER went 20.0 →
33.9 %.

Two properties were checked before the numbers were trusted. Every token
eSpeak emits is present in the model vocabulary (100 % over 400 transcripts
from both corpora, with stress marks suppressed, since eSpeak's stressed forms
`ˈiː`, `ˈaɪ`, `ˈoʊ` are absent from that vocabulary), and every one folds
through `IPA_TO_39` into TIMIT-39 (0 unmapped of 16,176 tokens). Its sequence
is naturally shorter than the reference, a median 0.83 of the gold phone count
on TIMIT, because eSpeak emits no closures or silences where the corpus marks
`h#`, `dcl`, `gcl`. Those show up honestly as deletions.

The two corpora pull the count in opposite directions, and both are honest.
TIMIT gold is TIMIT-61, of which 19% is silence and stop closures (`h#`,
`tcl`, `kcl`, `dcl`, `pcl`, `bcl`, `gcl`, `epi`) that have no acoustic target
and are correctly proposed by nobody, so a G2P sequence runs a median **0.83**
of the gold count there. Buckeye marks no closures but transcribes spontaneous
speech *as reduced*, while eSpeak proposes the canonical form, so the same
system runs **1.04** of gold. The first shows up as deletions, the second as
insertions and substitutions. Neither is the aligner mis-timing anything.

Two guards sit under this. `gate#10` fails any published phone tier covering
less than 65% of the reference, and the worker refuses an utterance whose G2P
it can map to under 95% of the model vocabulary, naming the tokens it could
not. That is a safety net rather than a routine path, since measured coverage
is 100%.

### Sub, Del, Ins and PER, why a phone left the matched path

A count of unmatched gold phones cannot say **why**. A **substitution** still
puts a boundary near the right place with the wrong label. A **deletion**
contributes none at all.

Every gold phone is matched, substituted or deleted, so on the gold side the
decomposition is exact.

```
matched% + Sub% + Del% = 100%      (to rounding)
```

`Ins%` has no gold counterpart. It is normalised by the gold count, per the
PER and WER convention, so it sits **outside** that identity, and
`PER% ≠ 100 − matched%` by exactly `Ins%`. `PER% = Sub% + Del% + Ins%`.

**Why most systems repeat the same S/D/I in all five conditions.** In the
Details tables these columns are usually flat across clean and the four
degradations, and that is correct rather than a copied cell. A forced aligner
that emits exactly the phone sequence it derived from the transcript makes no
label decision the audio can influence. Noise moves *where* the boundaries
land and leaves *which* phones were proposed alone. So its edit columns are a
property of its lexicon or G2P against the corpus's transcription
conventions, and its degradation shows up in MAE, F1 and the threshold
accuracies instead. MFA is the exception, and instructively so. It carries
pronunciation variants and chooses between them acoustically, which is why
its `S` drifts (14.0 → 14.4 on Buckeye dev) as conditions worsen.

## Noise robustness

Every table on a corpus page already spans the degraded conditions, so there
is no separate noise section. Each shows **Clean** against a single **Noisy**
mean, with the per-condition breakdown in Details. The ground truth, the
splits and the tools are the same, and only the acoustics differ. All four
reproduce Kaldi's
[`egs/voxceleb/v2/run.sh`](https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh)
exactly rather than an invented SNR sweep.

### What the four conditions are

Three mix in [MUSAN](https://www.openslr.org/17/) (Snyder, Chen & Povey,
[arXiv:1510.08484](https://arxiv.org/abs/1510.08484)), about 109 hours of
**recorded audio** rather than a synthetic spectral profile. The fourth
convolves room impulse responses and adds nothing.

| Condition | Source | What it is |
|---|---|---|
| Reverb | Simulated RIRs, 0.5 smallroom + 0.5 mediumroom | Convolution rather than mixing. Energy smears forward in time, so a boundary's label time is unchanged but the acoustic evidence for it has moved |
| Noise | MUSAN noise, 930 recordings, 6 h 07 m | Technical and ambient sound, from dial tones and button presses to thunder, car horns and city ambience |
| Music | MUSAN music, 660 tracks | Western art music and popular genres, annotated for vocals |
| Babble | MUSAN speech, 60 h 26 m | LibriVox recordings and US government archives, so the overlay is **real talkers** rather than shaped noise |

**Every degraded file is exactly as long as its clean source.** The recipe
that builds the degraded audio pads each file by 475 ms at both ends before
degrading it, and both pads are cut off before any system hears it. Until
2026-09-25 only the leading pad was cut, so each degraded TIMIT file ran on
for 475 ms of noise after its last word, and a system that runs its last word
or phone to the end of the file was charged for it. Buckeye was not affected,
because its utterances are cut from inside each recording and never reach the
end. Every TIMIT noisy cell was re-run on the corrected audio, with two
exceptions. ElevenLabs was spot-checked instead. A smoke run of a few
utterances on the corrected audio returned the same output as the earlier run,
so the full re-run was skipped, and its credit is now spent. Its earlier output
never ran into the extra audio, and cutting it at the clean length changes none
of its numbers, so they stand. NeuFA's output
comes from its authors' unreleased checkpoint and cannot be re-run here, so
its earlier output is cut at the clean length, with every start and end past
it moved to it.

## Which subset the numbers cover

**These are held-out splits rather than whole-corpus passes**, a change from
the previous version of this page.

<!-- BEGIN GENERATED: coverage -->
All **17** aligner-track systems are scored on all **4** splits (Buckeye Dev, Buckeye Test, TIMIT Dev, TIMIT Core-test).

BFA, Charsiu, CrisperWhisper, FALCON, MAPS, MFA 2.0, MFA 3.4, MMS-FA, NeMo-FA 40 ms, NeMo-FA 80 ms, NeuFA, Olign 1.0, Qwen3-FA, stable-ts, TorchAudio, UnitY2, WhisperX.

Scored separately in **track 2** are the timestamped ASRs, which decode their own words rather than being given the transcript, so the two tracks never share a leaderboard. They are Amazon Transcribe, AssemblyAI Universal 3.5, Azure AI Speech, CrisperWhisper, Deepgram Nova-3, ElevenLabs Scribe v2, Google Chirp 2, Google Chirp 2 → Olign 1.0, IBM Watson Large, Parakeet-TDT, Parakeet-TDT → MFA 3.4, Parakeet-TDT → Olign 1.0, Qwen3 → BFA, Qwen3 → Charsiu, Qwen3 → CrisperWhisper, Qwen3 → MAPS, Qwen3 → MFA 2.0, Qwen3 → MFA 3.4, Qwen3 → MMS-FA, Qwen3 → NeMo-FA 40 ms, Qwen3 → NeMo-FA 80 ms, Qwen3 → Olign 1.0, Qwen3 → Qwen3-FA, Qwen3 → stable-ts, Qwen3 → TorchAudio, Qwen3 → UnitY2, Qwen3 → WhisperX, Speechmatics enhanced, TorchAudio (ASR), Whisper large-v3, Whisper → WhisperX, Whisper-timestamped.
<!-- END GENERATED: coverage -->

Three changes make the old numbers incomparable rather than merely
superseded.

1. **TIMIT's SA sentences are now excluded everywhere.** The corpus
   documentation states they must not be used for training or test.
   `full_test` therefore means **1,344** rather than the 1,680 previously
   reported, and the old `all` (6,300) cell no longer exists.
2. **Buckeye is re-split.** The previous stride rule put **4 young and 0 old**
   speakers in test, so it measured a single age group. The split is now
   stratified on the corpus's own sex × age design, with 24/8/8 speakers and
   cells of 6/6/6/6 in train and 2/2/2/2 in each of dev and test.
3. **The scorer changed.** August's word MAE counted a boundary shared by two
   words twice and its F1 paired boundaries by time alone. September counts
   each boundary once, and its F1 counts a boundary only when the words on
   both sides match, the two utterance edges included. Words are matched
   without regard to case, an utterance a system returned nothing for counts
   against its F1, WER and PER, and a one-step recognizer is scored on the
   words it wrote.

Membership is committed in `datasets/languages/en/{timit,buckeye}/split/*.list`,
one `<speaker_id> <utterance_id>` per line.

## Aligner provenance

### Versions as evaluated

Read from the installed environment rather than typed by hand, from lock
files, conda-meta, each tool's venv and the git checkouts. Release dates are
PyPI `upload_time` for the exact pinned version, or the commit date for
git-installed tools. The checkpoint is the one each tool's recipe loads. For
an endpoint, the model is the one requested and the dates are those of the
calls behind the published rows. Regenerate with `evals/gen_provenance.py`.

<!-- BEGIN GENERATED: provenance -->
**FA-Bench release** commit `b8efca42032a`, branch `paper` (2026-09-26) + uncommitted changes

| System | Version | Commit | Released | Checkpoint |
|---|---|---|---|---|
| BFA | 1.1.5 | — | 2026-06-05 | Tabahi/CUPE-2i en_libri1000_ua01c_e4 (preset en-us) |
| Charsiu | (git) | `13a69f2a22ca` | 2022-09-18 | charsiu/en_w2v2_fc_10ms |
| CrisperWhisper | 2.0.2 | — | 2026-08-06 | nyrahealth/CrisperWhisper |
| CrisperWhisper-FA | 2.0.2 | — | 2026-08-06 | nyrahealth/CrisperWhisper |
| FALCON | (git) | `3d6e3d876eba` | 2026-06-29 | falcon_joint_multilingual.pt |
| MAPS | (git) | `bf797f434b83` | 2026-02-23 | timbuck_eng.tf |
| MFA 2.0 | 2.0.6 | — | 2022-08-08 | english_us_arpa acoustic model and dictionary |
| MFA 3.4 | 3.4.1 | — | 2026-07-11 | english_us_arpa acoustic model and dictionary |
| MMS-FA | 2.8.0 | — | 2025-08-06 | MMS_FA |
| NeMo-FA | 2.7.3 | — | 2026-04-23 | stt_en_fastconformer_hybrid_large_pc (80 ms), stt_en_conformer_ctc_large (40 ms) |
| NeuFA | (git) | `6cacd91cfe02` | 2025-01-17 | neufa-fabench-220k.pt, the authors', not released (SHA-256 `68b163eb3599`) |
| Olign | v1.0.0 | — | undisclosed | — |
| Parakeet-TDT | 2.7.3 | — | 2026-04-23 | nvidia/parakeet-tdt-0.6b-v3 |
| Qwen3-ASR | 0.0.6 | — | 2026-01-30 | Qwen/Qwen3-ASR-1.7B, with Qwen/Qwen3-ForcedAligner-0.6B |
| Qwen3-FA | 0.0.6 | — | 2026-01-30 | Qwen/Qwen3-ForcedAligner-0.6B |
| stable-ts | (git) | `e312072cc024` | — | Whisper base |
| TorchAudio | 2.8.0 | — | 2025-08-06 | WAV2VEC2_ASR_BASE_960H, facebook/wav2vec2-lv-60-espeak-cv-ft |
| TorchAudio (ASR) | 2.8.0 | — | 2025-08-06 | WAV2VEC2_ASR_BASE_960H |
| UnitY2 | (git) | `9a081e935c29` | 2026-09-08 | nar_t2u_aligner |
| Whisper large-v3 | 5.16.1 | — | 2026-08-26 | openai/whisper-large-v3 |
| Whisper-timestamped | 1.15.9 | — | 2025-09-09 | Whisper large-v3 |
| WhisperX | 3.8.6 | — | 2026-05-25 | WAV2VEC2_ASR_BASE_960H |
| WhisperX (ASR) | 3.8.6 | — | 2026-05-25 | Whisper large-v3, then WAV2VEC2_ASR_BASE_960H |

Commercial endpoints, with the model as requested and the days of the calls the published rows come from (UTC).

| Endpoint | Model | Called |
|---|---|---|
| Amazon Transcribe | en-US | 2026-09-20 to 2026-09-25 |
| AssemblyAI Universal 3.5 | universal-3-5-pro | 2026-09-17 to 2026-09-25 |
| Azure AI Speech | en-US, API 2024-11-15 | 2026-09-18 to 2026-09-25 |
| Deepgram Nova-3 | nova-3 | 2026-09-17 to 2026-09-25 |
| ElevenLabs Scribe v2 | scribe_v2 | 2026-09-17 to 2026-09-24 |
| Google Chirp 2 | chirp_2 | 2026-09-17 to 2026-09-25 |
| IBM Watson Large | en-US | 2026-09-17 to 2026-09-26 |
| Speechmatics enhanced | enhanced | 2026-09-17 to 2026-09-25 |
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
| NeuFA | Bidirectional attention | LibriSpeech + Buckeye, 36 speakers | ⚠ **Buckeye only**, see below |
| FALCON | Soft dynamic programming | Buckeye, its own 80/10/10 speaker split | ⚠ **Buckeye**, see below |
| Olign | Undisclosed | Undisclosed | none |
| TorchAudio | wav2vec2 CTC, words and phones | LibriSpeech 960 h for words, and LibriLight 60k h then Common Voice phone labels for phones | none |
| MMS-FA | wav2vec2 CTC | 31k h in 1,130 languages | none |
| NeMo-FA 40 ms | Conformer CTC | LibriSpeech, Fisher, Switchboard-1, WSJ, NSC, VCTK, VoxPopuli, Europarl-ASR, MLS, Common Voice | none |
| NeMo-FA 80 ms | FastConformer hybrid | LibriSpeech, Fisher, Common Voice, NSC, VCTK, VoxPopuli, Europarl-ASR, MLS, SPGI | none |
| CrisperWhisper | Whisper large-v3, fine-tuned | English and German verbatim data, with AMI IHM and TIMIT for word timestamps | ⚠ **TIMIT possible**, see below |
| Qwen3-FA | LLM-based aligner | Not itemized | unknown |
| stable-ts | Whisper base | Whisper's web audio, not itemized | unknown |
| UnitY2 | Text-to-unit aligner (SeamlessM4T) | Not itemized | unknown |

On Track 2, the one-step recognizers.

| System | Training data | Overlap with these splits |
|---|---|---|
| Whisper large-v3, Whisper-timestamped, WhisperX (ASR) | 1M h weakly labelled and 4M h pseudo-labelled audio, not itemized | unknown |
| Parakeet-TDT | 10k h of NeMo ASR Set 3.0 (LibriSpeech, Fisher, NSC, VCTK, Europarl-ASR, MLS, Common Voice, AMI) and 660k h pseudo-labelled Granary | none |
| Qwen3-ASR | Not itemized | unknown |
| CrisperWhisper | as on Track 1 | ⚠ **TIMIT possible** |
| TorchAudio (ASR) | LibriSpeech 960 h | none |
| The eight commercial endpoints | Undisclosed | unknown |

Training data is as each system's model card or documentation states it.
"none" means the data is itemized and includes neither TIMIT nor Buckeye.
"unknown" means it is not itemized, so an overlap can be neither shown nor
ruled out.

⚠ **MAPS is not on equal footing with the rest, on Buckeye.** Its `timbuck`
models are trained on TIMIT and Buckeye, and its
[model card](https://github.com/MasonPhonLab/MAPS) states the split exactly.
Buckeye speaker 4 is held out for validation, speakers 27, 38, 39 and 40 for
test, plus the TIMIT test set. Buckeye ships no official split, so FA-Bench
chose a different one and the two disagree. Seven of the eight speakers in
each of our Buckeye splits are in its training set, so those rows are not
held-out results. Its TIMIT rows are held out, because both our TIMIT splits
are carved from TIMIT `TEST/`, which it did not train on.

⚠ **NeuFA and FALCON are in the same position on Buckeye.** NeuFA's recipe
trains on 36 of Buckeye's 40 speakers and holds out 10, 20, 30 and 40, so 7 of
the 8 speakers in each of our Buckeye splits are in its training set. It does
not train on TIMIT. FALCON trains on its own 80/10/10 speaker split of
Buckeye, so at least 8 of the 16 speakers in our dev and test splits are in
its training set, and it is handed the reference phones rather than the
words.

⚠ **CrisperWhisper** names TIMIT among the datasets with word timestamps it
used, and chose its alignment heads on TIMIT, without saying which part of
the corpus. Both our TIMIT splits come from TIMIT `TEST/`, so its TIMIT rows
are held out only if it used the training part.

This is two projects splitting an unsplit corpus differently rather than a
disclosure failure. The overlap is quantified here only because MAPS stated
its split. The same table would have to say "undisclosed" for a system that
does not state one.

Every row marked none, Olign included, is held out. No system was trained on
the splits it is scored on. One distinction the table cannot show is that
MFA, Charsiu, BFA and WhisperX never saw either corpus in any form, while a
same-corpus-trained system meets familiar channel, recording conditions and
annotation conventions even on speakers it has never heard. That is worth a
reader's attention, though it is not an overlap.

**Olign is undisclosed** beyond its input and output contract, which takes
audio plus a reference transcript and returns word and phone boundaries with
confidences. Its architecture, training data and configuration are all
unpublished. Its row reports the shipped system, as any system would be
entered.

### Output quirks the scores keep

Every system is scored on what it returned. These are the known cases where
that output is unusual, and what the scorer does with it.

- **Qwen3-FA** reports times on an 80 ms grid, so a word shorter than one step
  gets the same start and end, and both of its boundaries land on one time.
  That is 5.9% of its words on clean Buckeye test and 10.8% under noise, and
  3.0% on clean TIMIT test.
- **NeuFA** predicts each boundary on its own, so neighbouring words and
  phones overlap. Word MAE reads a boundary at the end of the word before it,
  and F1 at the start of the unit after it. For output that tiles, which is
  every other system, those are the same time.
- **TorchAudio** runs twice into one file, mode A given the words and mode B
  given the phones, so each `leaderboard.csv` has two TorchAudio rows. The
  word tables read mode A and the phone tables mode B. Qwen3 → TorchAudio is
  the same.
- **Google Chirp 2** returned one word, `clinton`, ending at 166.88 s in a
  3.05 s Buckeye test segment (`buckeye_s0501a_038`). The word matches
  nothing, so word MAE is unchanged, but any signed or time-only statistic
  over Google's Buckeye test output includes it.
- **WhisperX** returns one word with an empty label in each of the four
  degraded Buckeye test cells, where the reference has Buckeye's `?` for an
  unintelligible word. It matches nothing and counts as one inserted boundary.
- **Deepgram Nova-3** times the last word past the end of the audio in a
  quarter of Buckeye test utterances. The ‡ note under its tables has the
  numbers.

## Reproducing

Every alignment is persisted with the tool that produced it, at
`evals/<kind>/<tool>/en/<corpus>/<subset>/<condition>/hyp.jsonl`, so a metric
change is a **rescore** rather than a re-run.

```
evals/run_evals.sh [tool ...]              # align and score, one run per (cell, tool)
evals/rescore_all.sh                       # rebuild every leaderboard from the saved hyp
evals/publish_records.py --release <tag>   # snapshot the numbers into records/
```

Per-tool environments and the exact parameters are in `evals/<kind>/<tool>/`.

**Comparing a reproduction with this snapshot.** The MAE and F1 on the word
pages are the `wbe_ms` and `wbnd_f1_all_20ms` columns of
`summary/<kind>/en/<corpus>/<subset>/<condition>/leaderboard.csv`, and on the
phone pages `mae_ms` and `bnd_f1_all_20ms`. The Noisy column is the mean of
the four conditions. `evals/update_public_tables.py --records-dir
records/202609/en --check` regenerates every table on these pages from your
`summary/`, changes nothing, and exits 1 naming each page that would differ.
