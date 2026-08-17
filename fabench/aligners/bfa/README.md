# BFA aligner

Bournemouth Forced Aligner — neural (CUPE + CTC). Text-driven via espeak G2P →
IPA phones. One of the MFA-2026 paper's Table-5 baselines.

- **Modes:** A. **Granularity:** word + phone. **Confidence:** yes.

## Config

```yaml
- name: bfa
  adapter: bfa
  enabled: true
  modes: [A]
  granularity: [word, phone]
  params: { preset: en-us, device: cuda }
```

Note: under `scoring.protocol: mfa_paper`, BFA is scored **onset-only** (its
inter-phone gaps are a CTC artifact) — see `fabench/score/mfa_paper/`.
