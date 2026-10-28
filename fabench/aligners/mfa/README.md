# MFA aligner

Montreal Forced Aligner, Kaldi GMM-HMM with speaker adaptation (SAT, fMLLR
and LDA). The standard high-accuracy baseline.

- **Modes.** A (from text) and B (from gold phones). **Granularity.** Word
  and phone.
- **Confidence.** None per boundary. The acoustic log-likelihood ranks
  utterances only.
- **Batch.** Yes. One model load is amortized over the corpus.

## Requirements

MFA installed in a conda or micromamba env with an English dictionary and
acoustic model (`english_us_arpa`). FA-Bench shells into that env.
`evals/aligners/mfa/download_and_install.sh` builds one under `repo/mamba`,
and the adapter finds the micromamba it installs there.

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

Phones are ARPABET, and the normalization source is `mfa`.

Because MFA adapts to each speaker, its output for one utterance depends on
the other utterances of that speaker in the same run. Re-running a few
utterances of a cell does not reproduce the published output exactly. Re-run
whole speakers instead.
