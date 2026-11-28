# How each Track 1 system used TIMIT and Buckeye

FA-Bench scores forced aligners on TIMIT and Buckeye. A system that trained on
the speakers it is scored on has heard them before, and its score says less
about how it handles a speaker it has never met.

This page tells you, for every aligner on the leaderboard, whether its training
recipe is public and whether it used each of FA-Bench's splits. Every answer
comes from what the system's authors published about the version on the board,
as checked in November 2026.

## The table

| System | Training recipe released? | Used training set for training? | Used dev set for training? | Used test set for training or tuning? |
|---|---|---|---|---|
| BFA | No | ✅ No\* | ✅ No\* | 🟨 Not disclosed |
| Charsiu | Yes | ✅ No | ✅ No | ✅ No |
| CrisperWhisper | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| ElevenLabs-FA | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| MAPS | Yes | 🟧 Yes | 🟧 Yes | 🟧 Yes |
| Meta MMS-FA | No | ✅ No\* | ✅ No\* | ✅ No\* |
| Meta UnitY2 | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| Montreal-FA | Yes | ✅ No | ✅ No | ✅ No |
| NeuFA | Yes | 🟧 Yes | 🟧 Yes | 🟧 Yes |
| NVIDIA NeMo-FA | Yes | ✅ No | ✅ No | ✅ No |
| nyra-FA | No | ✅ No\* | ✅ No\* | 🟨 Not disclosed |
| PocketSphinx | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| Qwen3-FA | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| rumblex | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| stable-ts | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |
| TorchAudio | Yes | ✅ No | ✅ No | ✅ No |
| WhisperX | Yes | ✅ No | ✅ No | ✅ No |
| Zyphra FuseAlign | No | ✅ No\* | ✅ No\* | ✅ No\* |
| Olewave Olign v1 (unranked) | No | 🟨 Not disclosed | 🟨 Not disclosed | 🟨 Not disclosed |

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

Olewave makes both FA-Bench and Olign. Olign is listed last and unranked, and
Olewave does not disclose its training data. The phone board and both
recognized-words boards give the same answers for the same systems.

## Read the marks

| Mark | Answer | What it tells you |
|---|---|---|
| 🟧 dark yellow ⚠ | Yes | The authors say the system used that audio in that way |
| 🟨 light yellow ⚠ | Not disclosed | The authors do not list the data, or do not say which part of TIMIT or Buckeye they used |
| ✅ green check | No | The authors list the data, or rule out both corpora, and show no such use |

**A No is only as strong as its source.** Where the recipe is public, you can
rebuild the model and see the data for yourself. Where it is not, the No is the
authors' word, and the asterisk tells you so. A Yes never gets an asterisk. A
system that says it trained on the test speakers needs no proof beyond saying
so.

**Not disclosed is a fact about the sources.** It does not say the system did
anything wrong. Most of these systems simply never list what they trained on.

## See FA-Bench's splits yourself

The four columns ask about FA-Bench's own splits, and the lists ship with this
repository. From the repository root, print the Buckeye speakers in each split.

```bash
for s in train dev test; do
  printf '%-6s' "$s"
  grep -v '^#' datasets/languages/en/buckeye/split/$s.list | grep -oE '\bs[0-9]{2}' | sort -u | tr '\n' ' '
  echo
done
```

It prints the 24 train, 8 dev and 8 test speakers.

```text
train s01 s02 s03 s06 s09 s11 s12 s13 s15 s16 s17 s18 s19 s20 s21 s24 s26 s27 s29 s30 s33 s36 s38 s39
dev   s07 s08 s14 s22 s32 s35 s37 s40
test  s04 s05 s10 s23 s25 s28 s31 s34
```

TIMIT keeps its own lists beside them. Count the speakers in each.

```bash
for s in train dev core_test; do
  printf '%-10s' "$s"
  grep -v '^#' datasets/languages/en/timit/split/$s.list | awk '{print $1}' | sort -u | wc -l
done
```

You get 462 training speakers from TIMIT's `TRAIN/`, and 50 dev and 24 core
test speakers, both carved from its `TEST/`.

## Check an overlap yourself

When a system names the speakers it held out, one line of Python finds its
overlap with FA-Bench. NeuFA holds out Buckeye speakers 10, 20, 30 and 40.

```python
test = {"s04", "s05", "s10", "s23", "s25", "s28", "s31", "s34"}
print(sorted(test - {"s10", "s20", "s30", "s40"}))
```

It prints the seven FA-Bench test speakers that NeuFA trained on.

```text
['s04', 's05', 's23', 's25', 's28', 's31', 's34']
```

## Why each answer

Each row quotes the source that decides its answers.

