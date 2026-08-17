# MFA aligner

Montreal Forced Aligner — Kaldi GMM-HMM with speaker adaptation (SAT + fMLLR +
LDA). The standard high-accuracy baseline.

- **Modes:** A (from text) + B (from gold phones). **Granularity:** word + phone.
- **Confidence:** none per-boundary (acoustic log-likelihood ranks utterances only).
- **Batch:** yes — one model load amortized over the corpus.

## Requirements

MFA installed in a conda/micromamba env with an English dictionary + acoustic
model (`english_us_arpa`). FA-Bench shells into that env.

## Config

```yaml
- name: mfa
  adapter: mfa
  enabled: true
  modes: [A, B]
  granularity: [word, phone]
  params:
    version: "3.4"                 # selects the conda env
    dictionary: english_us_arpa
    acoustic_model: english_us_arpa
    # align_args: ["--single_speaker"]   # extra flags injected before positionals
```

Phones are ARPABET → `mfa`/`arpabet` normalization source.
