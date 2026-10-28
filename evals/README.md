# evals, how each system was run and what it produced

`fabench/` is the benchmark's code. **`evals/` is the record of running it.**
For every system it holds the environment it ran in and the data and
parameters it was given. It also holds the command that drove it and the
output it produced. Nothing here is imported by the package. A sweep can be re-read, re-scored or audited
entirely from this directory.

| The question | What answers it |
|---|---|
| in what environment? | `<kind>/<tool>/download_and_install.sh` and `requirements.lock` |
| with what parameters? | `<kind>/<tool>/config.yaml`, the recipe's own definition |
| on what data? | `<cell>/config.yaml`, the generated cell config, in the cell |
| driven how? | `run_evals.sh`, `run_evals_parallel.sh` |
| producing what? | `<cell>/hyp.jsonl` **and** its scores, one cell per directory |
| what happened? | `<kind>/<tool>/log/` and `log/summary.tsv` |
| on what hardware? | `env.sh`, through `FABENCH_CUDA_DEVICES` and `FABENCH_THREADS` |

Because every alignment is persisted, a metric change is a **rescore**
(`run_evals.sh --stage 3`) rather than a re-run.

## Layout

A cell is `<lang>/<corpus>/<subset>/<condition>`, with `origin` for
un-augmented audio. Everything about one cell sits in one directory.

```
evals/aligners/mfa/
  download_and_install.sh     one-shot environment setup
  config.yaml                 the recipe, with version pin, params and adapter
  venv/ | repo/               its own interpreter and checkout
  worker.py                   what runs inside that interpreter
  log/                        per-cell logs
  en/buckeye/dev/
    origin/   config.yaml  hyp.jsonl  leaderboard.csv  *.parquet
    babble/   music/  noise/  reverb/
```

Recipes are grouped by contract (`aligners/`, `timestamp_asrs/`), and then
**a system owns its subtree** rather than sprawling across the list as
siblings.

```
evals/aligners/nemo_fa/                  the official, current recipe
evals/aligners/nemo_fa/exps/conformer/   a variant of it, with its own parameters
evals/aligners/mfa/v2.0.6/               a historical version, kept runnable
```

Each of those is a full recipe with its own `config.yaml`, cells and logs. A
recipe is found by the **name it declares** in `config.yaml`, never by its
directory name, so `mfa2` stays `mfa2` in every config and leaderboard while
living at `mfa/v2.0.6/`.
`fabench.paths.tool_index()` is the one place that knows this layout. Shell
drivers find recipes with `find … -name config.yaml`.

Generated per-cell configs, logs and outputs are gitignored. All of them are
derived, and `hyp.jsonl` carries the licensed corpora's transcripts besides.
Tracked here are the recipes, meaning `config.yaml`,
`download_and_install.sh`, `worker.py` and `requirements.lock`.

## Every tool runs in its own interpreter

No adapter imports its tool into FA-Bench's process. Packages that share a
process share a dependency resolution, and these conflict. Installing whisperx
into the shared venv once moved **transformers 5.14.1 → 4.57.6 and torch 2.13
→ 2.8** under Charsiu and BFA, so their published numbers were set by another
tool's install. Grafting `sys.path` does not fix that. It is a shared
environment with extra steps, and it cannot survive a native-extension
mismatch, since a `.so` is loaded once per process.

| Tool | Interpreter |
|---|---|
| bfa, charsiu, maps | `<tool>/repo/env` |
| mfa | `<tool>/repo/mamba` (micromamba) |
| crisperwhisper, falcon, nemo_fa, neufa, parakeet_tdt, pocketsphinx, qwen3_asr, qwen3_fa, stable_ts, torchaudio_fa, unity2, whisper3, whisper_ts, whisperx | `<tool>/venv` |
| crisperwhisper_fa | shares `timestamp_asrs/crisperwhisper/venv`, the same package |
| mms_fa, torchaudio_asr | share `aligners/torchaudio_fa/venv`, the same package |
| whisperx_asr | shares `aligners/whisperx/venv` |
| olign | none, a REST client of the hosted API |
| assemblyai, aws, azure, deepgram, elevenlabs, elevenlabs_fa, google_stt, ibm, speechmatics | none, HTTPS from the shared venv |

