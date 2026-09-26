# stable-ts aligner

[stable-ts](https://github.com/jianfch/stable-ts) wraps OpenAI Whisper and
stabilises its timestamps. It exposes `model.align(audio, text, language=...)`,
which takes the audio **plus the reference transcript**, so FA-Bench drives
it as a **track-1 forced aligner**. The worker never calls `transcribe()`,
and its numbers are timing error only, comparable with MFA and Olign.

- **Modes.** A (reference transcript). **Granularity.** Word only. It has no
  phone tier, so it is absent from the phone tables by construction, as
  WhisperX and Qwen3-FA are. **Confidence.** None.
- **Pinned.** Commit `e312072cc024` (2026-08-11). The installer refuses
  moving refs. The Whisper model is `base` (set `params.model`).

## Install

```bash
evals/aligners/stable_ts/download_and_install.sh   # own venv, pinned commit
```

The installer pins `numba>=0.60` **ahead of the resolver**. Left alone,
`openai-whisper` drags in numba 0.53.1 and llvmlite 0.36, which refuses to
build on Python 3.10 or later. The same chain once defeated a parakeet
install here.

## Config

```yaml
- name: stable_ts
  adapter: stable_ts
  enabled: true
  modes: [A]
  granularity: [word]
  emits_confidence: false
  params:
    venv: evals/aligners/stable_ts/venv
    worker: evals/aligners/stable_ts/worker.py
    model: base
    timeout_s: null        # batch worker, so a timeout destroys the run
```

`regroup=False` is passed to `align()` deliberately. stable-ts otherwise
merges and splits segments, and the emitted words stop matching the reference
sequence the scorer pairs against.

## How to read its numbers

Two caveats, both documented from measurement rather than assumed.

1. **It is a subtitle-grade timestamper evaluated at a 20 ms tolerance.** As
   with WhisperX, its own ecosystem works with collars an order of magnitude
   wider. On clean audio its word MAE is 97 ms on TIMIT core test and 71 ms
   on Buckeye test, against 37 and 42 ms for WhisperX, with precision about
   equal to recall. It emits the right *number* of boundaries and places them
   loosely.
2. **The first word tends to absorb leading silence.** TIMIT clips carry long
   silent lead-ins and stable-ts often starts the first word at 0.00 (for
   example `the` 0.00 to 0.66 against gold 0.60 to 0.67). Buckeye clips are
   cut tight, so this fires mainly on TIMIT. That is why its TIMIT numbers
   are *worse* than its Buckeye ones, and why three of the four degradations
   appear to "improve" TIMIT. They perturb the silence-suppression
   heuristics. Read its TIMIT rows with that in mind.
