<p align="center">
  <img src="docs/FA-Bench.jpeg" alt="FA-Bench" width="200">
</p>

<p align="center">
  <a href="docs/paper.pdf"><img src="https://img.shields.io/badge/paper-PDF-b31b1b" alt="Paper (PDF)"></a>
  <a href="https://github.com/olewave/fa-bench/actions/workflows/ci.yml"><img src="https://github.com/olewave/fa-bench/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-blue" alt="License: PolyForm Noncommercial 1.0.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
</p>

# <a href="docs/paper.pdf" title="The FA-Bench paper (PDF)"><img src="docs/pdf-icon.svg" alt="Paper (PDF)" height="32"></a> FA-Bench: A Benchmark for Evaluating Phone- and Word-Level Timestamp Accuracy in Forced Aligners (v1)

<p align="right">
  <b> Click ⭐ at the top right to save FA-Bench into your speech toolbox - save it now! ↗️</b><br>
  <b> 点击右上角⭐，将FA-Bench收藏进您的语音工具箱，现在就收藏! ↗️</b><br>
  <b> 오른쪽 상단의 ⭐를 클릭해 FA-Bench를 음성 툴박스에 저장하세요. 지금 바로! ↗️</b><br>
  <b> 右上の⭐をクリックして、FA-Bench を音声ツールボックスに保存しましょう。今すぐ！↗️</b><br>
  <b dir="rtl"> انقر على ⭐ في أعلى اليمين لحفظ FA-Bench في صندوق أدوات الكلام لديك - احفظه الآن! ↗️</b>
</p>

