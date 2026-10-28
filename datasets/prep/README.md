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

`fabench prepare` runs steps 1 to 3 in one command, from your staged corpora
into one new directory.

```
fabench prepare --corpus timit --subset core_test --out /data/fabench/noisy-timit
```

## What step 2 needs

Step 2 needs five things, and `fabench prepare` checks each one before it
starts.

1. **The staged corpora**, at `FABENCH_TIMIT_ROOT` and `FABENCH_BUCKEYE_ROOT`.
   `make_noisy.py` reads Kaldi data directories, and
   `fabench/dataprep/noisemix/datadirs.py` writes them from these roots and
   the split lists. Each `wav.scp` line pipes a source file through
   `ffmpeg -hide_banner -loglevel error -i <src> -ar 16000 -ac 1 -af "adelay=475,apad=pad_dur=0.475" -f wav - |`.
   There is one line per TIMIT utterance (`dr1_felc0_si1386`) and one per
   Buckeye recording (`s0701a`). The noise is drawn in the order of these
   lines, so that order is part of the seed. From the same corpus files, all
   six default splits come out byte for byte as the published build had them.
   Only the Buckeye audio paths in `wav.scp` differ, because that build read
   a flat copy of the same recordings.
2. **`wav-reverberate` and `wav-to-duration`**, two Kaldi binaries. The first
   does the mixing and the second measures MUSAN. Build both with
   `git submodule update --init tools/kaldi && tools/build_wav_reverberate.sh`,
   then pass `--wav-reverberate` or set `FABENCH_WAV_REVERBERATE`. Kaldi's
   `utils/` comes from the same Kaldi tree.