| System | Why |
|---|---|
| BFA | Its phone model CUPE was trained on LibriSpeech 960 h ([card](https://huggingface.co/Tabahi/CUPE-2i)), but the default `boundary_softness=3` was chosen "because at 3 it performs the best on TIMIT and buckeye dataset" ([CHANGELOG](https://github.com/tabahi/bournemouth-forced-aligner/blob/main/CHANGELOG.md)), with no part named |
| Charsiu | en_w2v2_fc_10ms was trained on LibriSpeech 960 h with MFA labels, and its paper's TIMIT test set "does not overlap with any of the training data" ([paper](https://arxiv.org/abs/2110.03876)) |
| CrisperWhisper | Its word timing used "AMI IHM and TIMIT", and its alignment heads were chosen "on the timestamped timit dataset", with no part named ([model card](https://huggingface.co/nyrahealth/CrisperWhisper)) |
| ElevenLabs-FA | No statement in the documentation ([docs](https://elevenlabs.io/docs/overview/capabilities/forced-alignment.md)) |
| MAPS | timbuck_eng was trained on TIMIT `TRAIN/` and Buckeye, holding out speaker 4 to pick the epoch and speakers 27, 38, 39 and 40 for test ([model card](https://github.com/MasonPhonLab/MAPS/blob/main/timbuck_eng_model_card.md)). FA-Bench's test speakers s05 s10 s23 s25 s28 s31 s34 are in its training data and s04 chose its model |
| Meta MMS-FA | 31k h in 1,130 languages, from FLEURS, Common Voice 8.0 and the MMS-lab recordings ([MMS paper](https://arxiv.org/abs/2305.13516)) |
| Meta UnitY2 | "Mono-lingual speech corpora constructed from publicly available Internet dataset" ([Seamless paper](https://arxiv.org/abs/2312.05187), Appendix F) |
| Montreal-FA | english_us_arpa v3.0.0 was trained on LibriSpeech, 982 h ([model page](https://mfa-models.readthedocs.io/en/latest/acoustic/English/English%20%28US%29%20ARPA%20acoustic%20model%20v3_0_0.html)) |
| NeuFA | Trained on LibriSpeech and then on 36 Buckeye speakers, holding out s10 s20 s30 s40 ([paper](https://arxiv.org/abs/2203.16838), [recipe](https://github.com/thuhcsi/NeuFA)). That takes in 22 of FA-Bench's 24 train speakers, 7 of its 8 dev speakers and 7 of its 8 test speakers |
| NVIDIA NeMo-FA | stt_en_fastconformer_hybrid_large_pc, trained on NeMo ASRSet En PC, nine named corpora ([card](https://huggingface.co/nvidia/stt_en_fastconformer_hybrid_large_pc)) |
| nyra-FA | Its paper says "TIMIT, Buckeye, and FluencyBank are fully held out from training" and names seven other sources ([paper](https://arxiv.org/abs/2610.22583)). It also chose parts of its design by results on TIMIT and Buckeye, with no separate dev set, and does not say which parts of either corpus those were. Version 0.2.5 picked a setting on FA-Bench's TIMIT core test and Buckeye test, so moving the row to it would change the test answer to Yes |
| PocketSphinx | The bundled en-us model's README names no corpus ([README](https://github.com/cmusphinx/pocketsphinx/blob/f20ff1b7a5db/model/en-us/en-us/README)) |
| Qwen3-FA | Trained on MFA pseudo-labels, corpora not named ([Qwen3-ASR report](https://arxiv.org/abs/2601.21337)) |
| rumblex | Reson8/Rumble-2-Flash states no training data ([card](https://huggingface.co/Reson8/Rumble-2-Flash)). rumblex's own boundary head was trained on LibriSpeech only ([docs](https://github.com/EdwardGlockner/rumblex/blob/v0.6.0/docs/boundary_head.md)) |
| stable-ts | Whisper base, "680,000 hours of audio and the corresponding transcripts collected from the internet", deduplicated only against TED-LIUM 3 ([model card](https://github.com/openai/whisper/blob/main/model-card.md)) |
| TorchAudio, WhisperX | WAV2VEC2_ASR_BASE_960H, pretrained and fine-tuned on LibriSpeech 960 h ([torchaudio](https://docs.pytorch.org/audio/2.8.0/generated/torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.html)) |
| Zyphra FuseAlign | "none of it, nor the data of the checkpoints it was trained from, is TIMIT or Buckeye audio" ([PR #30](https://github.com/olewave/fa-bench/pull/30)) |

## Where the released recipes are

Six systems publish the code that trained their released model.

| System | Training code |
|---|---|
| Charsiu | [charsiu](https://github.com/lingjzhu/charsiu) `experiments/train_frame_classification.py` |
| MAPS | [MAPS_Paper_Code](https://github.com/MasonPhonLab/MAPS_Paper_Code) `py_scripts/01-crisp_models.py` and `02-sparse_models.py` |
| Montreal-FA | [mfa-models](https://github.com/MontrealCorpusTools/mfa-models) `scripts/training_models/train_acoustic_models.py` |
| NeuFA | [NeuFA](https://github.com/thuhcsi/NeuFA) `train.py`, with the speaker split in its README |
| NVIDIA NeMo-FA | The NeMo example script and base config named on its model card |
| TorchAudio, WhisperX | [fairseq](https://github.com/facebookresearch/fairseq) `examples/wav2vec/config/finetuning/base_960h.yaml` |

You can look for training code in any repository yourself. This lists NeuFA's
training script.

```bash
curl -s "https://api.github.com/repos/thuhcsi/NeuFA/git/trees/HEAD?recursive=1" \
  | grep -o '"path": *"[^"]*train[^"]*"'
```

The other systems publish inference code or weights only, so their No answers
are self-claimed.

## Keeping it current

FA-Bench checks a system again whenever its version on the board changes. A pull
request that adds a system should state its training data, whether its recipe
is public, and which TIMIT or Buckeye audio it used, split by split.

## Next steps

- **[The research behind each answer](info_research.md)**  
  Every quote and source, the speaker overlaps FA-Bench measured, and the calls
  that needed judgement.
- **[The leaderboard](https://olewave.com/en/leaderboard/fa-bench)**  
  The same answers, shown beside each system's scores.
- **[Add your own system](../CONTRIBUTING.md)**  
  How to open a pull request with a new aligner.
