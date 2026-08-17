# Charsiu aligner

Wav2Vec2 frame-classifier forced aligner (`charsiu/en_w2v2_fc_10ms`), 10 ms grid,
phone-level. One of the MFA-2026 paper's Table-5 baselines.

- **Modes:** A + B. **Granularity:** phone. **Confidence:** yes (frame posteriors).

## Requirements

```bash
pip install git+https://github.com/lingjzhu/charsiu
```

## Config

```yaml
- name: charsiu
  adapter: charsiu
  enabled: true
  modes: [A, B]
  granularity: [phone]
  params: { model: charsiu/en_w2v2_fc_10ms, device: cuda }
```

Phones are IPA → `charsiu`/`ipa` normalization source.
