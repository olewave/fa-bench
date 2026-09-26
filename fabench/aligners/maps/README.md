# MAPS aligner

Mason-Alberta Phonetic Segmentor, a neural phone segmentor. It is
text-driven and phone-level, and it is one of the MFA-2026 paper's Table 5
baselines.

- **Modes.** A. **Granularity.** Phone. **Confidence.** Yes.

## Install

```bash
evals/aligners/maps/download_and_install.sh   # its own environment, pinned
```

## Config

```yaml
- name: maps
  adapter: maps
  enabled: true
  modes: [A]
  granularity: [phone]
  params: { device: cuda }
```

Phones are ARPABET, so the normalization source is `arpabet`.

Its `timbuck` models were trained on TIMIT and Buckeye. Its TIMIT rows are
held out, since both FA-Bench TIMIT splits come from TIMIT `TEST/`, which it
did not train on. Its Buckeye rows are not, since 7 of the 8 speakers in each
FA-Bench Buckeye split are in its training set. The records flag them.
