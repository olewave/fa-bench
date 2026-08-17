# evals — how each system was run, and what it produced

`fabench/` is the benchmark's code; **`evals/` is the record of running it**:
for every system, the environment it ran in, the data and parameters it was
given, the command that drove it, and the output it produced. Nothing here is
imported by the package — a sweep can be re-read, re-scored or audited entirely
from this directory.

| The question | What answers it |
|---|---|
| in what environment? | `<kind>/<tool>/download_and_install.sh` + `requirements.lock` |
| with what parameters? | `<kind>/<tool>/config.yaml` — the recipe's own definition |
| on what data? | `<cell>/config.yaml` — the generated cell config, in the cell |
| driven how? | `run_evals.sh`, `run_evals_parallel.sh`, `rescore_all.sh` |
| producing what? | `<cell>/hyp.jsonl` **and** its scores, one cell per directory |
| what happened? | `<kind>/<tool>/log/` and `log/summary.tsv` |
| on what hardware? | `env.sh` — `FABENCH_CUDA_DEVICES`, `FABENCH_THREADS` |

Because every alignment is persisted, a metric change is a **rescore, not a
re-run** (`rescore_all.sh`). The leaderboards derived from these outputs live in
`summary/`.

## Layout

A cell is `<lang>/<corpus>/<subset>/<condition>`, with `origin` for un-augmented
audio. Everything about one cell sits in one directory:

```
evals/aligners/mfa/
  download_and_install.sh     one-shot environment setup
  config.yaml                 the recipe: version pin, params, adapter
  venv/ | repo/               its own interpreter and checkout
  worker.py                   what runs inside that interpreter
  log/                        per-cell logs
  en/buckeye/dev/
    origin/   config.yaml  hyp.jsonl  leaderboard.csv  *.parquet
    babble/   music/  noise/  reverb/
```

Grouped by contract (`aligners/`, `timestamp_asrs/`), then **a system owns its
subtree** rather than sprawling across the list as siblings:

```
evals/aligners/olign/          the official, current recipe
              /exps/<name>/    a manipulation of it — ablations, sweeps
              /v<version>/     a historical version, kept runnable
```

Each of those is a full recipe with its own `config.yaml`, cells and logs. A
recipe is found by the **name it declares** in `config.yaml`, never by its
directory name, so `olign_noisy` stays `olign_noisy` in every config and
leaderboard while living at `olign/exps/noisy/`.
`fabench.paths.tool_index()` is the one place that knows this layout; shell
drivers find recipes with `find … -name config.yaml`.

Generated per-cell configs, logs and outputs are gitignored — all derived, and
`hyp.jsonl` carries the licensed corpora's transcripts besides. Tracked here are
the recipes: `config.yaml`, `download_and_install.sh`, `worker.py`,
`requirements.lock`.

## Every tool runs in its own interpreter

No adapter imports its tool into FA-Bench's process. Packages that share a
process share a dependency resolution, and these conflict: installing whisperx
into the shared venv once moved **transformers 5.14.1 → 4.57.6 and torch 2.13 →
2.8** under Charsiu and BFA, so their published numbers were set by another
tool's install. `sys.path` grafting does not fix that — it is a shared
environment with extra steps, and it cannot survive a native-extension mismatch,
since a `.so` is loaded once per process.

| Tool | Interpreter |
|---|---|
| bfa, charsiu, maps | `<tool>/repo/env` |
| mfa | `<tool>/repo/mamba` (micromamba) |
| crisperwhisper, neufa, parakeet_tdt, qwen3_fa, stable_ts, torchaudio_fa, whisperx | `<tool>/venv` |
| crisperwhisper_fa | shares `timestamp_asrs/crisperwhisper/venv` — same package |
| olign | none: a REST client to a running server |

Each declares its own in `params.venv`, and `SubprocessAligner` refuses to load
without it. Batch by construction — a subprocess per utterance would pay the
model load every time.

`.venv` is a **uv** venv with **no `pip`**. Use
`uv pip install --python .venv/bin/python <pkg>`; `.venv/bin/pip` does not
exist, and a `cd` in a backgrounded shell does not persist — both produce the
same misleading "No such file or directory".

## Using the box: `env.sh`

Sourced by every driver, and the one place that decides how a sweep uses the
machine rather than what it measures:

- `FABENCH_CUDA_DEVICES` — which GPUs. **Unset** means all of them; **empty**
  means none (CPU); a list means those.
- `FABENCH_THREADS` — BLAS/OMP threads per process, default 1. Unpinned, a
  multi-tool sweep thrashes: measured 40× throughput loss on a 48-core box.

Values come from `.fabench.env`, and an exported variable always wins.

## Running it: three stages

```bash
./run_evals.sh                             # stages 1 + 3: align clean, then score
./run_evals.sh --use-noisy-dataset         # + stage 2: same cells, noisy audio
./run_evals.sh --stage 3 mfa               # rescore mfa from saved hyp, no GPU
./run_evals.sh --stage 2 --stop-stage 2 \
               --use-noisy-dataset true    # explicit Kaldi form
```

| Stage | Does | Writes |
|---|---|---|
| 1 | align on clean audio | `<tool>/en/<corpus>/<subset>/origin/hyp.jsonl` |
| 2 | align on noise-augmented audio (**only** with `--use-noisy-dataset`) | `…/<subset>/<condition>/hyp.jsonl` |
| 3 | score from the saved hypotheses | the same cell directory |

Options are Kaldi-style (`parse_options.sh`): each driver declares its knobs as
shell variables with defaults, `--knob value` assigns them, dashes map to
underscores, and an unknown option is an error rather than a silently ignored
flag. `run_all.sh` uses the same parser.

Clean and noisy are stages rather than separate tools: the same recipe over
different audio, so the system list stays a list of systems. Noisy hypotheses
land in a sibling condition directory, never overwriting the clean baseline they
are compared against.

Stage 3 scores **one tool** into its own cell. The cross-tool leaderboards under
`summary/<kind>/` are a different artefact, pooled from every tool by
`rescore_all.sh`, which scores the two tracks separately — aligners are given
the reference transcript, timestamped ASRs decode their own words, and the two
must not be ranked head to head.

## Splits

**Membership is defined by committed lists, not by code**:
`datasets/languages/en/{timit,buckeye}/split/*.list`, one
`<speaker_id> <utterance_id>` per line. Anything that trains on these corpora
reads the same lists, so a training recipe and the benchmark cannot drift apart.

| Corpus | Cell | Utts | Speakers |
|---|---|---|---|
| TIMIT | `train` | 3,696 | 462 |
| TIMIT | `dev` | 400 | 50 |
| TIMIT | `core_test` | 192 | 24 |
| Buckeye | `train` | 13,473 | 24 |
| Buckeye | `dev` | 4,456 | 8 |
| Buckeye | `test` | 4,513 | 8 |

**TIMIT's SA sentences are excluded from every cell** — the corpus
documentation says they must not be used for training or test, so `train` is
3,696 rather than 4,620.

**Buckeye's split is stratified on the corpus's own sex × age design** (6/6/6/6
in train, 2/2/2/2 in each of dev and test).

Sweeps evaluate the held-out cells only. `train` is the training split, so a
number measured there says nothing about generalisation.
