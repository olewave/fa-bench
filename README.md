<p align="center">
  <img src="docs/FA-Bench.jpeg" alt="FA-Bench" width="200">
</p>

<p align="center">
  <a href="https://github.com/olewave/fa-bench/actions/workflows/ci.yml"><img src="https://github.com/olewave/fa-bench/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-blue" alt="License: PolyForm Noncommercial 1.0.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
</p>

# FA-Bench: A Benchmark for Evaluating Phone- and Word-Level Timestamp Accuracy in Forced Aligners (v1)

<p align="right">
  <b> Click ⭐ at the top right to save FA-Bench into your speech toolbox - save it now! ↗️</b><br>
  <b> 点击右上角⭐，将FA-Bench收藏进您的语音工具箱，现在就收藏! ↗️</b><br>
  <b> 오른쪽 상단의 ⭐를 클릭해 FA-Bench를 음성 툴박스에 저장하세요. 지금 바로! ↗️</b><br>
  <b> 右上の⭐をクリックして、FA-Bench を音声ツールボックスに保存しましょう。今すぐ！↗️</b><br>
  <b dir="rtl"> انقر على ⭐ في أعلى اليمين لحفظ FA-Bench في صندوق أدوات الكلام لديك - احفظه الآن! ↗️</b>
</p>