3. **sox and ffmpeg** on `PATH`.
4. **MUSAN** ([OpenSLR 17](https://www.openslr.org/17/)) at `--musan` or
   `$MUSAN`, and **RIRS_NOISES** ([OpenSLR 28](https://www.openslr.org/28/))
   at `--rirs` or `$RIRS`.
5. **An empty output directory.** A directory that holds anything is refused,
   so a stale file is never reused.

Each corpus takes the subsets it has, so one command builds every published
condition.

```
fabench prepare --corpus timit,buckeye --subset train,dev,core_test,test \
    --out /data/fabench/noisy --jobs 16
FABENCH_SHADOW=/data/fabench/noisy/shadow evals/gen_noisy_configs.py --tools ALL --subsets ALL
```

The output of step 2 is padded by 475 ms at both ends, on purpose, and step 3
cuts every file back to the samples and length of its clean source.

## The manifest

`<out>/manifest.json` holds the sha256 of every audio file the build wrote.
It also holds the sha256 of every input that can change those bytes, from the
corpus audio and the noise corpora to each binary and every library it loads.
The draws are seeded, so two builds from the same inputs write the same
manifest.

```
cmp first/manifest.json second/manifest.json
```

## How close a rebuild comes to the published audio

The draws come out exact. A rebuild writes every `wav.scp` line for line as
the published build did, so each file gets the same noise at the same SNR. The
samples can still move by a few units in the last place, because
`wav-reverberate` scales the speech and the noise by powers it sums in single
precision through BLAS, and each BLAS sums in its own order. The binary that
built the published audio was not kept. A rebuild with each BLAS at hand
measured these differences against the published files.

| Build | BLAS | Corpus | Files identical | Samples that differ | Largest difference | Difference energy |
|---|---|---|---|---|---|---|
| `tools/kaldi` | OpenBLAS 0.3.20 | TIMIT core_test | 1 to 10 of 192 | 0.025% to 0.033% | 1 LSB | 88 to 90 dB below the signal |
| `tools/kaldi` | MKL 2020.0 | TIMIT core_test | 1 to 3 of 192 | 0.047% to 0.41% | 1 LSB | 77 to 87 dB below the signal |
| `tools/kaldi` | OpenBLAS 0.3.20 | TIMIT dev | 2 to 13 of 400 | 0.025% to 0.035% | 1 LSB | 87 to 89 dB below the signal |
| `tools/kaldi` | OpenBLAS 0.3.20 | Buckeye dev | 0 of 50 | 1.9% to 2.4% | 10 LSB | 75 to 77 dB below the signal |
| `tools/kaldi` | MKL 2020.0 | Buckeye dev | 0 of 50 | 4.9% to 6.4% | 19 LSB | 71 to 72 dB below the signal |

The ranges run over the four conditions. A Buckeye recording runs about ten
minutes, so its sums are longer and drift further. Two conda-forge Kaldi
builds on OpenBLAS 0.3.34 matched the OpenBLAS row byte for byte, and a
second MKL build matched the MKL row, so the BLAS is what moves the samples.
Forcing other OpenBLAS kernels or versions moved them again.

Check which BLAS your binary loads before you compare two builds. The
OpenBLAS row above ran on the distribution's library, which the loader found
ahead of the one `tools/build_wav_reverberate.sh` builds. The manifest records
the sha256 of every library each binary loads, so it tells two such builds
apart.

```
ldd tools/kaldi/src/featbin/wav-reverberate | grep -i -e blas -e mkl
```

The published shadow files carry the ffmpeg version in their WAV header
(`Lavf...`), so compare their samples with a build of your own. From release
2.0 the shadow step writes no such tag, so two builds compare byte for byte.
Cut from identical noisy files, they match sample for sample.

### The published audio, by its hashes

[`reference_audio_202610.sha256`](reference_audio_202610.sha256) holds the
sha256 of every degraded file behind the published cells, 2,764 in all. They
are the four conditions of TIMIT dev and core_test, and of the 99 Buckeye
recordings in dev and test, as the noise recipe wrote them before the shadow
step. Compare a build of your own with them.

```
python datasets/prep/compare_reference.py <out>/manifest.json
```

It counts, per corpus, subset and condition, the files that are byte-identical
to the published ones. A file that matches came from the same samples. A file
that differs should differ within the table above. Release 2.1 pins one build
of `wav-reverberate`, so that a rebuild can match every file.

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

Three details decide what an SNR in this table means.

- `wav-reverberate` measures the SNR against the mean power of the whole
  padded input, its silences included. A TIMIT file carries 475 ms of digital
  silence at each end, and a Buckeye recording carries every pause of a
  conversation, so the speech itself sits above the noise by more than the
  drawn figure.
- In `babble` each talker gets its own SNR, so three to seven talkers summed
  sit several dB louder than any one drawn figure.
- MUSAN has 660 music tracks. Fifteen of them have no line in its annotation
  file, and the recipe leaves those out, so `music` draws from 645 tracks.

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

Every split starts from the same seed, so the k-th line of every split draws
the same noise file and the same SNR. TIMIT core_test and the first 192
utterances of TIMIT dev share all of their `reverb`, `music` and `babble`
draws, and the Buckeye dev and test recordings pair up the same way. `noise`
shares fewer, because its draws also depend on the length of every earlier
file. Dev and test are therefore two looks at one draw sequence. Release 2.1
gives each split its own seed, which changes the degraded audio and so comes
with a new snapshot.

## Is this language-agnostic?

**The recipe is. The code underneath is not yet.** Worth knowing before you
add a second language under `datasets/languages/`.

| Layer | Agnostic? | Why |
|---|---|---|
| `ingest.sh` | **yes** | passes corpus names to `fabench ingest`, which resolves everything through `datasets/languages/<lang>/` |
| `augment.sh` | **yes** | the corpus list is read from the tree rather than hardcoded, and the four Kaldi conditions are additive noise and RIRs, which do not care what is being said |
| `shadow_root.py` | **no** | `--corpus` is `choices=("timit", "buckeye")`, and the clean-root and directory-name maps are keyed on those two names |
| `make_noisy.py` | **no** | `DEFAULT_SPLITS` names the six English splits, and split-to-corpus is a `startswith("timit"/"buckeye")` test |
| `datadirs.py` | **no** | one writer per corpus, `timit()` and `buckeye()`, each with that corpus's layout and segmentation |

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
