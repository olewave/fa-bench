# Third-party notices

## Vendored files: `mapping_files/*.yaml`, `LICENSE`

Source: https://github.com/MontrealCorpusTools/mfa-interspeech2026
Commit: `df8e2bfc0c628a45b0de78ed104f862d49c93c1f` (main, fetched 2026-07-08)
License: MIT (Copyright (c) 2026 Michael McAuliffe) — see `LICENSE` in this directory,
copied verbatim from the same commit.

These are the paper's own custom phone-mapping files for `mfa compare_alignments`
(one per aligner-family x corpus), used unmodified so fabench's `mfa_paper` scoring
protocol matches the MFA-2026 paper's (arXiv:2606.18466) Table 5 exactly:

- `arpa_timit_mapping.yaml`, `arpa_buckeye_mapping.yaml` — MFA/ARPABET
- `bournemouth_timit_mapping.yaml`, `bournemouth_buckeye_mapping.yaml` — BFA
- `charsiu_timit_mapping.yaml`, `charsiu_buckeye_mapping.yaml` — Charsiu
- `maps_timit_mapping.yaml`, `maps_buckeye_mapping.yaml` — MAPS

Re-fetch with `refresh_mapping_files.sh` (diff the result before accepting an update —
this is a deliberate manual step, not an automatic sync).

## NOT vendored verbatim: `fabench/score/mfa_paper/manner_categories.py`

This is a from-scratch Python **port** of the logic in that same repo's
`analysis/data_prep.R` (`test_phone_lists`, `reference_phone_lists`, and the
ARPABET-rhotic override) — re-expressed as Python dicts/functions, not a copied file.
Ported under the same MIT license/commit referenced above.
