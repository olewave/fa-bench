# Research behind the TIMIT and Buckeye use table

This page holds the evidence for every answer in
[timit_buckeye_use.md](timit_buckeye_use.md). It records which sources were read for
each system, the exact sentences that decide each answer, the overlaps FA-Bench
measured itself, and the calls that needed judgement. Everything was checked on
2026-11-27, for the version the leaderboard runs.

## How the answers are decided

**Sources read.** For each system, its model card, paper, README, CHANGELOG
and pull requests, and the file tree of every public repository that belongs to
it. Quotes below are copied from those sources. Where a source is silent, this
page says so and does not guess.

**Yes** needs a sentence or a file that shows the use. **No** needs the
training data to be itemized, or both corpora to be excluded outright, with no
sign of tuning on them. **Not disclosed** covers data that is not itemized, a
corpus used without naming the part, and data the owner keeps private.
**Self-claimed** marks a No from a system whose training recipe is not public,
because nobody outside can check it. A Yes is never starred, since a system
that says it used the test speakers is believed as it stands.

**A Yes for the training set** is shown plain, with no warning, because training
on the training set is what that set is for.

**Tuning** means choosing a checkpoint, a design or a default setting by its
score. Only the test question counts it, because the dev set exists for tuning.

**FA-Bench's splits.** These are the speakers each question is about.

| Split | TIMIT | Buckeye speakers |
|---|---|---|
| Training set | `TRAIN/`, 462 speakers | s01 s02 s03 s06 s09 s11 s12 s13 s15 s16 s17 s18 s19 s20 s21 s24 s26 s27 s29 s30 s33 s36 s38 s39 |
| Dev set | Kaldi's 50 dev speakers, from `TEST/` | s07 s08 s14 s22 s32 s35 s37 s40 |
| Test set | the 24 core test speakers, from `TEST/` | s04 s05 s10 s23 s25 s28 s31 s34 |

## The systems that used the test speakers

Buckeye ships no official split, and FA-Bench drew its own in August 2026. Both
systems below chose their Buckeye speakers before that, NeuFA in its 2022 recipe
and MAPS in 2023, so their overlap with FA-Bench's test speakers comes from
history.

### MAPS (timbuck_eng)

