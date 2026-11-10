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
    # beam: 400                    # MFA defaults to 10
    # retry_beam: 4000             # MFA defaults to 40
    # align_args: ["--single_speaker"]   # extra flags injected before positionals
```

## Models and beams

MFA ships two English models. The leaderboard row runs `english_us_arpa` at
MFA's default beam, which is the stronger of the two on TIMIT and Buckeye.
Three variant recipes under `evals/aligners/mfa/exps/` let you measure the
other settings yourself.

| Recipe | Model | Beam | Tiers |
|---|---|---|---|
| `mfa` | `english_us_arpa` | default, 10 and 40 | word and phone |
| `mfa_arpa_wide` | `english_us_arpa` | 400 and 4000 | word and phone |
| `mfa_english_mfa` | `english_mfa` | default | word |
| `mfa_english_mfa_wide` | `english_mfa` | 400 and 4000 | word |

Run one with `./run_evals.sh --use-noisy-dataset true mfa_arpa_wide`.

`english_mfa` uses MFA's own phone set, so its recipes score the word tier
only. A wide beam matters on long recordings, where the default beam can lose
the best path. On FA-Bench's short utterances it changes little. With
`english_mfa` the default beam drops some noisy utterances and the wide beam
keeps them.

MFA keeps its working files in one folder per user. Two MFA runs at the same
time corrupt each other there, so run one recipe at a time, or give each its
own `mfa_root`.

Phones are ARPABET, and the normalization source is `mfa`.

Because MFA adapts to each speaker, its output for one utterance depends on
the other utterances of that speaker in the same run. Re-running a few
utterances of a cell does not reproduce the published output exactly. Re-run
whole speakers instead.
