# datasets/prep, how the staged corpora become benchmark data

`datasets/` says what the data **is**, meaning which corpora, which splits and
which per-corpus options. This folder says how it was **produced**, meaning
the commands and parameters that turn a licensed copy you staged into
canonical gold, and gold into the four noisy conditions.

The scripts themselves live in `fabench/dataprep/`, where they are testable
and importable. What is recorded here is the *invocation*, which script ran
with which parameters and in which order. That is the part a result depends
on and the part no docstring captures.

> **Why here rather than in `evals/`.** `evals/` records how a *system under
> test* was run, and its per-cell configs and logs are gitignored because they
> are machine-specific. These parameters are the opposite. The SNR sets and
> RIR mix below **define the benchmark's noise conditions**, so they are
> published methodology and belong in a tracked file beside the dataset they
> describe.

## The order

```
  staged corpus  --(1) ingest---->  canonical gold
  canonical gold --(2) augment--->  noisy/<type>/<utt>.wav
  gold + noisy   --(3) shadow---->  a root that LOOKS clean, per condition
                 --(4) configs-->   evals/<kind>/<tool>/en/<corpus>/<subset>/<condition>/config.yaml
```

Step 4 is `evals/gen_noisy_configs.py` and is recorded in `evals/README.md`.
Everything before it is here.

| Step | Script | Recorded in |
|---|---|---|
| 1. ingest | `fabench ingest` | [`ingest.sh`](ingest.sh) |
| 2. augment | `fabench/dataprep/noisemix/make_noisy.py` | [`augment.sh`](augment.sh) |
| 3. shadow roots | `fabench/dataprep/noisemix/shadow_root.py` | [`augment.sh`](augment.sh) |

## What step 2 needs

Step 2 does not run from this repository alone. It needs five things.

1. **The gold-prep recipe's Kaldi data directories**, named with
   `make_noisy.py --ref <dir>` (or `REF=<dir>`). The script reads
   `<dir>/data/golden/<split>/wav.scp` with its `utt2spk`, `segments` and
   `reco2spk`. Each `wav.scp` line pipes a source file through
   `ffmpeg -hide_banner -loglevel error -i <src> -ar 16000 -ac 1 -af "adelay=475,apad=pad_dur=0.475" -f wav - |`,
   one line per TIMIT utterance (`dr1_felc0_si1386`) and one per Buckeye
   recording (`s0701a`). That recipe is not published here. The augmentation
   draws its noise in the order of the `wav.scp` lines, so rebuilding the
   audio bit for bit needs those files as they were, line order included.
   Without `--ref` the script stops with an error.
2. **`wav-reverberate`**, the Kaldi binary that does the mixing. Build it with
   `git submodule update --init tools/kaldi && tools/build_wav_reverberate.sh`.
   The script explains why a different BLAS changes the output bytes.
3. **sox and ffmpeg** on `PATH`.
4. **MUSAN** ([OpenSLR 17](https://www.openslr.org/17/)) at `$MUSAN`, and
   **RIRS_NOISES** ([OpenSLR 28](https://www.openslr.org/28/)) at `$RIRS`.
5. Kaldi's `utils/`, linked in at run time from the same submodule. See
   `fabench/dataprep/noisemix/kaldi/PROVENANCE.md`.

Its output is padded by 475 ms at both ends, on purpose, and step 3 cuts every
file back to the samples and length of its clean source.

## The noise conditions, and why these numbers

The four conditions follow Kaldi's
[**`egs/voxceleb/v2/run.sh`**](https://github.com/kaldi-asr/kaldi/blob/master/egs/voxceleb/v2/run.sh)
exactly, with the same scripts and the same parameters, so they match what
the field trains on rather than an invented SNR sweep.

| Condition | Source | Parameters |
|---|---|---|
| `reverb` | simulated RIRs | 0.5 smallroom + 0.5 mediumroom, `rvb-prob 1`, pointsource/isotropic noise probability **0** (reverb only) |
| `noise` | MUSAN noise | `--fg-interval 1 --fg-snrs 15:10:5:0` |
| `music` | MUSAN music | `--bg-snrs 15:10:8:5 --num-bg-noises 1` |
| `babble` | MUSAN speech | `--bg-snrs 20:17:15:13 --num-bg-noises 3:4:5:6:7` |

These are a different axis from the condition matrix of `fabench run`, which
mixes white, pink, MUSAN ambient and babble noise at 20, 15 and 10 dB
in-process at a fixed sample rate (`fabench/noise/`). That matrix is
sample-aligned by construction, so clean gold transfers with zero offset
correction. The Kaldi conditions here are materialised to disk instead, which
is why they need shadow roots. It is also why `reverb` is reported
separately. Reverberation is a convolution rather than an addition, so it
sits outside the frozen v1 scope contract (`channel: additive_noise_only`) as
a probe rather than a headline result.

## Determinism

Kaldi's `augment_data_dir.py` seeds with `random.seed(args.random_seed)`,
default `123`, and `reverberate_data_dir.py` does the same with default `0`.
Neither is overridden, so the SNR, noise-file and impulse choices are fixed,
and re-running the recipe emits byte-identical `wav.scp` and byte-identical
audio. The draws follow the order of the `wav.scp` lines, so that order is
part of the seed. `make_noisy.py` is a port of `make_noisy.sh`, which is kept
beside it as the reference the port was verified against.

## Is this language-agnostic?

**The recipe is. The code underneath is not yet.** Worth knowing before you
add a second language under `datasets/languages/`.

| Layer | Agnostic? | Why |
|---|---|---|
| `ingest.sh` | **yes** | passes corpus names to `fabench ingest`, which resolves everything through `datasets/languages/<lang>/` |
| `augment.sh` | **yes** | the corpus list is read from the tree rather than hardcoded, and the four Kaldi conditions are additive noise and RIRs, which do not care what is being said |
| `shadow_root.py` | **no** | `--corpus` is `choices=("timit", "buckeye")`, and the clean-root and directory-name maps are keyed on those two names |
| `make_noisy.py` | **no** | `DEFAULT_SPLITS` names the seven English splits, and split-to-corpus is a `startswith("timit"/"buckeye")` test |

So `augment.sh` picks up a new corpus automatically and then reports it as
skipped, rather than pretending to have augmented it. The two Python scripts
need per-corpus wiring first, the same way a new corpus needs a processor
under `fabench/dataprep/datasets/<lang>/`.

`datasets/prep/` therefore sits beside `languages/` rather than inside
`languages/en/`. The noise recipe is a benchmark-wide methodological choice
rather than an English one, and a copy per language would invite the second
copy to drift.

## What is NOT here

Absolute paths to your staged corpora, MUSAN or RIRS. Those are machine
settings and live in `.fabench.env` (`FABENCH_*`). Every script below reads
them from the environment, so these files stay portable and licensed paths
never enter the history.
