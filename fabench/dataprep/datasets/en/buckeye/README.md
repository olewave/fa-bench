# Buckeye data processor

Hand-labelled English **spontaneous** conversational speech. Speaker folders
`sNN/` each hold `.words` / `.phones` / `.wav`. Long interview tracks are
segmented into utterances at silence.

- **Restricted:** registration-gated (buckeyecorpus.osu.edu). Register and
  download — never fetched by fabench.
- **Register:** spontaneous.

## Config

```yaml
datasets:
  gold:
    buckeye:
      root: /path/to/Buckeye       # dir of sNN/ speaker folders
      protocol: paper              # fabench | paper
```

- **`protocol`** — `fabench` = fabench's own silence-based segmentation;
  `paper` = the MFA-2026 (arXiv:2606.18466) segmentation used to reproduce its
  Table 5 (~22,458 utts). The two are distinct cache variants
  (`buckeye__<protocol>.jsonl`).

Public API: `iter_utterances`, plus `parse_tier`, `segment_track`,
`segment_track_paper` (see `processor.py`).
