# torchaudio forced aligner

CTC forced alignment through torchaudio's alignment API, with a wav2vec2
bundle (for example `WAV2VEC2_ASR_BASE_960H`).

- **Modes.** A and B. **Granularity.** Word and phone. **Confidence.** Yes
  (CTC frame posteriors).

## Requirements

```bash
evals/aligners/torchaudio_fa/download_and_install.sh
```

Its own venv rather than FA-Bench's. It was the last tool importing torch
in-process, which made the shared environment carry a CUDA build for one
consumer and left this tool's numbers set by whatever that environment
resolved to. The recipe pins torch and torchaudio 2.8.0+cu128 and transformers
5.14.1, which is what produced the published rows. `phonemizer` needs the
espeak-ng system library (`apt install espeak-ng`).

## Config

```yaml
- name: torchaudio_fa
  adapter: torchaudio_fa
  enabled: true
  modes: [A, B]
  granularity: [word, phone]
  params: { model: WAV2VEC2_ASR_BASE_960H, device: cuda }
```

Mode A aligns the words. Mode B aligns a phone sequence the worker derives
from the transcript with eSpeak G2P, through `params.phoneme_model`
(`facebook/wav2vec2-lv-60-espeak-cv-ft`). Both run into one `hyp.jsonl`, so
each leaderboard carries two rows for it. The word tables read mode A and the
phone tables read mode B.