- **Training data.** The model card says "5% of the training data was randomly
  selected to be held out as a validation set during training. Speaker 4 from
  the Buckey data set was also held out for the validation set." Its test data
  "consisted of the test data set from TIMIT and the phrases from speakers 27,
  38, 39, and 40"
  ([model card](https://github.com/MasonPhonLab/MAPS/blob/main/timbuck_eng_model_card.md)).
- **TIMIT.** The paper's data script trains on `TIMIT\TRAIN` and tests on
  `TIMIT\TEST`
  ([00-data.py](https://github.com/MasonPhonLab/MAPS_Paper_Code/blob/HEAD/py_scripts/00-data.py)),
  and the paper says "The standard TIMIT test set was used"
  ([paper](https://arxiv.org/abs/2310.15425)). So TIMIT's dev and core test were
  never trained on.
- **Overlap with FA-Bench.**

  | FA-Bench split | In MAPS training | Used to pick the model | Never seen |
  |---|---|---|---|
  | Training set | 21 of 24 (all but s27 s38 s39) | | |
  | Dev set | s07 s08 s14 s22 s32 s35 s37 | | s40 |
  | Test set | s05 s10 s23 s25 s28 s31 s34 | s04 | none |

- **Recipe.** Public, in
  [MAPS_Paper_Code](https://github.com/MasonPhonLab/MAPS_Paper_Code)
  (`py_scripts/01-crisp_models.py` and `02-sparse_models.py`), with the timbuck
  split stated on the model card.
- **Answers.** Recipe Yes. Training set Yes, dev set Yes, test set Yes.

### NeuFA

- **Training data.** The paper says "Each NeuFA model is firstly trained on the
  full set of the LibriSpeech corpus for 120,000 steps … Then each model is
  trained on the data of 36 speakers in the Buckeye corpus for 220,000 steps"
  ([paper](https://arxiv.org/abs/2203.16838)). Its README moves speakers 10, 20,
  30 and 40 to a held-out set
  ([NeuFA](https://github.com/thuhcsi/NeuFA)). TIMIT is not mentioned in the
  paper, and the repository has no TIMIT loader.
- **Overlap with FA-Bench.**

  | FA-Bench split | In NeuFA training | Held out |
  |---|---|---|
  | Training set | 22 of 24 | s20 s30 |
  | Dev set | s07 s08 s14 s22 s32 s35 s37 | s40 |
  | Test set | s04 s05 s23 s25 s28 s31 s34 | s10 |

- **Caveat.** The leaderboard row runs the authors' own checkpoint, which they
  shared with FA-Bench but have not released. That it followed the public
  recipe is assumed.
- **Answers.** Recipe Yes (`train.py`). Training set Yes, dev set Yes, test set
  Yes.

## The systems that used TIMIT or Buckeye without naming the part

### BFA (bournemouth-forced-aligner 1.1.5, CUPE-2i en_libri1000)

- **Training.** The CUPE model card lists "LibriSpeech ASR corpus (SR12): 960
  hours", using "train-100, train-360, and train-500 splits"
  ([card](https://huggingface.co/Tabahi/CUPE-2i)).
- **Tuning.** The 1.1.5 CHANGELOG entry says "Default `boundary_softness=3` is
  changed from 7 to 3 because at 3 it performs the best on TIMIT and buckeye
  dataset"
  ([CHANGELOG](https://github.com/tabahi/bournemouth-forced-aligner/blob/main/CHANGELOG.md)).
  FA-Bench runs 1.1.5 with that default. The entry does not say which part of
  either corpus.
- **Recipe.** Not public. Neither the aligner's repository nor CUPE's holds
  training code.
- **Answers.** Recipe No. Training set No\*, dev set No\*, test set Not
  disclosed.

### CrisperWhisper (nyrahealth/CrisperWhisper 1.0)

- **Word timing.** "We used datasets with word-level timestamp annotations, such
  as AMI IHM and TIMIT, but required additional timestamped data" (model card).
- **Alignment heads.** "To choose the heads for alignment we evaluated the
  alignment performance of each individual decoder attention head on the
  timestamped timit dataset. We choose the 15 best performing heads" (model
  card). The card also reports a TIMIT F1 of 0.69, linked to the whole corpus,
  and says the number of heads was picked by "the result attaining the highest
  F1 Score" ([model card](https://huggingface.co/nyrahealth/CrisperWhisper)).
- **The paper is silent on TIMIT.** It names "the AMI Meeting Corpus and a
  specially adapted version of the PodcastFillers Corpus, along with a cleaned
  segment of the CommonVoice14 Corpus"
  ([paper](https://arxiv.org/abs/2408.16589)). The card explains that its
  attention loss "was not included in the original paper". The rest of its
  roughly 10,000 hours is not itemized, so Buckeye cannot be ruled out either.
- **Recipe.** Not public.
- **Answers.** Recipe No. Not disclosed in all three. The test answer turns on
  which TIMIT files were used, and the card does not say.

### nyra-FA (nyra_forced_aligner_en, nyra-forced-aligner 0.2.4)

- **Training.** "TIMIT, Buckeye, and FluencyBank are fully held out from
  training" (paper, p. 3). Table 2 lists seven training sources, 149 h in total:
  ICSI, NSC part 6, LibriSpeech with sound events, Common Voice 14, AMI, VCTK and
  DisfluencySpeech ([paper](https://arxiv.org/abs/2610.22583)).
- **Design choices made by results.**
  - "Unlike MFA, we apply no speaker adaptation and no maximum-likelihood linear
    transform (MLLT) of the features, since neither improved boundary accuracy
    in our ablations" (p. 2).
  - "We adopt the noise-robust arm as the final system: it matches the clean
    flagship on Buckeye while adding the robustness of Sec. 5.3" (p. 3).
- **Where those results were measured.** "We evaluate on TIMIT, Buckeye, and
  FluencyBank" (p. 3). The paper names no dev or validation set, and no TIMIT
  or Buckeye part, speaker or count.
- **The public benchmark with the same three corpora.** nyra's own benchmark
  ([nyra_speech_timing_benchmark](https://github.com/nyrahealth/nyra_speech_timing_benchmark),
  commit `738fb1f`) ships text-free manifests. FA-Bench measured them against
  its own splits.

  | nyra set | Contents | Overlap with FA-Bench |
  |---|---|---|
  | TIMIT | 1,626 utterances from all 168 `TEST/` speakers, 826 SX, 464 SI and 336 SA | 183 of the 192 core test utterances, 385 of the 400 dev utterances |
  | Buckeye | 2,008 chunks of at most 20 s, 432.6 min, speakers s10 to s18 | all 35.2 min of FA-Bench's s10 test pieces (18.6% of its Buckeye test audio), all 30.4 min of its s14 dev pieces (15.9% of the dev audio), and 7 FA-Bench train speakers |

  The benchmark's README sets its own rule, "Systems must not be trained or
  tuned on the test splits." The paper does not cite the benchmark, and the
  benchmark is the only source that names these parts.
- **The released model.** Its `meta.json` on Hugging Face names the variant
  `pub_wavlm_ldadirect_clean` and WavLM layer 23, which is a different variant
  from the paper's noise-robust final system. How it was chosen is not stated.
- **Recipe.** Not public. The package repository holds inference code only, 31
  files.
- **Answers.** Recipe No. Training set No\*, dev set No\*, test set Not
  disclosed. The benchmark names TIMIT and Buckeye parts and the paper names
  none. The paper does not cite the benchmark, so this page does not join the
  two.

## The systems whose data is not itemized

| System | What the sources say | Source |
|---|---|---|
| ElevenLabs-FA | No statement in the documentation or in the Cue post | [docs](https://elevenlabs.io/docs/overview/capabilities/forced-alignment.md), [Cue post](https://elevenlabs.io/blog/cue-aligner) |
| Meta UnitY2 (nar_t2u_aligner) | "Mono-lingual speech corpora constructed from publicly available Internet dataset". Its XLS-R units list their pretraining data, and neither corpus is in it | [Seamless paper](https://arxiv.org/abs/2312.05187), Appendix F |
| PocketSphinx (en-us) | "generic US english acoustic model trained with latest sphinxtrain", no corpus named | [model README](https://github.com/cmusphinx/pocketsphinx/blob/f20ff1b7a5db/model/en-us/en-us/README) |
| Qwen3-FA (Qwen3-ForcedAligner-0.6B) | "we use pseudo-timestamp labels generated by the Montreal forced aligner (MFA)", corpora not named | [Qwen3-ASR report](https://arxiv.org/abs/2601.21337) |
| rumblex (Reson8/Rumble-2-Flash) | The speech model's card states no training data, and its base, Qwen3-ASR-0.6B, is not itemized. rumblex's own boundary head saw "2,500 LibriSpeech utterances" only | [card](https://huggingface.co/Reson8/Rumble-2-Flash), [boundary head](https://github.com/EdwardGlockner/rumblex/blob/v0.6.0/docs/boundary_head.md) |
| stable-ts (Whisper base) | "680,000 hours of audio and the corresponding transcripts collected from the internet". The paper deduplicates only against TED-LIUM 3, and its alignment heads were picked by hand on data it does not name | [model card](https://github.com/openai/whisper/blob/main/model-card.md), [paper](https://arxiv.org/abs/2212.04356) |

All six have no public recipe, so they read Recipe No and Not disclosed in all
three questions.

## The systems that itemize their data

| System | Training data as stated | Recipe | Source |
|---|---|---|---|
| Charsiu (en_w2v2_fc_10ms) | "alignments of the 960h Librispeech obtained through MFA", and its TIMIT test set "does not overlap with any of the training data" | Yes, `experiments/train_frame_classification.py` | [paper](https://arxiv.org/abs/2110.03876) |
| Meta MMS-FA | "31K hours in 1,130 languages", from FLEURS, Common Voice 8.0 and the MMS-lab recordings | No, fairseq's `examples/mms` covers data preparation and alignment only | [MMS paper](https://arxiv.org/abs/2305.13516) |
| Montreal-FA (english_us_arpa v3.0.0) | LibriSpeech, 982 h | Yes, `scripts/training_models/train_acoustic_models.py` in mfa-models | [model page](https://mfa-models.readthedocs.io/en/latest/acoustic/English/English%20%28US%29%20ARPA%20acoustic%20model%20v3_0_0.html) |
| NVIDIA NeMo-FA (stt_en_fastconformer_hybrid_large_pc) | NeMo ASRSet En PC, nine named corpora | Yes, the example script and base config on its card | [card](https://huggingface.co/nvidia/stt_en_fastconformer_hybrid_large_pc) |
| TorchAudio, WhisperX (WAV2VEC2_ASR_BASE_960H) | "pre-trained on 960 hours of unlabeled audio from LibriSpeech … and fine-tuned for ASR on the same audio" | Yes, fairseq `base_960h.yaml` | [torchaudio](https://docs.pytorch.org/audio/2.8.0/generated/torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.html) |
| Zyphra FuseAlign (ns4-step60000) | "none of it, nor the data of the checkpoints it was trained from, is TIMIT or Buckeye audio; TIMIT's prompt sentences appear only as read by other speakers in a TTS corpus" | No, the package repository has inference code only | [PR #30](https://github.com/olewave/fa-bench/pull/30) |

The first four read Recipe Yes and No in all three. MMS-FA and FuseAlign read
Recipe No and No\* in all three.

Two notes on these rows.

- **Charsiu.** The checkpoint has no model card. That it is the paper's
  LibriSpeech model rests on its config, which names `facebook/wav2vec2-base`
  and frame classification, and on the training script, which trains on
  LibriSpeech alignments.
- **FuseAlign.** The no-TIMIT statement is in Zyphra's PR only, not on the model
  card. The Descript paper that FuseAlign reproduces makes a similar statement
  about its own model, which does not carry over. TIMIT's sentence texts reach
  the training data only as read by other speakers, which is text and not
  TIMIT audio. PR #30 reports the dev cells and leaves the test cells to
  FA-Bench, and how the checkpoint was chosen is not stated.

## Olewave Olign v1

Olewave makes both FA-Bench and Olign. Olewave does not disclose Olign's
training data, so its row reads Not disclosed wherever the data would have to
be described, and Olign is listed unranked.

## What changes an answer

- A new version is checked again before its row changes.
- A source that names a dev set, or a split that excludes FA-Bench's test
  speakers, can move a Not disclosed to a No. A released recipe removes the
  asterisk from a No.
- A pull request that adds a system should state its training data, whether its
  recipe is public, and any use of TIMIT or Buckeye, split by split.
