# Parakeet-TDT (timestamped ASR)

[NVIDIA Parakeet-TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
— a Token-and-Duration Transducer. It predicts token *durations*, so word
timestamps fall out of decoding rather than being estimated afterwards. It is a production-grade ASR rather than a research checkpoint, which makes it
an operationally relevant row.

**This is track 2: it ignores the reference transcript and decodes its own.**
Its rows mix recognition error with timing error — a misrecognised word leaves
the matched path and depresses recall instead of worsening MAE. Read boundary
F1 (label-agnostic) as the primary metric here and MAE as secondary, the
inverse of the aligner tables, and do not rank it head-to-head against MFA,
Olign, or Qwen3-FA.

- **Modes:** A. **Granularity:** word only — absent from the phone tables by
  construction. **Confidence:** no.

## Requirements

```bash
egs/timestamp_asrs/parakeet_tdt/download_and_install.sh   # own venv
```

Versions are pinned to `requirements.observed` — the environment the published
numbers were actually measured in (nemo 2.7.3, torch 2.11.0+cu128). Pin a
3.12-capable numba *before* installing NeMo, or the
`librosa → numba → llvmlite` chain will defeat the install; see
`evals/aligners/stable_ts/download_and_install.sh` for the pattern.

## Config

```yaml
- name: parakeet_tdt
  adapter: parakeet_tdt
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: nvidia/parakeet-tdt-0.6b-v3
```

Runs in its own interpreter (`fabench/timestamp_asrs/subprocess_asr.py`).
Results are emitted only when the batch worker finishes, so set `timeout_s`
well above the expected cell time — a timeout costs the whole cell, not a
partial one.
