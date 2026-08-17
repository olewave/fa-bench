# TIMIT data processor

Hand-corrected English **read** speech — the canonical FA gold. NIST layout
(`TRAIN/`, `TEST/DR<n>/<SPKR>/<sent>.PHN`), 16 kHz. `.PHN`/`.WRD` give
`start_sample end_sample label` (divide by 16000 for seconds); `.TXT` the
sentence.

- **Restricted:** LDC (Catalog LDC93S1). Obtain via LDC licence — never
  downloaded by fabench.
- **Register:** read.

## Config

```yaml
datasets:
  gold:
    timit:
      root: /path/to/timit        # dir containing TRAIN/ and TEST/
      subset: core_test           # core_test (192) | dev (400) | train (3696)
      merge_closures: false       # true => fold stop closures into the burst
```

- **`subset`** — `core_test` = the standard 24-speaker / 192-utt set (default);
  `dev` = 400 utts / 50 spk (Kaldi convention);
  `train` = 3,696 / 462. Every subset excludes the 2 SA sentences, which TIMIT
  states must not be used for training or test.
- **`merge_closures`** — TIMIT annotates each stop as a silent closure + burst;
  Buckeye labels the whole stop as one phone. `true` folds each `{b,d,g,p,t,k}cl`
  into its following burst so closures stop counting as silence — makes TIMIT
  "Buckeye-style" for cross-register comparison. Written to a distinct cache
  variant (`timit__<subset>__mergeclosures.jsonl`).

Public API: `iter_utterances`, `parse_utterance` (see `processor.py`).
