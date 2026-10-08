# ElevenLabs forced aligner

ElevenLabs offers a forced alignment endpoint beside its Scribe recognizer.
You send it a recording and the words spoken in it, and it returns a start and
an end time for each word. FA-Bench hands it the reference transcript, so it
runs in Track 1 and is scored beside MFA and Olign. Scribe keeps its own row
in Track 2, where it decodes the words itself.

- **Mode.** A, the reference transcript.
- **Granularity.** Word only. The response carries word and character times
  and no phones, so the row is absent from the phone tables by construction.
- **Confidence.** None. Each word comes back with an alignment loss on no
  stated scale, so the adapter leaves the confidence field empty.
- **Batch.** Yes. `align_corpus()` keeps `params.concurrency` uploads in
  flight on a thread pool.
- **Status.** Off by default. The recipe ships with `enabled: false`, and the
  row has no published numbers yet.

## How a request is built

The adapter posts each utterance to
`https://api.elevenlabs.io/v1/forced-alignment` as a multipart upload. The
`file` part is the audio. The `text` part is the reference words, joined with
single spaces. The key travels in the `xi-api-key` header.

```bash
curl https://api.elevenlabs.io/v1/forced-alignment \
  -H "xi-api-key: $ELEVENLABS_STT_API_KEY" \
  -F file=@utterance.wav \
  -F text="she had your dark suit in greasy wash water all year"
```

The response lists the words in order, with times in seconds. Here is its
shape, with the `characters` list left out and the values for illustration.

```json
{
  "words": [
    {"text": "she", "start": 0.12, "end": 0.31, "loss": 0.42},
    {"text": "had", "start": 0.31, "end": 0.52, "loss": 0.57}
  ],
  "loss": 0.49
}
```

The adapter keeps each word's text, start and end. It skips any entry that
holds only whitespace, since a space between two words marks no boundary. The
response total goes into the output's meta as `alignment_loss`.

The runner then maps the returned words back onto the reference tokens before
it writes `hyp.jsonl`, as it does for MFA and every other Track 1 row. The row
is scored on where it puts the boundaries of the words it was given.

## Credentials

The adapter uses the same key as the Scribe row. Put it in `.fabench.env` at
the repository root. That file is untracked, and a key never goes in a config.

```bash
# .fabench.env
ELEVENLABS_STT_API_KEY=<your key>
```

`ELEVENLABS_API_KEY` and `XI_API_KEY` are read too, in that order, when
`ELEVENLABS_STT_API_KEY` is unset. A recipe can name a different variable with
`params.key_env`.

## Check the key on one utterance

A forced aligner needs the words as well as the audio, so the check script
takes both.

```bash
evals/timestamp_asrs/cloud_check.py elevenlabs_fa \
  --audio utterance.wav --text "she had your dark suit in greasy wash water all year"
```

It prints each word with its start and end. Without `--audio` and `--text` it
skips this row, because timing words nobody said proves nothing and still
bills. Add `--raw` to print the response before the parser reads it.

## Budget before you run

ElevenLabs bills forced alignment at its Speech to Text rate, and FA-Bench
sends one request per utterance. Every split of both corpora, on clean audio
and under the four degradations, comes to 47,805 requests and 34.1 audio
hours. The cost script prices that grid from the real durations.

```bash
evals/timestamp_asrs/cloud_cost.py                  # the whole grid
evals/timestamp_asrs/cloud_cost.py --conditions 1   # clean audio only
evals/timestamp_asrs/cloud_cost.py --actual         # what the cache says was spent
```

The script prices this row at the Scribe list rate. Check that against your
own plan before you quote it.

## Run one cell first

`enabled: false` keeps the row out of `rescore_all.sh` and the pooled tables.
A run that names it still goes ahead, so you can try one cell before you
commit to the grid. Cap the spend in the recipe while you do.

```yaml
params:
  max_calls: 200            # TIMIT core test is 192 utterances
```

Then align TIMIT core test on clean audio and score it.

```bash
FABENCH_CELLS="timit core_test" evals/run_evals.sh elevenlabs_fa
```

Every response is cached under `evals/aligners/elevenlabs_fa/cache/`. The key
covers the audio, the reference text and every option that can change the
answer. A restart or a rescore reads the cache and costs nothing, and
`max_calls: 0` replays a cached cell with no chance of a bill.

When the cell looks right, take `max_calls` out and set `enabled: true`. Then
run the grid.

```bash
evals/run_evals.sh --use-noisy-dataset elevenlabs_fa
```

If the credit runs out partway, ElevenLabs refuses the next request and the
adapter stops the cell there. The responses already cached stay, so a run
after a top-up picks up where the last one stopped.

## Tests

```bash
.venv/bin/python -m pytest fabench/aligners/elevenlabs_fa
```

The tests stub the network and bill nothing. Among other things they check
that the transcript is part of the cache key, and that adding it left the
Scribe row's cached responses where they were.
