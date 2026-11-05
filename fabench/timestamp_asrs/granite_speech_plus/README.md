# Granite Speech 4.1 2B-plus (timestamped ASR)

[IBM Granite Speech 4.1 2B-plus](https://huggingface.co/ibm-granite/granite-speech-4.1-2b-plus),
a speech LLM built on `granite-4.0-1b-base`, Apache 2.0. Given the model
card's timestamp prompt it writes an end-time tag after every word,
`hello [T:45] world [T:82]`, in centiseconds, and a `_` with its own tag for
each silence.

**This is track 2. It ignores the reference transcript and decodes its own.**
Its rows mix recognition error with timing error. Read the label-checked F1 as
the primary metric here and MAE as secondary, and do not rank it head-to-head
against MFA, Olign or Qwen3-FA.

- **Modes.** A. **Granularity.** Word only. **Confidence.** None.
- **Start times.** The model gives none. A word starts where the token before
  it ended, word or `_`, and the first starts at 0. A pause it does not mark
  is counted inside the next word, so its onsets read early.
- **Rollover.** A tag holds only the last three digits, so it wraps every
  10 s. The worker unwraps it as the card does, assuming no gap of 10 s or
  more between tags.
- **Output.** Lower case, no punctuation (the `plus` model drops both).
- **Grid.** Measured at 10 ms, the centisecond tag itself.
- **Training overlap.** None. Its timestamp training includes TIMIT `TRAIN/`
  only, and no Buckeye; both our TIMIT splits are carved from `TEST/`.

## Requirements

```bash
evals/timestamp_asrs/granite_speech_plus/download_and_install.sh   # own venv
```

It needs `transformers>=5.8`, newer than any other tool here, and is pinned
to torch 2.11.0+cu128. `requirements.observed` records what was installed.

## Config

```yaml
- name: granite_speech_plus
  adapter: granite_speech_plus
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: ibm-granite/granite-speech-4.1-2b-plus
    num_beams: 4        # what IBM's reported numbers used; 1 is faster
```

Decoding follows the card: `repetition_penalty=2.0`, and an output cap of
48 tokens per second of audio, at least 256. Items run one at a time.
