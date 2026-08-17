# torchaudio forced aligner

CTC forced alignment via torchaudio's alignment API (a wav2vec2 bundle, e.g.
`WAV2VEC2_ASR_BASE_960H`). The default always-available aligner.

- **Modes:** A + B. **Granularity:** word + phone. **Confidence:** yes (CTC frame
  posteriors).

## Requirements

```bash
evals/aligners/torchaudio_fa/download_and_install.sh
```

Its own venv, not FA-Bench's. It was the last tool importing torch in-process,
which made the shared environment carry a CUDA build for one consumer and left
this tool's numbers set by whatever that environment resolved to. The recipe
pins torch/torchaudio 2.8.0+cu128 and transformers 5.14.1 -- what produced the
published rows. `phonemizer` needs the espeak-ng system library
(`apt install espeak-ng`).

## Config

```yaml
- name: torchaudio_fa
  adapter: torchaudio_fa
  enabled: true
  modes: [A, B]
  granularity: [word, phone]
  params: { model: WAV2VEC2_ASR_BASE_960H, device: cuda }
```