FA-Bench measures how well a system places word and phone boundaries in
speech, and how much of that accuracy survives noise. The reference is the
boundaries that human linguists marked by hand in two English corpora, read
speech in [TIMIT](records/202609/en/gold/word/timit/README.md#about-timit)
and conversation in
[Buckeye](records/202609/en/gold/word/buckeye/README.md#about-buckeye). We add
**no new annotation**. Times are used as annotated and labels are folded into
the shared TIMIT-39 phone set. The [FA-Bench paper](docs/paper.pdf) describes
the protocol and what the results show.

Every system runs on **clean** audio and on
[four degradations](records/202609/en/README.md#what-the-four-conditions-are)
(`reverb`, `noise`, `music`, `babble`). Systems are scored in **two tracks
that never share a leaderboard**. A forced aligner is given the reference
transcript, so only its timing is tested. A timestamped ASR decodes its own
words, so its timing error carries its recognition error too. Every run is
seeded and reproducible from a single command.

**30 systems scored**, 21 open models and 9 commercial APIs.

- **Forced aligners**, given the reference transcript.
  [BFA](https://github.com/tabahi/bournemouth-forced-aligner) ·
  [Charsiu](https://github.com/lingjzhu/charsiu) ·
  [CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper) ·
  [FALCON](https://github.com/MLSpeech/FALCON) ·
  [MAPS](https://github.com/MasonPhonLab/MAPS) ·
  [Montreal Forced Aligner (MFA)](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner) 2.0 and 3.4 ·
  [MMS-FA](https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.MMS_FA.html) ·
  [NeMo Forced Aligner](https://github.com/NVIDIA-NeMo/Speech/tree/main/tools/nemo_forced_aligner), Conformer and FastConformer checkpoints ·
  [NeuFA](https://github.com/thuhcsi/NeuFA) ·
  [Qwen3-ForcedAligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) ·
  [stable-ts](https://github.com/jianfch/stable-ts) ·
  [TorchAudio-FA](https://github.com/pytorch/audio) ·
  [UnitY2](https://github.com/facebookresearch/seamless_communication) ·
  [WhisperX](https://github.com/m-bain/whisperx)
- **Open ASR with timestamps**, decoding their own words.
  [Parakeet-TDT](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) ·
  [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) ·
  [TorchAudio wav2vec2 ASR](https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H.html) ·
  [Whisper large-v3](https://huggingface.co/openai/whisper-large-v3) ·
  [Whisper-timestamped](https://github.com/linto-ai/whisper-timestamped).
  CrisperWhisper runs here too.
- **Commercial APIs.**
  [Olign](https://olewave.com/en/olign-olewaves-lancet-accurate-speech-to-text-forced-alignment-service/) (forced alignment) ·
  [Amazon Transcribe](https://aws.amazon.com/transcribe/) ·
  [AssemblyAI Universal 3.5](https://www.assemblyai.com/) ·
  [Azure AI Speech](https://azure.microsoft.com/en-us/products/ai-foundry/tools/speech) ·
  [Deepgram Nova-3](https://deepgram.com/) ·
  [ElevenLabs Scribe v2](https://elevenlabs.io/speech-to-text) ·
  [Google Chirp 2](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-2) ·
  [IBM Watson Speech to Text](https://www.ibm.com/products/speech-to-text) ·
  [Speechmatics](https://www.speechmatics.com/)

We also score 19 two-step cascades, in which one of the aligners re-times the
words an ASR produced.

**Latest results**, the September 2026 snapshot.
[TIMIT, words](records/202609/en/gold/word/timit/README.md) ·
[TIMIT, phones](records/202609/en/gold/phone/timit/README.md) ·
[Buckeye, words](records/202609/en/gold/word/buckeye/README.md) ·
[Buckeye, phones](records/202609/en/gold/phone/buckeye/README.md) ·
[Timestamped ASRs](records/202609/en/asr/word/timit/README.md) ·
[Methodology](records/202609/en/README.md)

> **Licensed under [PolyForm Noncommercial 1.0.0](LICENSE)**
>
> | | |
> |---|---|
> | ✅ **Free** | Research, teaching, personal study, and work by charitable, educational, public-safety, environmental and government organisations. |
> | 💼 **Commercial use** | Requires a separate licence. Write to <info@olewave.com>. |
>
> © 2026 Olewave, LLC · Contributions are welcome under
> [`CONTRIBUTING.md`](CONTRIBUTING.md) · Vendored third-party code keeps its own
> licence.

---

## Install

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[test]"         # the core library and pytest
```

That is enough to run the self-test and the sanity gates. Each system
installs itself from its own recipe,
`evals/<kind>/<tool>/download_and_install.sh`, into its own environment. See
[`evals/README.md`](evals/README.md).

---

## Quickstart

```bash
fabench selftest      # prove the whole chain with NO licensed data
fabench gates         # sanity gates that need no data
fabench init          # say where your corpora are (interactive)
fabench config        # inspect the fully resolved run
```

If you see `fabench: command not found`, the venv is not active. Run
`. .venv/bin/activate`, or call `./bin/fabench`, which always uses this
checkout.

`gates` is the known-answer check on the measurement chain. Run it on a fresh
clone. Every gate has one answer fixed in advance, so a broken chain fails
loudly instead of reporting plausible numbers. Gate #2 needs licensed audio
and runs inside `fabench ingest`. `selftest` builds the synthetic corpus the
other gates use.

---

## Running it

```bash
fabench ingest        # staged corpora -> canonical gold, plus the plausibility gate
fabench noise fetch   # MUSAN (about 11 GB, once), only when needed
fabench run           # mix -> align -> score -> report
```

`fabench run` mixes its own noise on the fly, white, pink, ambient and babble
noise at set SNRs (`fabench/noise/config.yaml`). It is a quick check that the
chain works. **The published noisy numbers use a different set.** They come
from the four Kaldi conditions, reverb, noise, music and babble, built once by
[`datasets/prep/augment.sh`](datasets/prep/README.md). Its last step writes the
shadow roots every noisy cell reads.

For sweeps across systems and cells, use the staged driver. It takes the tools
to run by name. With no names it runs `mfa charsiu maps bfa`.

```bash
evals/run_evals.sh mfa                       # align clean, then score
evals/run_evals.sh --use-noisy-dataset mfa   # the same cells on the Kaldi conditions
evals/run_evals.sh --stage 3 mfa             # rescore from saved output, no GPU
```

Alignments are kept on disk, so a change to a metric or a grouping is a
**rescore** (`evals/rescore_all.sh`), which takes seconds per cell instead of
GPU hours.

TIMIT and Buckeye are **licensed, and you stage them yourself**. FA-Bench never
downloads them. `fabench init` asks where they are and writes `.fabench.env`.
A corpus it cannot find is left unset rather than guessed, and `fabench run`
skips it and prints how to obtain it.

---

## Where things live

```
fabench/     the library, one folder per subsystem, each with its own README
evals/       how each system was run, with recipes, environments and raw output
datasets/    split lists and per-corpus config, with prep/ recording how gold was built
summary/     leaderboards and reports, SCRIPT OUTPUT, gitignored
records/     published snapshots, <YYYYMM>/en/<transcript>/<tier>/<corpus>/
```

Every path below `evals/` and `summary/` shares one cell key,
`<lang>/<corpus>/<subset>/<condition>`, with `origin` for un-augmented audio.

| Path | Holds | Tracked? |
|---|---|---|
| `evals/<kind>/<tool>/<cell>/` | one tool's run, with its config, `hyp.jsonl` and scores together | no |
| `summary/<kind>/<cell>/` | the cross-tool leaderboard for that track | no, regenerated |
| `summary/local/<cell>/` | your own `fabench run` | no |
| `records/<YYYYMM>/en/<transcript>/<tier>/<corpus>/` | the **published snapshot**, written by `evals/publish_records.py` | **yes** |

Nothing you run is tracked, so reproducing the benchmark leaves `git status`
clean. **Publishing is a separate, deliberate act.** `evals/publish_records.py
--release <tag>` snapshots the current numbers into
`records/<YYYYMM>/en/<transcript>/<tier>/<corpus>/`, carries the previous
month's prose forward so only the tables move, and names that public release
as the one that produced them.

Further reading. [`evals/README.md`](evals/README.md) explains how the systems
were run, [`datasets/README.md`](datasets/README.md) covers staging, splits and
licensing, and [`datasets/prep/README.md`](datasets/prep/README.md) has the
exact data-prep and augmentation commands.

---

## Configuration

**There is no run config to write.** Every default composes at load time from
the part of the tree that owns it, so `fabench run` with no `--config` is a
complete, valid run. The defaults live in

- `fabench/config.yaml` and `fabench/noise/config.yaml`,
- `datasets/languages/<lang>/config.yaml`,
- `evals/config.yaml` and `evals/<kind>/<tool>/config.yaml`,
- `fabench/normalize/<lang>/config.yaml` and `fabench/score/config.yaml`.

Two files carry what is specific to you.

| File | Holds | Tracked? |
|---|---|---|
| `.fabench.env` | what the **machine** is, with staged corpus roots, GPUs, threads and tool paths | no (template in `.fabench.env.example`) |
| a YAML you name | a deliberate **variant**, passed as `--config my.yaml` or `$FABENCH_CONFIG` | your choice |

Precedence is **run config > environment > composed defaults**. There is no
magic filename. A config is only ever loaded because you named it. Check what
anything resolved to with `fabench config`.

---

## Metrics

Both tiers, words and phones, carry the same set. The two the paper and the
comparison pages report are MAE and the label-checked F1.

- **Boundary MAE** (`wbe_ms` for words, `mae_ms` for phones), with median,
  signed mean and a bootstrap **95 % CI**. Units are matched to the reference
  by label first. A boundary is then scored only when every unit beside it
  matched, so a dropped or misrecognized unit leaves the average instead of
  worsening it. Threshold accuracy at **10 / 20 / 25 / 50 / 100 ms**
  (`fabench/score/config.yaml`) is the tail-sensitive companion.
- **F1 at 20 ms, labels checked** (`wbnd_f1_all_20ms`, `bnd_f1_all_20ms`). A
  boundary is a hit only when the units on **both** sides of it match the
  reference and it lies within 20 ms. The two utterance edges count, against
  silence. Every reference boundary is in the denominator, including those of
  an utterance a system returned nothing for, so skipping hard material costs
  recall. The same F1 is reported at 10, 25, 50 and 100 ms.
- **Boundary classes**, the F1 of each kind of reference boundary, which is
  Table 3 of the paper. `M2_I` is an interior boundary whose two words both
  match (`*_f1_int_both_20ms`). `M1_I` has only one of them matching
  (`*_int_one_`). `M1_B` and `M1_E` are the utterance's start and end with
  their one word matched (`*_start_ok_`, `*_end_ok_`). `M0` is the rest
  (`*_rest_`).
- **S / D / I, WER and PER** say why a reference unit left the matched path.
  It was relabelled, never emitted, or invented. A system that skips hard
  units to flatter its MAE shows up in `D`.
- **Time-only P/R/F1, over-segmentation and R-val** (`*_f1_20ms`, on the
  Details pages) pair boundaries by time alone, so a boundary at the right
  moment on the wrong word is free there. Read it as a diagnostic. The
  headline is the label-checked F1.

Every table spans **clean and the four degradations on one row**, because the
question is how much of a system's accuracy survives degradation.

`scoring.protocol` selects how boundaries are matched. `fabench`, the default,
uses our own matcher with the manner-match exclusion and works for every
aligner. `mfa_paper` bridges to the MFA paper's own evaluation code, so its
Table 5 can be reproduced exactly. What that changes, and the residual it does
not explain, is worked through in
[the methodology page](records/202609/en/README.md).

---

## Status

FA-Bench reproduces **Table 5** of
[McAuliffe, 2026](https://github.com/MontrealCorpusTools/mfa-interspeech2026)
on TIMIT and paper-segmented Buckeye, and scores it under **clean audio and
the four degradations** above.

The roster is listed at the top. Track 1 is given the transcript. Track 2
decodes its own words. Every system is scored on both corpora, all four
splits, clean and degraded, with one exception. ElevenLabs has degraded cells
on the two test splits only, because its credit ran out.

**Olign is in beta and access is by request.** It needs credentials from
Olewave (<info@olewave.com>). Every other system installs from its own recipe
and needs nothing from us.

Not every system reaches every tier. On Track 1, only **BFA, Charsiu, FALCON,
MAPS, MFA, NeuFA, Olign and TorchAudio emit phones**. The others, and every
one-step ASR, emit words only and appear in the word tables alone. The tables
show a dash rather than a number wherever that is so. Per-system notes are in
each tool's README under `fabench/aligners/`. The numbers and their caveats are
in [`records/`](records/202609/en/gold/word/timit/README.md).

Reproduce with `.venv/bin/python -m pytest -q` and `fabench gates`. The only
gate that needs restricted data is gold plausibility, which runs inside
`fabench ingest`.

---

## License / data

FA-Bench ships **manifests and recipes, never audio**. TIMIT (LDC) and Buckeye
(OSU registration) must be obtained under their own licences and staged by
you. Aligner hypotheses embed the corpora's transcripts, so they are gitignored
and never enter the history. The same goes for the machine-specific paths in
`.fabench.env`.

Vendored third-party code keeps its own licence. The Kaldi augmentation
scripts under `fabench/dataprep/noisemix/kaldi/` remain **Apache-2.0**, with
their `COPYING` and `PROVENANCE.md` beside them. The PolyForm licence covers
Olewave's own code.