Each declares its own in `params.venv`, and `SubprocessAligner` refuses to
load without it. They run in batches by construction, since a subprocess per
utterance would pay the model load every time.

`.venv` is a **uv** venv with **no `pip`**. Use
`uv pip install --python .venv/bin/python <pkg>`. `.venv/bin/pip` does not
exist, and a `cd` in a backgrounded shell does not persist. Both produce the
same misleading "No such file or directory".

## Commercial endpoints

Eight timestamped ASRs are paid HTTPS services rather than checkpoints. They
are `assemblyai`, `aws`, `azure`, `deepgram`, `elevenlabs`, `google_stt`,
`ibm` and `speechmatics`. All of them are Track 2 rows on the word tier, wired
through `fabench/timestamp_asrs/cloud/` with **no vendor SDK and no venv**. Eight dependency trees would undo the isolation above, the GPU host
has no PyPI route, and every one of these APIs is plain HTTPS and JSON that
`urllib` can speak.

One Track 1 row bills through the same code. `elevenlabs_fa` hands
ElevenLabs the reference transcript with the audio and gets back the time of
each word. Its recipe sits under `evals/aligners/`, its cache under
`evals/aligners/elevenlabs_fa/cache/`, and its cache key carries the
transcript as well. The cost and the caching below hold for it too, and
[its README](../fabench/aligners/elevenlabs_fa/README.md) covers the rest.

They differ from every other row in four ways the code has to answer for.

**A call costs money, so nothing is ever called twice.** Every response is
cached under `evals/timestamp_asrs/<tool>/cache/`, keyed by the SHA-256 of
the audio bytes plus the model and every request option that can change the
answer. A rescore, a restart after a crash, or a re-run to fix a scoring bug
all hit the cache and cost nothing. Change the model or an option and the key
changes, so the cache cannot serve a stale configuration. The directory is
gitignored. The payloads carry the licensed corpora's transcripts, the same
reason `hyp.jsonl` is.

Budget before starting, with `evals/timestamp_asrs/cloud_cost.py`, which
reads the real durations out of the mix manifests rather than guessing. Both
corpora across five conditions are **47,805 requests and 34.1 audio hours per
provider**. When the first four vendors were added, that came to about **$40
for each of the three that bill per second, and anywhere from $39 to $287 for
Google**, because FA-Bench sends one request per utterance and its utterances
are short. At a 2.6 s mean, a vendor rounding each request up to a 15-second
increment bills 5.8x the audio it heard. The increment, more than the rate,
is what to check before committing.

Check one utterance first.

```
evals/timestamp_asrs/cloud_check.py                 # every provider, one file
evals/timestamp_asrs/cloud_check.py deepgram        # just one
evals/timestamp_asrs/cloud_check.py --no-cache      # force a real call
```

A provider with no credential is reported and skipped, so registering them one
at a time is the normal path. `params.max_calls` caps a recipe while a key is
being tried, and `max_calls: 0` allows no call at all, so a cached cell can be
replayed with no risk of a bill.

**A key is a secret and this repo is public.** Credentials come from the
environment only, under the names `.fabench.env.example` lists,
`DEEPGRAM_STT_API_KEY`, `SPEECHMATICS_STT_API_KEY` and so on. A recipe can
point at a different variable with `params.key_env`. Google takes either
`GOOGLE_STT_API_KEY` or `GOOGLE_STT_ACCESS_TOKEN`, and falls back to
`gcloud auth print-access-token`. Put them in `.fabench.env`, which is
gitignored. Nothing reads a key out of a tracked config even if one is
written there.

