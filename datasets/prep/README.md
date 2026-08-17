# datasets/prep/ — how the staged corpora become benchmark data

`datasets/` says what the data **is**: which corpora, which splits, which
per-corpus options. This folder says how it was **produced** — the commands and
parameters that turn a licensed copy you staged into canonical gold, and gold
into the four noisy conditions.

The scripts themselves live in `fabench/dataprep/`, where they are testable and
importable. What is recorded here is the *invocation*: which script, with which
parameters, in which order. That is the part a result depends on and the part
no docstring captures.

> **Why here and not `evals/`.** `evals/` records how a *system under test* was
> run, and its per-cell configs and logs are gitignored because they are
> machine-specific. These parameters are the opposite: the SNR sets and RIR mix
> below **define the benchmark's noise conditions**, so they are published
> methodology and belong in a tracked file beside the dataset they describe.

## The order

```
  staged corpus  --(1) ingest---->  canonical gold
  canonical gold --(2) augment--->  noisy/<type>/<utt>.wav
  gold + noisy   --(3) shadow---->  a root that LOOKS clean, per condition
                 --(4) configs-->   evals/<kind>/<tool>/configs/noisy_*.yaml
```

Step 4 is `evals/gen_noisy_configs.py` and is recorded in `evals/README.md`;
everything before it is here.

| Step | Script | Recorded in |
|---|---|---|
| 1. ingest | `fabench ingest` | [`ingest.sh`](ingest.sh) |
| 2. augment | `fabench/dataprep/noisemix/make_noisy.py` | [`augment.sh`](augment.sh) |
| 3. shadow roots | `fabench/dataprep/noisemix/shadow_root.py` | [`augment.sh`](augment.sh) |

## The noise conditions, and why these numbers

The four conditions follow Kaldi's
[**`egs/voxceleb/v2/run.sh`**](https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh)
exactly — same scripts, same parameters — so they match what the field actually
trains on rather than an invented SNR sweep:

| Condition | Source | Parameters |
|---|---|---|
| `reverb` | simulated RIRs | 0.5 smallroom + 0.5 mediumroom, `rvb-prob 1`, pointsource/isotropic noise probability **0** (reverb only) |
| `noise` | MUSAN noise | `--fg-interval 1 --fg-snrs 15:10:5:0` |
| `music` | MUSAN music | `--bg-snrs 15:10:8:5 --num-bg-noises 1` |
| `babble` | MUSAN speech | `--bg-snrs 20:17:15:13 --num-bg-noises 3:4:5:6:7` |

These are **not** the same axis as `fabench run`'s condition matrix
(white/pink/musan_ambient/babble at 20/15/10 dB, mixed in-process at a fixed
sample rate by `fabench/noise/`). That one is sample-aligned by construction so
clean gold transfers with zero offset correction. The Kaldi conditions here are
materialised to disk instead, which is why they need shadow roots — and why
`reverb` is reported separately: it is **not** additive, so it sits outside the
frozen v1 scope contract (`channel: additive_noise_only`) and is an
out-of-scope probe, not a headline result.

## Determinism

Kaldi's `augment_data_dir.py` and `reverberate_data_dir.py` both call
`random.seed(args.random_seed)` (default `123`), so the SNR and noise-file
choices are fixed: re-running the recipe emits byte-identical `wav.scp` and
byte-identical audio. `make_noisy.py` is a port of `make_noisy.sh`, which is
kept beside it as the reference the port was verified against.

## Is this language-agnostic?

**The recipe is; the code underneath is not yet.** Worth knowing before you add
a second language under `datasets/languages/`.

| Layer | Agnostic? | Why |
|---|---|---|
| `ingest.sh` | **yes** | passes corpus names to `fabench ingest`, which resolves everything through `datasets/languages/<lang>/` |
| `augment.sh` | **yes** | the corpus list is read from the tree, not hardcoded; the four Kaldi conditions are additive noise and RIRs, which do not care what is being said |
| `shadow_root.py` | **no** | `--corpus` is `choices=("timit", "buckeye")`, and the clean-root and directory-name maps are keyed on those two names |
| `make_noisy.py` | **no** | `DEFAULT_SPLITS` names the seven English splits, and split-to-corpus is a `startswith("timit"/"buckeye")` test |

So `augment.sh` picks up a new corpus automatically and then reports it as
skipped, rather than pretending to have augmented it — the two Python scripts
need per-corpus wiring first, the same way a new corpus needs a processor under
`fabench/dataprep/datasets/<lang>/`.

`datasets/prep/` therefore sits beside `languages/` rather than inside
`languages/en/`: the noise recipe is a benchmark-wide methodological choice, not
an English one, and duplicating it per language would be the wrong place for the
inevitable second copy to drift.

## What is NOT here

Absolute paths to your staged corpora, MUSAN or RIRS. Those are machine
settings and live in `.fabench.env` (`FABENCH_*`); every script below reads
them from the environment, so these files stay portable and licensed paths
never enter the history.
