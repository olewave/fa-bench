# WhisperX aligner

WhisperX word alignment, a wav2vec2 CTC alignment head
(`WAV2VEC2_ASR_BASE_960H`) driven on the reference transcript. **Word only**,
with no phones, so it appears only in the word-level tables and never in the
phone tables.

- **Modes.** A. **Granularity.** Word. **Confidence.** Yes.

## Install

```bash
evals/aligners/whisperx/download_and_install.sh   # its own venv, pinned
```

It runs in its own venv because installing whisperx into the shared
environment once moved torch and transformers under other tools. See
`evals/README.md`.

## Config

```yaml
- name: whisperx
  adapter: whisperx
  enabled: true
  modes: [A]
  granularity: [word]
  params: { model: WAV2VEC2_ASR_BASE_960H, device: cuda }
```

The same package also runs on track 2 as `whisperx_asr`, where Whisper
large-v3 decodes the words first and this head then times them.
