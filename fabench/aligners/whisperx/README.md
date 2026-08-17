# WhisperX aligner

WhisperX word alignment. **Word-only** (no phones) — so it appears only in the
word-level tables, never in phone tables.

- **Modes:** A. **Granularity:** word. **Confidence:** yes.

## Requirements

```bash
pip install whisperx
```

## Config

```yaml
- name: whisperx
  adapter: whisperx
  enabled: true
  modes: [A]
  granularity: [word]
  params: { model: WAV2VEC2_ASR_BASE_960H, device: cuda }
```
