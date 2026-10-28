<p align="center">
  <img src="docs/FA-Bench.jpeg" alt="FA-Bench" width="200">
</p>

<p align="center">
  <a href="https://olewave.com/en/leaderboard/fa-bench"><img src="https://img.shields.io/badge/leaderboard-latest-orange" alt="Leaderboard (latest)"></a>
  <a href="https://arxiv.org/abs/2609.32396"><img src="https://img.shields.io/badge/arXiv-2609.32396-b31b1b" alt="Paper on arXiv"></a>
  <a href="https://github.com/olewave/fa-bench/actions/workflows/ci.yml"><img src="https://github.com/olewave/fa-bench/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="Apache 2.0 license"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
</p>

# <a href="https://arxiv.org/abs/2609.32396" title="The FA-Bench paper on arXiv"><img src="docs/pdf-icon.svg" alt="Paper (PDF)" height="32"></a> FA-Bench: A Benchmark for Evaluating Phone- and Word-Level Timestamp Accuracy in Forced Aligners

<p align="right">
  <b> Click ⭐ at the top right to save FA-Bench into your speech toolbox. Save it now! ↗️</b><br>
  <b> 点击右上角⭐，将FA-Bench收藏进您的语音工具箱，现在就收藏! ↗️</b><br>
  <b> 오른쪽 상단의 ⭐를 클릭해 FA-Bench를 음성 툴박스에 저장하세요. 지금 바로! ↗️</b><br>
  <b> 右上の⭐をクリックして、FA-Bench を音声ツールボックスに保存しましょう。今すぐ！↗️</b><br>
  <b dir="rtl"> انقر على ⭐ في أعلى اليمين لحفظ FA-Bench في صندوق أدوات الكلام لديك. احفظه الآن! ↗️</b>
</p>

