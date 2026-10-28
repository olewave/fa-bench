# TIMIT data processor

Hand-corrected English **read** speech, the canonical forced-alignment gold.
NIST layout (`TRAIN/`, `TEST/DR<n>/<SPKR>/<sent>.PHN`), 16 kHz. `.PHN` and
`.WRD` give `start_sample end_sample label` (divide by 16000 for seconds),
and `.TXT` gives the sentence.

- **Restricted.** LDC (Catalog LDC93S1). Obtain it under an LDC licence.
  fabench never downloads it.
- **Register.** Read speech.

## Config

```yaml
datasets:
  gold:
    timit:
      root: /path/to/timit        # dir containing TRAIN/ and TEST/
      subset: core_test           # core_test (192) | dev (400) | train (3696)
      merge_closures: false       # true folds stop closures into the burst
```

- **`subset`**. `core_test` is the standard 24-speaker, 192-utterance set and
  the default. `dev` is 400 utterances from 50 speakers, a Kaldi convention.
  `train` is 3,696 utterances from 462 speakers. Every subset excludes the 2
  SA sentences, which TIMIT states must not be used for training or test.
- **`merge_closures`**. TIMIT annotates each stop as a silent closure plus a
  burst, whereas Buckeye labels the whole stop as one phone. `true` folds each
  `{b,d,g,p,t,k}cl` into its following burst so closures stop counting as
  silence, which makes TIMIT "Buckeye-style" for cross-register comparison.
  It is written to a distinct cache variant
  (`timit__<subset>__mergeclosures.jsonl`).

The public API is `iter_utterances` and `parse_utterance` (see
`processor.py`).
