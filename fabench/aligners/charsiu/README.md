# Charsiu aligner

A wav2vec2 frame-classifier forced aligner (`charsiu/en_w2v2_fc_10ms`) on a
10 ms grid. It is one of the MFA-2026 paper's Table 5 baselines.

- **Modes.** A and B. **Granularity.** Word and phone. **Confidence.** Yes
  (frame posteriors).

## Install

```bash
evals/aligners/charsiu/download_and_install.sh   # its own environment, pinned commit
```

## Config

```yaml
- name: charsiu
  adapter: charsiu
  enabled: true
  modes: [A, B]
  granularity: [word, phone]
  params: { model: charsiu/en_w2v2_fc_10ms, device: cuda }
```

Phones are ARPABET, so the normalization source is `arpabet`.

Charsiu emits `[sil]` tokens in its word tier. The scorer drops silence
pseudo-words on both sides before matching words, so they never count as
insertions.
