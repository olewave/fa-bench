# BFA aligner

Bournemouth Forced Aligner, a neural aligner (CUPE + CTC). It is text-driven,
through espeak G2P to IPA phones, and it is one of the MFA-2026 paper's Table
5 baselines.

- **Modes.** A. **Granularity.** Word and phone. **Confidence.** Yes.

## Install

```bash
evals/aligners/bfa/download_and_install.sh   # its own environment, pinned
```

## Config

```yaml
- name: bfa
  adapter: bfa
  enabled: true
  modes: [A]
  granularity: [word, phone]
  params: { preset: en-us, device: cuda }
```

Phones are IPA, so the normalization source is `ipa`.

Note that under `scoring.protocol: mfa_paper`, BFA is scored **onset-only**,
because its inter-phone gaps are a CTC artifact. See
`fabench/score/mfa_paper/`.