**Every one of them formats text for a human by default**, turning "twenty
one" into "21" and adding capitals and punctuation. Against a gold transcript
that spells its numbers out, that scores as a recognition error although it
is none, and it would rank the vendor that formats hardest rather than the one
that hears worst. So each recipe asks for raw words. ElevenLabs Scribe has no
such switch, which is recorded in its recipe and is a real caveat on its WER.
Its timing, which the formatting does not touch, reads straight. A recognizer
is then scored on the words it returned, with no rewriting onto the reference
spelling.

**They are not reproducible the way an open checkpoint is.** The model behind
an endpoint can change without notice and without a version number, so a row
records what the service returned on the date of the run and nothing
stronger. That is a property of the systems rather than of the benchmark. Each
recipe declares `access: commercial` so the distinction is data rather than a
list someone has to maintain, and these rows belong in a commercial track
reported apart from the open-weight one rather than mixed into a single
leaderboard.

**Latency is measured per request**, because for these rows a request is the
unit of work. Each hyp record carries the wall time of the one request that
produced it as `latency_s`, with the audio it was given as `audio_s`. A
real-time factor cannot serve. On the batch path the runner computes one
`elapsed / total_audio` for the whole cell, so at concurrency 8 it reports
throughput and every utterance carries the same number. RTF also divides by
audio duration, which for a network endpoint buries a fixed per-request cost.
The same API scores RTF 0.31 on a 2.6 s utterance and 0.01 on a 60 s file.

**The network is inside the number, so it is measured too.** Before the first
paid call of a cell the adapter probes DNS, TCP and TLS to that endpoint with
no payload, and records it in each hyp record as `setup_s`. That floor is a
property of this machine's network, and only what remains of a call is the
service's, so only that remainder is comparable across vendors.
From our scoring host the floor was 38 ms to Google's us-central1, 46 ms to
ElevenLabs, 68 ms to AssemblyAI and 149 ms to Deepgram, against observed calls
around 1.4 s. So it is a few percent rather than the whole story, but a few
percent separates vendors that otherwise look tied, and all of it is an
artefact of where the sweep ran.

Note that urllib opens a new connection per request and does not pool, so
that floor is paid on every call rather than once. Over 47,805 requests it is
30 minutes for Google and two hours for Deepgram of pure handshake.

So these are a **deployment** measurement rather than a vendor benchmark. They
answer what a sweep costs in wall clock from here, and they support a ranking
among providers measured from one machine at one time. They do not support an
absolute claim about a vendor's speed and they do not reproduce on another
network. They also hold only at the concurrency the cell ran at. Cache hits
contribute nothing, by recording no latency rather than a zero. Retries, their
backoff and AssemblyAI's polling are counted separately in the hyp record, so
a slow call can be attributed to the vendor or to our own client.

`fabench/timestamp_asrs/cloud/test/test_cloud.py` covers the client with the
network stubbed. It checks each response shape and both time units, then the
cache keying, the spend cap and the retry policy, so a wiring mistake costs
nothing to find.

### Before a paid sweep

Every paid sweep runs on an account and under that vendor's terms. Check these
five points before the first paid call. For the published records, Wei Chu
manages every vendor account, and a new paid sweep starts only after Wei
confirms the list for that vendor.

1. **The account is the organisation's.** It belongs to Olewave, or to the
   organisation that will publish your scores, and one named person controls
   its plan and its settings.
2. **The vendor keeps no audio for training.** Where a request can carry the
   opt-out, the recipe sets `data_opt_out: true`, and the Deepgram and IBM
   recipes do. AssemblyAI keeps the switch in its dashboard on paid plans. AWS
   needs an AI services opt-out policy in AWS Organizations. ElevenLabs turns
   logging off on enterprise plans only.
3. **The terms allow benchmarking and publishing the scores.** Read the
   vendor's current terms on the day of the sweep and keep the date. Some
   vendors forbid benchmarking outright, and others allow it on conditions you
   must meet when you publish.
