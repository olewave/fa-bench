# nyra forced aligner

A forced aligner from nyra labs. It puts WavLM-large features under a triphone
GMM-HMM and adds units for fillers and vocal events.

- **Modes.** A, from text. **Granularity.** Word.
- **Confidence.** One per word.
- **Batch.** Yes. The model loads once per cell.

## Licence

The `nyra-forced-aligner` package is MIT. The model
[`nyralabs/nyra_forced_aligner_en`](https://huggingface.co/nyralabs/nyra_forced_aligner_en)
is under the nyra health Non-Commercial Research License. Read that licence
before you run the recipe for anything but research.

## Requirements

`evals/aligners/nyra_fa/download_and_install.sh` builds the tool's own
environment under `venv` and fetches the model. The package needs `espeak-ng`
for words outside its lexicon, so install that first.

## Config

```yaml
- name: nyra_fa
  adapter: nyra_fa
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: nyralabs/nyra_forced_aligner_en
    device: cuda
```

## What the worker does

The model card asks for fillers as bracketed tags in upper case. The worker
sends "um" and "uh" as `[UM]` and `[UH]` and leaves every other word as it is.
The aligner returns one entry per token, and the worker hands the times back
under the reference labels so the scorer can pair them.

The package also returns phones, in a set of 39 that FA-Bench has no mapping
for yet. The phone tier is therefore not scored.