FA-Bench measures how well a system places word and phone boundaries in
speech, and how much of that accuracy survives noise. The reference is the
boundaries that human linguists marked by hand in two English corpora, read
speech in [TIMIT](records/README.md#about-timit)
and conversation in
[Buckeye](records/README.md#about-buckeye). We add
**no new annotation**. Times are used as annotated and labels are folded into
the shared TIMIT-39 phone set. The [FA-Bench paper](https://arxiv.org/abs/2609.32396) describes
the protocol and what the results show.

Every system runs on **clean** audio and on
[four degradations](records/README.md#the-four-conditions)
(`reverb`, `noise`, `music`, `babble`). Systems are scored in **two tracks
that never share a leaderboard**. A forced aligner is given the reference
transcript, so only its timing is tested. A timestamped ASR decodes its own
words, so its timing error carries its recognition error too. Every run is
seeded and reproducible from a single command.

**31 systems scored**, 22 open models and 9 commercial APIs.

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
  [PocketSphinx](https://github.com/cmusphinx/pocketsphinx) ·
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

We also score 17 cascades, in which one of the aligners re-times the words an
ASR produced. A cascade holds the recognizer constant, which an ASR cannot, so
it is not ranked among the ASRs. It is reported beside the aligner on Track 1
instead, as what recognition errors cost that aligner.

**Latest results** are on the
[leaderboard](https://olewave.com/en/leaderboard/fa-bench).
[`records/`](records/README.md) lists the snapshots and describes the corpora
and the four conditions.

> **Licensed under the [Apache License 2.0](LICENSE)** from release 2.0.0.
> Copyright 2026 Olewave, LLC. The name FA-Bench stays with Olewave, as
> [the name policy](#the-name) explains. Contributions are welcome under
> [`CONTRIBUTING.md`](CONTRIBUTING.md), and vendored third-party code keeps its
> own licence ([`NOTICE`](NOTICE)).

---

## Install

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[test]"         # the core library and pytest
```

The scorer is also published on PyPI as `fa-bench`, and `pip install
fa-bench` gives the library and the `fabench` command. The commands that build
and run the benchmark read the dataset definitions and system recipes from a
checkout of this repository, so clone it, or unpack the sdist, to reproduce
the published numbers.

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
from the four Kaldi conditions, reverb, noise, music and babble.
`fabench prepare` builds them from your staged corpora, together with the
shadow roots every noisy cell reads and a sha256 manifest of both
([`datasets/prep/README.md`](datasets/prep/README.md)).

```bash
fabench prepare --corpus timit --subset core_test --out /data/fabench/noisy
```

Reproducing a published number takes three commands. `prepare` builds the
degraded audio, `run` runs one system on one cell through its adapter, and
`score` turns the saved outputs into the headline metrics. A cell config names
one system and one cell, `<corpus>/<subset>/<condition>`, and
`evals/gen_config.py` writes one for any cell.

```bash
fabench prepare --corpus timit,buckeye --out /data/fabench/noisy   # the four degraded conditions
fabench run --config <cell>.yaml      # one system on one cell
fabench score --config <cell>.yaml    # saved outputs -> the published metrics
```

For sweeps across systems and cells, use the staged driver. It takes the tools
to run by name. With no names it runs `mfa charsiu maps bfa`.

```bash
evals/run_evals.sh mfa                       # align clean, then score
evals/run_evals.sh --use-noisy-dataset mfa   # the same cells on the Kaldi conditions
evals/run_evals.sh --stage 3 mfa             # rescore from saved output, no GPU
```

Alignments are kept on disk, so a change to a metric or a grouping is a
**rescore** (`evals/run_evals.sh --stage 3`), which takes seconds per cell
instead of GPU hours.

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
records/     what each published snapshot covers, numbers on the leaderboard
```

Every path below `evals/` and `summary/` shares one cell key,
`<lang>/<corpus>/<subset>/<condition>`, with `origin` for un-augmented audio.

| Path | Holds | Tracked? |
|---|---|---|
| `evals/<kind>/<tool>/<cell>/` | one tool's run, with its config, `hyp.jsonl` and scores together | no |
| `summary/<kind>/<cell>/` | the cross-tool leaderboard for that track | no, regenerated |
| `summary/local/<cell>/` | your own `fabench run` | no |

Nothing you run is tracked, so reproducing the benchmark leaves `git status`
clean. **Publishing is a separate, deliberate act.** Olewave posts the
numbers of a snapshot on the
[leaderboard](https://olewave.com/en/leaderboard/fa-bench) and names the
public release that produced them.

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

FA-Bench scores both tiers, words and phones, at 20 ms. From release 2.0.0 the
word tier leads with the **word timestamp F1**, and the phone tier keeps the
label-checked boundary F1. The October 2026 snapshot was published before
2.0.0 and reports the label-checked F1 on both tiers.

- **Word timestamp F1 at 20 ms** (`wts_f1`, with `wts_precision` and
  `wts_recall`, new in 2.0.0). Every reference word owns two timestamps, its
  start and its end. A timestamp is a hit when the system returned the same
  word, matched by label on the scorer's alignment, and placed that word's
  start or end within 20 ms. Recall divides the hits by two per reference word
  and precision by two per system word, so a misrecognized, dropped or
  invented word costs its own two timestamps and nothing else. `wts_mae_ms`
  averages the start and end errors of the matched words, and
  `wts_start_mae_ms` and `wts_end_mae_ms` report them apart.
- **Boundary MAE** (`wbe_ms` for words, `mae_ms` for phones). Units are
  matched to the reference by label first. A boundary is then scored only
  when every unit beside it matched, so a dropped or misrecognized unit
  leaves the average instead of worsening it. `n_word_boundaries` and
  `n_boundaries` count the boundaries each average covers.
- **F1 at 20 ms, labels checked** (`wbnd_f1_all_20ms`, `bnd_f1_all_20ms`). A
  boundary is a hit only when the units on **both** sides of it match the
  reference and it lies within 20 ms. The two utterance edges count, against
  silence. Every reference boundary is in the denominator, including those of
  an utterance a system returned nothing for, so skipping hard material costs
  recall. The `n_*_gold_all` and `n_*_hyp_all` columns hold the two
  denominators.
- **WER and PER** add up the units a system relabelled, dropped or invented,
  over the number of reference units. A system that skips hard units to
  flatter its MAE pays for them here.

Each row also says how many utterances the system returned (`n_utts`), how
many it returned nothing for (`n_absent`) and how many came back empty
(`n_empty`). Further analysis metrics, among them the other tolerances and
the boundary classes of the paper, are part of Olewave's analysis work, and
this repository does not compute them.

Every table spans **clean and the four degradations on one row**, because the
question is how much of a system's accuracy survives degradation.

---

## Status

The roster is listed at the top. Track 1 is given the transcript. Track 2
decodes its own words. Every system is scored on both corpora, on all four
scored splits and on clean and degraded audio. There is one exception.
ElevenLabs has degraded cells on the two test splits only, because its credit
ran out.

**Olign gives accurate and cost-effective forced alignment and ASR with
timestamps.** It is a hosted service at a launch price of $0.18 per audio hour
(list price $0.21), and every new account comes with free credits. Register at
<https://tycho.olewave.com/#signup> and create an API key under Profile → API
key. Every other system installs from its own recipe and needs nothing from us.

**Cloud-service outputs and scores never go into training, tuning or target
setting for Olign.**

Not every system reaches every tier. On Track 1, only **BFA, Charsiu, FALCON,
MAPS, MFA, NeuFA, Olign, PocketSphinx and TorchAudio emit phones**. The others,
and every Track 2 system, emit words only and appear in the word tables alone.
The tables show a dash rather than a number wherever that is so. Per-system
notes are in each tool's README under `fabench/aligners/`. The numbers and
their caveats are on the
[leaderboard](https://olewave.com/en/leaderboard/fa-bench).

Reproduce with `.venv/bin/python -m pytest -q` and `fabench gates`. The only
gate that needs restricted data is gold plausibility, which runs inside
`fabench ingest`.

---

## License

FA-Bench is licensed under the [Apache License 2.0](LICENSE) from release
2.0.0. Copyright 2026 Olewave, LLC. [`NOTICE`](NOTICE) names the third-party
material in the tree, and each vendored tree keeps its licence beside it.
Releases up to 1.1.3 were published under PolyForm Noncommercial and are no
longer distributed. If you publish results produced with this software,
please cite the [paper](https://arxiv.org/abs/2609.32396), whose entry is in
[`CITATION.cff`](CITATION.cff).

### The name

FA-Bench is a name of Olewave, LLC. Results that Olewave runs under the
published protocol are FA-Bench results. Results you produce with this code
are welcome, and you can describe them as scored with the FA-Bench scorer,
version 2.0. The Apache 2.0 license covers the code. The name stays with
Olewave.

### What this repository leaves out, and why

- **The corpora.** TIMIT and Buckeye are licensed by their publishers, and
  their audio, transcripts and hand-marked boundaries may not be passed on.
  FA-Bench ships the split lists and the recipes that turn your own licensed
  copy into the benchmark data, and it never downloads either corpus.
- **System outputs.** A forced aligner's output carries the reference
  transcript word for word, and a recogniser's output comes close to it, so
  every hypothesis file is as restricted as the corpus. They stay on the
  machine that produced them, and the published tables hold numbers only.
- **Olewave's analysis tools.** The metrics beyond the headline set and the
  per-utterance error analysis are part of Olewave's paid service. So are the
  tools that compare vendors utterance by utterance, the result tables of
  each snapshot and the code that builds them. The scorer that produces every
  headline number is here in full.
- **Machine settings.** `.fabench.env` holds your corpus paths and API keys.
  The tracked template is `.fabench.env.example`.

### Getting the corpora

- **TIMIT** is catalog item
  [LDC93S1](https://catalog.ldc.upenn.edu/LDC93S1) of the Linguistic Data
  Consortium. Obtain it under an LDC licence. Members of the consortium
  receive it with their membership, and others pay a fee.
- **Buckeye** is distributed by The Ohio State University through
  [buckeyecorpus.osu.edu](https://buckeyecorpus.osu.edu/), after registration
  on that site.

Stage each copy in any folder and tell FA-Bench where it is with
`fabench init`, which writes `FABENCH_TIMIT_ROOT` and `FABENCH_BUCKEYE_ROOT`
into `.fabench.env`.

### Systems under test

Each system is installed by its own recipe under its own terms, and FA-Bench
redistributes none of their code or weights. Some carry restrictions worth
knowing before you run them. MMS-FA, CrisperWhisper and the UnitY2 tokenizer
are released for noncommercial use only, BFA and whisper-timestamped are under
the GPL family, NeuFA and its G2P carry no licence at all, and WebMAUS is
offered for academic research. [`evals/README.md`](evals/README.md) lists each
recipe with its licence.

---

## Paper

The FA-Bench paper is on arXiv as
[arXiv 2609.32396](https://arxiv.org/abs/2609.32396), and every link to the
paper on this page opens it there.