4. **The credit covers the whole sweep.** Price the sweep with
   `cloud_cost.py`, then hold the price against the plan's balance and its
   rate limits. A free plan is often for noncommercial use and one account per
   person.
5. **The key stays in `.fabench.env`.** Never print it, commit it or pass it
   on a command line, where the shell history keeps it.

## Using the box, `env.sh`

Every driver sources it, and it is the one place that decides how a sweep uses
the machine rather than what it measures.

- `FABENCH_CUDA_DEVICES` says which GPUs. **Unset** means all of them,
  **empty** means none (CPU), and a list means those.
- `FABENCH_THREADS` sets the BLAS and OMP threads per process, default 1.
  Unpinned, a multi-tool sweep thrashes. We measured a 40× throughput loss on
  a 48-core box.

Values come from `.fabench.env`, and an exported variable always wins.

## Running it in three stages

```bash
./run_evals.sh                             # stages 1 and 3, align clean then score
./run_evals.sh --use-noisy-dataset         # adds stage 2, the same cells on noisy audio
./run_evals.sh --stage 3 mfa               # rescore mfa from saved hyp, no GPU
./run_evals.sh --stage 2 --stop-stage 2 \
               --use-noisy-dataset true    # the explicit Kaldi form
```

| Stage | Does | Writes |
|---|---|---|
| 1 | align on clean audio | `<tool>/en/<corpus>/<subset>/origin/hyp.jsonl` |
| 2 | align on noise-augmented audio (**only** with `--use-noisy-dataset`) | `…/<subset>/<condition>/hyp.jsonl` |
| 3 | score from the saved hypotheses | the same cell directory |

Stage 2 reads the shadow roots under `FABENCH_SHADOW`. `fabench prepare`
builds them from your staged corpora, as
[`datasets/prep/README.md`](../datasets/prep/README.md) explains.

Options are Kaldi-style (`parse_options.sh`). Each driver declares its knobs
as shell variables with defaults, and `--knob value` assigns one, with a dash
in the option standing for an underscore in the variable. An unknown option is
an error rather than a silently ignored flag. The top-level `run_all.sh` uses
the same parser.

Clean and noisy are stages rather than separate tools. The same recipe runs
over different audio, so the system list stays a list of systems. Noisy
hypotheses land in a sibling condition directory and never overwrite the
clean baseline they are compared against.

Stage 3 scores **one tool** into its own cell. A cross-tool leaderboard is
one `fabench score` over a cell config that lists every tool, and
`gen_config.py --tools` writes one. Score the two tracks apart. Aligners are
given the reference transcript and timestamped ASRs decode their own words, so
the two must never be ranked head to head.

## Licences of the systems under test

FA-Bench's own code is Apache 2.0. The systems it runs are not part of it.
Each recipe fetches its tool and its weights from upstream into its own
environment, under the upstream terms, and FA-Bench redistributes none of
them. The table records what each recipe fetches, checked in October 2026.
Read the upstream terms before you run a row commercially, and before you
pass on an environment you built.

