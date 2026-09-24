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
| deepgram, assemblyai, elevenlabs, google_stt | none: HTTPS from the shared venv |

Each declares its own in `params.venv`, and `SubprocessAligner` refuses to load
without it. Batch by construction — a subprocess per utterance would pay the
model load every time.

`.venv` is a **uv** venv with **no `pip`**. Use
`uv pip install --python .venv/bin/python <pkg>`; `.venv/bin/pip` does not
exist, and a `cd` in a backgrounded shell does not persist — both produce the
same misleading "No such file or directory".

## Commercial endpoints

Four timestamped ASRs are paid HTTPS services rather than checkpoints:
`deepgram`, `assemblyai`, `elevenlabs`, `google_stt`. They are Track 2,
one-step, word tier, and they are wired through
`fabench/timestamp_asrs/cloud/` with **no vendor SDK and no venv** — four
dependency trees would undo the isolation above, and the GPU host has no PyPI route,
while all four APIs are plain HTTPS and JSON that `urllib` can speak.

They differ from every other row in four ways the code has to answer for.

**A call costs money, so nothing is ever called twice.** Every response is
cached under `evals/timestamp_asrs/<tool>/cache/`, keyed by the SHA-256 of the
audio bytes plus the model and every request option that can change the answer.
A rescore, a restart after a crash, or a re-run to fix a scoring bug all hit the
cache and cost nothing. Change the model or an option and the key changes, so
the cache cannot serve a stale configuration. The directory is gitignored: the
payloads carry the licensed corpora's transcripts, the same reason `hyp.jsonl`
is.

Budget before starting, with `evals/timestamp_asrs/cloud_cost.py`, which reads
the real durations out of the mix manifests rather than guessing. Both corpora
across five conditions are **47,805 requests and 34.1 audio hours per
provider**, which is about **$40 for the three vendors that bill per second and
anywhere from $39 to $287 for Google**, because FA-Bench sends one request per
utterance and its utterances are short. At a 2.6 s mean, a vendor rounding each
request up to a 15-second increment bills 5.8x the audio it heard. The
increment, not the rate, is what to check before committing.

Check one utterance first:

```
evals/timestamp_asrs/cloud_check.py                 # every provider, one file
evals/timestamp_asrs/cloud_check.py deepgram        # just one
evals/timestamp_asrs/cloud_check.py --no-cache      # force a real call
```

A provider with no credential is reported and skipped, so registering them one
at a time is the normal path. `params.max_calls` caps a recipe while a key is
being tried.

**A key is a secret and this repo is public.** Credentials come from the
environment only — `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY`,
`ELEVENLABS_API_KEY`, and for Google either `GOOGLE_STT_API_KEY` or
`GOOGLE_STT_ACCESS_TOKEN`, falling back to `gcloud auth print-access-token`.
Put them in `.fabench.env`, which is gitignored. Nothing reads a key out of a
tracked config even if one is written there.

**Every one of them formats text for a human by default**, turning "twenty one"
into "21" and adding capitals and punctuation. Against a gold transcript that
spells its numbers out, that is not a recognition error but it scores as one,
and it would rank the vendor that formats hardest rather than the one that
hears worst. So each recipe asks for raw words. ElevenLabs Scribe has no such
switch, which is recorded in its recipe and is a real caveat on its WER — its
timing, which the formatting does not touch, reads straight.

**They are not reproducible the way an open checkpoint is.** The model behind an
endpoint can change without notice and without a version number, so a row
records what the service returned on the date of the run and nothing stronger.
That is a property of the systems, not of the benchmark. Each recipe declares
`access: commercial` so the distinction is data rather than a list someone has
to maintain, and these rows belong in a commercial track reported apart from the
open-weight one rather than mixed into a single leaderboard.

**Latency is measured per request**, because for these rows a request is the
unit of work. `rtf_mean` cannot serve: on the batch path the runner computes one
`elapsed / total_audio` for the whole cell, so at concurrency 8 it reports
throughput and every utterance carries the same number. RTF also divides by
audio duration, which for a network endpoint buries a fixed per-request cost --
the same API scores RTF 0.31 on a 2.6 s utterance and 0.01 on a 60 s file.

`fabench/score/latency.py` reports the distribution and the decomposition
instead: `lat_p50_s`, `lat_p90_s`, `lat_p95_s`, `lat_p99_s`, `lat_max_s`, and a
least-squares split of `latency = lat_fixed_s + lat_per_audio_s x duration`
with its `lat_r2`. Percentiles rather than a mean because one retried call
outweighs a hundred fast ones in a mean while moving p50 not at all, and p95 is
what a 48,000-request sweep actually waits on. The split because it separates
what a request costs before any audio is processed from the rate once it is,
which is exactly what RTF conflates.

**The network is inside the number, so it is measured too.** Before the first
paid call of a cell the adapter probes DNS + TCP + TLS to that endpoint with no
payload, and reports it as `lat_setup_s` with `lat_fixed_net_s` = `lat_fixed_s`
minus it. The first is a property of this machine's network, the second of the
service, and only the second is comparable across vendors. From our scoring host the floor
is 38 ms to Google's us-central1, 46 ms to ElevenLabs, 68 ms to AssemblyAI and
149 ms to Deepgram, against observed calls around 1.4 s. So it is a few percent
rather than the whole story, but a few percent separates vendors that otherwise
look tied, and all of it is an artefact of where the sweep ran.

Note that urllib opens a new connection per request and does not pool, so that
floor is paid on every call rather than once. Over 47,805 requests it is 30
minutes for Google and two hours for Deepgram of pure handshake.

So these are a **deployment** measurement, not a vendor benchmark. They answer
what a sweep costs in wall clock from here, and they support a ranking among
providers measured from one machine at one time. They do not support an
absolute claim about a vendor's speed and they do not reproduce on another
network. They also hold only at the concurrency the cell ran at. Cache hits
contribute nothing, by recording no latency rather than a zero, and retries,
their backoff and AssemblyAI's polling are counted separately in the hyp
record, so a slow call can be attributed to the vendor or to our own client.

`fabench/timestamp_asrs/cloud/test/test_cloud.py` covers the response shapes,
the millisecond and nanosecond time forms, the cache keying, the spend cap and
the retry policy with the network stubbed, so a wiring mistake costs nothing to
find.

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

## Checking the per-word claims

Most numbers in the paper come out of `summary/`, so anyone can read them off
the published tables. Five do not. They split words by what the recogniser did
to each one -- kept it, swapped it, dropped it, invented it -- and no pooled
per-cell metric can answer that.

```bash
./analyze_recognition_effects.py                       # buckeye dev, clean
./analyze_recognition_effects.py --corpus timit --subset core_test
```

It reads the same hypotheses the scorer reads, aligns each system's words to
the gold words with the scorer's own Needleman-Wunsch, and prints every quoted
figure. Two readings of "a word the recogniser missed" are printed side by
side, because the phrase is ambiguous and the choice moves the answer: counting
substitutions as missed gives a 2.2x ratio on Qwen3-ASR, counting only outright
deletions gives 1.9x. The paper quotes the first.

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
