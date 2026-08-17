# stable-ts aligner

[stable-ts](https://github.com/jianfch/stable-ts) wraps OpenAI Whisper and
stabilises its timestamps. It exposes `model.align(audio, text, language=...)`
— audio **plus the reference transcript** — so FA-Bench drives it as a
**track-1 forced aligner**: the worker never calls `transcribe()`, and its
numbers are timing error only, comparable with MFA and olign.

- **Modes:** A (reference transcript). **Granularity:** word only — no phone
  tier, so it is absent from the phone tables by construction, like WhisperX
  and Qwen3. **Confidence:** no.
- **Pinned:** commit `e312072cc024` (2026-08-11); the installer refuses moving
  refs. Whisper model: `base` (set `params.model`).

## Install

```bash
evals/aligners/stable_ts/download_and_install.sh   # own venv, pinned commit
```

The installer pins `numba>=0.60` **ahead of the resolver**: left alone,
`openai-whisper` drags in numba 0.53.1 → llvmlite 0.36, which refuses to build
on Python ≥ 3.10. Same chain that once defeated a parakeet install here.

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
    timeout_s: null        # batch worker: a timeout destroys, not truncates
```

`regroup=False` is passed to `align()` deliberately: stable-ts otherwise merges
and splits segments, and the emitted words stop matching the reference sequence
the scorer pairs against.

## How to read its numbers

Two caveats, both documented from measurement rather than assumed:

1. **It is a subtitle-grade timestamper evaluated at a 20 ms tolerance.** Like
   WhisperX, its own ecosystem works with collars an order of magnitude wider.
   Word MAE lands at 64–91 ms across cells (WhisperX: 46–48), with P ≈ R —
   it emits the right *number* of boundaries and places them loosely.
2. **The first word tends to absorb leading silence.** TIMIT clips carry long
   silent lead-ins and stable-ts often starts the first word at 0.00 (e.g.
   `the` 0.00–0.66 against gold 0.60–0.67). Buckeye clips are cut tight, so
   this fires mainly on TIMIT — which is why, uniquely among evaluated systems,
   its TIMIT numbers are *worse* than its Buckeye ones, and why added noise
   appears to "improve" TIMIT (it perturbs the silence-suppression heuristics).
   Read its TIMIT rows with that in mind.