| Recipe | Code | Weights or model | Worth knowing |
|---|---|---|---|
| `bfa` | bournemouth-forced-aligner, GPL-3.0 | Tabahi/CUPE-2i, GPL-3.0 | uses phonemizer and espeak-ng, GPL-3.0 or later |
| `charsiu` | lingjzhu/charsiu, MIT | charsiu/en_w2v2_fc_10ms | the model card states no licence |
| `crisperwhisper`, `crisperwhisper_fa` | crisperwhisper, MIT | nyrahealth/CrisperWhisper, CC BY-NC 4.0 | noncommercial weights |
| `falcon` | MLSpeech/FALCON, MIT | MLSpeech/FALCON-weights, MIT | trained on TIMIT and Buckeye |
| `maps` | MasonPhonLab/MAPS, MIT | the ensemble in the MAPS repository, MIT | trained on TIMIT and Buckeye |
| `mfa` (2.0 and 3.4) | Montreal Forced Aligner, MIT | english_us_arpa acoustic model and dictionary, CC BY 4.0 | attribution |
| `mms_fa` | torchaudio, BSD-2-Clause | torchaudio MMS_FA, CC BY-NC 4.0 | noncommercial weights |
| `nemo_fa` | NVIDIA NeMo, Apache-2.0 | stt_en_conformer_ctc_large and stt_en_fastconformer_hybrid_large_pc, CC BY 4.0 | attribution |
| `neufa` | thuhcsi/NeuFA, no licence | the authors' checkpoint, unreleased | no upstream licence, and its G2P uses sequitur-g2p, GPL-2.0-only |
| `pocketsphinx` | cmusphinx/pocketsphinx, BSD-style | the bundled en-us model and CMUdict, BSD-style | none |
| `qwen3_fa` | qwen-asr, Apache-2.0 | Qwen/Qwen3-ForcedAligner-0.6B, Apache-2.0 | none |
| `stable_ts` | jianfch/stable-ts, MIT | Whisper base, MIT | none |
| `torchaudio_fa` | torchaudio, BSD-2-Clause | WAV2VEC2_ASR_BASE_960H, MIT | mode B uses phonemizer and espeak-ng, GPL-3.0 or later |
| `unity2` | seamless_communication, MIT | unity2_aligner, MIT, with a tokenizer from facebook/seamless-streaming, CC BY-NC 4.0 | noncommercial tokenizer, and the unit extractor's licence is not stated |
| `whisperx`, `whisperx_asr` | whisperx, BSD-2-Clause | wav2vec2 960h and faster-whisper large-v3, MIT | none |
| `parakeet_tdt` | NVIDIA NeMo, Apache-2.0 | nvidia/parakeet-tdt-0.6b-v3, CC BY 4.0 | attribution |
| `qwen3_asr` | qwen-asr, Apache-2.0 | Qwen/Qwen3-ASR-1.7B, Apache-2.0 | none |
| `torchaudio_asr` | torchaudio, BSD-2-Clause | WAV2VEC2_ASR_BASE_960H, MIT | none |
| `whisper3` | transformers, Apache-2.0 | openai/whisper-large-v3, Apache-2.0 | none |
| `whisper_ts` | linto-ai/whisper-timestamped, AGPL-3.0 | Whisper large-v3, MIT | AGPL code, and dtw-python is GPL-3.0 or later |
| `*_on_*` cascades | the two systems they chain | the two systems they chain | each cascade carries the terms of both |
| cloud rows and `elevenlabs_fa`, `olign`, `olign_v1` | a web API, called over HTTPS | the vendor's service | the vendor's terms of service apply to every call |

`fabench[maps]` pulls in g2p-en, which lists the GPL package `distance` as a
requirement and never imports it.

## Splits

**Membership is defined by committed lists rather than by code.** They are
`datasets/languages/en/{timit,buckeye}/split/*.list`, one
`<speaker_id> <utterance_id>` per line. Anything that trains on these corpora
reads the same lists, so a training recipe and the benchmark cannot drift
apart.

| Corpus | Cell | Utts | Speakers |
|---|---|---|---|
| TIMIT | `train` | 3,696 | 462 |
| TIMIT | `dev` | 400 | 50 |
| TIMIT | `core_test` | 192 | 24 |
| Buckeye | `train` | 13,473 | 24 |
| Buckeye | `dev` | 4,456 | 8 |
| Buckeye | `test` | 4,513 | 8 |

**TIMIT's SA sentences are excluded from every cell.** The corpus
documentation says they must not be used for training or test, so `train` is
3,696 rather than 4,620.

**Buckeye's split is stratified on the corpus's own sex × age design**
(6/6/6/6 in train, 2/2/2/2 in each of dev and test).

Sweeps evaluate the held-out cells only. `train` is the training split, so a
number measured there says nothing about generalisation.
