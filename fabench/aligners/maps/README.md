# MAPS aligner

Mason-Alberta Phonetic Segmentor — a neural phone segmentor. Text-driven,
phone-level. One of the MFA-2026 paper's Table-5 baselines.

- **Modes:** A. **Granularity:** phone. **Confidence:** yes.

## Config

```yaml
- name: maps
  adapter: maps
  enabled: true
  modes: [A]
  granularity: [phone]
  params: { device: cuda }
```

Phones are ARPABET → `arpabet` normalization source.
