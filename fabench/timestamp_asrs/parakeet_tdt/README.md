# Parakeet-TDT (timestamped ASR)

[NVIDIA Parakeet-TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
a Token-and-Duration Transducer. It predicts token *durations*, so word
timestamps fall out of decoding rather than being estimated afterwards. It is
a production-grade ASR rather than a research checkpoint, which makes it an
operationally relevant row.

**This is track 2. It ignores the reference transcript and decodes its own.**
Its rows mix recognition error with timing error. A misrecognised word leaves
the matched path, so it costs the boundaries beside it in the label-checked
F1 while leaving MAE untouched. Read that F1 as the primary metric here and
MAE as secondary, and do not rank it head-to-head against MFA, Olign or
Qwen3-FA.

- **Modes.** A. **Granularity.** Word only, so it is absent from the phone
  tables by construction. **Confidence.** None.

## Requirements

```bash
evals/timestamp_asrs/parakeet_tdt/download_and_install.sh   # own venv
```

Versions are pinned to `requirements.observed`, the environment the
published numbers were measured in (nemo 2.7.3, torch 2.11.0+cu128). Pin a
3.12-capable numba *before* installing NeMo, or the
`librosa → numba → llvmlite` chain will defeat the install. See
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
well above the expected cell time. A timeout costs the whole cell rather than
a partial one.