A deterministic, config-driven benchmark measuring how **forced aligners**
perform and degrade under **additive noise**, scored against human linguists'
hand-labeled ground truth phone- and word-level boundaries. English so far, on
read speech ([TIMIT](records/aligners/en/202608/timit/README.md#about-timit))
and spontaneous speech
([Buckeye](records/aligners/en/202608/buckeye/README.md#about-buckeye)), using
each corpus's own boundaries with **no new annotation** — times as annotated,
labels folded to the shared TIMIT-39 set. Every system runs on **clean** audio
and [four degradations](records/aligners/en/202608/README.md#what-the-four-conditions-are)
(`reverb`, `noise`, `music`, `babble`), scored in **two tracks that never share
a leaderboard**: aligners are given the reference transcript, while timestamped
ASRs decode their own words, so their timing error carries recognition error
too. Everything is seeded, flag-gated, and reproducible from a single command.

**12 systems scored:**
[BFA](https://github.com/tabahi/bournemouth-forced-aligner) ·
[Charsiu](https://github.com/lingjzhu/charsiu) ·
[CrisperWhisper-FA](https://github.com/nyrahealth/CrisperWhisper) ·
[MAPS](https://github.com/MasonPhonLab/MAPS) ·
[Montreal-Forced-Aligner (MFA)](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner) ·
[Olign](https://olewave.com/en/olign-olewaves-lancet-accurate-speech-to-text-forced-alignment-service/) ·
[Parakeet-TDT](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) ·
[Qwen3-ForcedAligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) ·
[stable-ts](https://github.com/jianfch/stable-ts) ·
[TorchAudio-FA](https://github.com/pytorch/audio) ·
[WhisperX](https://github.com/m-bain/whisperx)

**Latest Results:** [TIMIT (read US English)](records/aligners/en/202608/timit/README.md) ·
[Buckeye (spontaneous English)](records/aligners/en/202608/buckeye/README.md) ·
[Methodology](records/aligners/en/202608/README.md)


> **License — [PolyForm Noncommercial 1.0.0](LICENSE)**
>
> | | |
> |---|---|
> | ✅ **Free** | Research, teaching, personal study, and work by charitable, educational, public-safety, environmental and government organisations. |
> | 💼 **Commercial use** | Requires a separate licence — <info@olewave.com>. |
>
> © 2026 Olewave, LLC · Contributions are welcome under
> [`CONTRIBUTING.md`](CONTRIBUTING.md) · Vendored third-party code keeps its own
> licence.

---

## Install

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[test]"         # core + pytest — `fabench gates` runs test subsets
```

Each additional system installs itself from its own recipe —
`evals/<kind>/<tool>/download_and_install.sh` — into its own environment.
See [`evals/README.md`](evals/README.md).

---

## Quickstart

```bash
fabench selftest      # prove the whole chain with NO licensed data
fabench gates         # data-independent sanity gates
fabench init          # say where your corpora are (interactive)
fabench config        # inspect the fully resolved run
```

`fabench: command not found` means the venv is not active — run
`. .venv/bin/activate`, or `./bin/fabench`, which always uses this checkout's.

`gates` is the **known-answer check on the measurement chain** — run it on a
fresh clone. Every gate has one answer fixed in advance, so a broken chain fails
loudly instead of reporting plausible numbers. Gate #2 needs licensed audio and
runs inside `fabench ingest`; `selftest` is the synthetic corpus the rest use.

---

## Running it

```bash
fabench ingest        # staged corpora -> canonical gold + plausibility gate
fabench noise fetch   # MUSAN (~11 GB, once) — only when needed
fabench run           # mix -> align -> score -> report
```

For sweeps across every system and cell, use the staged driver:

```bash
evals/run_evals.sh                       # align clean, then score
evals/run_evals.sh --use-noisy-dataset   # the same cells, noisy audio
evals/run_evals.sh --stage 3 mfa         # rescore from saved hyp — no GPU
```

Alignments are persisted, so a metric or grouping change is a **rescore, not a
re-run** (`evals/rescore_all.sh`, seconds per cell instead of GPU-hours).

TIMIT and Buckeye are **licensed and user-staged** — FA-Bench never downloads
them. `fabench init` asks where they are and writes `.fabench.env`; a corpus it
cannot find is left unset rather than guessed, and `fabench run` skips it with
acquisition instructions.

---

## Where things live

```
fabench/     the library — one folder per subsystem, each with its own README
evals/       how each system was run: recipes, environments, raw output
datasets/    split lists + per-corpus config; prep/ records how gold was built
summary/     leaderboards and reports — SCRIPT OUTPUT, gitignored
records/     the published snapshots: aligners/en/<YYYYMM>/, with latest -> newest
```

Every path below `evals/` and `summary/` shares one cell key —
`<lang>/<corpus>/<subset>/<condition>`, with `origin` for un-augmented audio:

| Path | Holds | Tracked? |
|---|---|---|
| `evals/<kind>/<tool>/<cell>/` | one tool's run — config, `hyp.jsonl`, and its scores, together | no |
| `summary/<kind>/<cell>/` | the cross-tool leaderboard for that track | no — regenerated |
| `summary/local/<cell>/` | your own `fabench run` | no |
| `records/aligners/en/<YYYYMM>/` | the **published snapshot**, written by `evals/publish_records.py` | **yes** |

Nothing you run is tracked, so reproducing the benchmark leaves `git status`
clean. **Publishing is a separate, deliberate act:** `evals/publish_records.py`
snapshots the current numbers into `records/aligners/en/<YYYYMM>/` and repoints
`latest`, carrying the previous month's prose forward so only the tables move.

Further reading: [`evals/README.md`](evals/README.md) (how systems were run) ·
[`datasets/README.md`](datasets/README.md) (staging, splits, licensing) ·
[`datasets/prep/README.md`](datasets/prep/README.md) (the exact data-prep and
augmentation commands).

---

## Configuration

**There is no run config to write.** Every default composes at load time from
the part of the tree that owns it — `fabench/config.yaml`,
`fabench/noise/config.yaml`, `datasets/languages/<lang>/config.yaml`,
`evals/config.yaml`, `evals/<kind>/<tool>/config.yaml`,
`fabench/normalize/<lang>/config.yaml`, `fabench/score/config.yaml` — so
`fabench run` with no `--config` is a complete, valid run.

Two files carry what is not a default:

| File | Holds | Tracked? |
|---|---|---|
| `.fabench.env` | what the **machine** is — staged corpus roots, GPUs, threads, tool paths | no (template: `.fabench.env.example`) |
| a YAML you name | a deliberate **variant** — `--config my.yaml` or `$FABENCH_CONFIG` | your choice |

Precedence is **run config > environment > composed defaults**, and there is no
magic filename: a config is only ever loaded because you named it. Check what
anything resolved to with `fabench config`.

---

## Metrics

- **Boundary MAE / median (x̃) / signed (δ̄)**, dual-edge, on the matched path
  only, with bootstrap **95 % CIs**; threshold accuracy at **t=10 / 50 / 100 ms**
  — the tail-sensitive companion to MAE.
- **S / D / I and PER** — why a gold phone left the matched path: relabelled,
  never emitted, or invented. The anti-gaming guard: a system that skips hard
  phones to flatter its MAE shows up in `D`.
- **Boundary detection @20 ms** — **P/R**, **F1**, over-segmentation and
  **R-val**. Paired by time and blind to labels, so a substitution at the right
  moment is free here — which is exactly what the matched-path metrics above
  cannot see.
- **The word tier carries the same set** at the same 20 ms tolerance — MAE,
  P/R, F1, OS, R-val — and is the only phone-independent one, so it is the only
  place a word-only system appears at all.

Every table spans **clean and the four degradations on one row**, because the
question is never a system's accuracy but how much of it survives.

`scoring.protocol` selects how boundaries are matched: `fabench` (default —
own matcher + manner-match exclusion, works for every aligner) or `mfa_paper`
(bridges to the paper's **actual** evaluation code for exact Table 5
reproduction). What that changes, and the residual it does not explain, is
worked through in [the methodology page](records/aligners/en/202608/README.md).

---

## Status

Reproduction of **Table 5** of
[McAuliffe, 2026](https://github.com/MontrealCorpusTools/mfa-interspeech2026)
on TIMIT and paper-segmented Buckeye, scored under **clean and the four
degradations** above.

The roster is listed at the top. Track 1 is given the transcript; track 2
decodes its own words. Every system is scored on every cell of this snapshot —
both corpora, all four splits, clean and the four degradations.

**Olign is in beta and access is by request** — it needs credentials from
Olewave (<info@olewave.com>); every other system installs from its own recipe
and needs nothing from us.

Not every system reaches every tier. **CrisperWhisper, Parakeet-TDT, Qwen3,
stable-ts and WhisperX emit words but no phones**, so they appear only in the
word tables; the tables show an em dash rather than a number wherever that is
so. Every other system is scored on both tiers. Per-system notes are in each
tool's README under `fabench/aligners/`; the numbers and their caveats are in
[`records/`](records/aligners/en/202608/timit/README.md).

Reproduce with `.venv/bin/python -m pytest -q` and `fabench gates`. The only
gate needing restricted data is gold plausibility, which runs inside
`fabench ingest`.

---

## License / data

FA-Bench ships **manifests + recipes, never audio**. TIMIT (LDC) and Buckeye
(OSU registration) must be obtained under their own licences and staged by you.
Aligner hypotheses embed the corpora's transcripts, so they are gitignored and
never enter the history — as are the machine-specific paths in `.fabench.env`.

Vendored third-party code keeps its own licence: the Kaldi augmentation
scripts under `fabench/dataprep/noisemix/kaldi/` remain **Apache-2.0** (their
`COPYING` and `PROVENANCE.md` sit beside them); the PolyForm licence covers
Olewave's own code.
