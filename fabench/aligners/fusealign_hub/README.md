# FuseAlign (fusealign_hub)

FuseAlign as Zyphra packages it in
[`fusealign-multilingual`](https://github.com/Zyphra/fusealign-multilingual):
the multilingual noisy student, step 60,000. It is not a CTC
model. A joint audio/text transformer reads the waveform and the UTF-8 bytes of
the transcript and predicts, per word, a start and an end on a 1 ms grid plus a
presence probability.

- **Modes.** A, from text. **Granularity.** Word.
- **Confidence.** One per word, the presence probability.
- **Batch.** Yes. The model loads once per cell, and clips share batched forwards.

## Licence

The `fusealign-multilingual` package is Apache-2.0. The checkpoint
[`Zyphra/fusealign`](https://huggingface.co/Zyphra/fusealign) is Apache-2.0,
including the frozen text encoder of Dia it carries. The model card describes
the training data, about 25,000 h in 73 languages. None of it, nor the data of
the checkpoints it was trained from, is TIMIT or Buckeye audio; TIMIT's prompt
sentences appear only as read by other speakers in a TTS corpus.

## Requirements

`evals/aligners/fusealign_hub/download_and_install.sh` builds the tool's own
environment under `venv`, from the package at a pinned commit with the
package's own dependency pins, and fetches the checkpoint at a pinned revision
into the Hugging Face cache. The worker then runs offline.

## Config

```yaml
- name: fusealign_hub
  adapter: fusealign_hub
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: Zyphra/fusealign
    revision: a4d58de4f0c6aff1e00f36e27bc58c901a39c359
    checkpoint: fusealign-multilingual-ns4-step60000.safetensors
    device: cuda
    batch_size: 64
    unplaced: fallback
```

## What the worker does

The worker calls the package's `align_batch` with the reference transcript as
given. The package returns one entry per whitespace token, and the worker
writes them back in order, with the presence probability as each word's
confidence.

A word the model does not place, with presence under 0.1, keeps the package's
uniform fallback interval under `unplaced: fallback`, the shipped behaviour.
`unplaced: drop`, the recipe in `exps/drop/`, leaves it out instead. Either way
the hyp record counts them in `n_unplaced`.

Clips over 30 s or transcripts over 1,022 bytes would take the package's
long-form path, which runs Whisper. No clip in the scored cells reaches either
limit.
