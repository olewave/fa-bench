# Buckeye data processor

Hand-labelled English **spontaneous** conversational speech. Speaker folders
`sNN/` each hold `.words`, `.phones` and `.wav`. Long interview tracks are
segmented into utterances at silence.

- **Restricted.** Registration-gated (buckeyecorpus.osu.edu). Register and
  download it. fabench never fetches it.
- **Register.** Spontaneous speech.

## Config

```yaml
datasets:
  gold:
    buckeye:
      root: /path/to/Buckeye       # dir of sNN/ speaker folders
      protocol: paper              # fabench | paper
```

- **`protocol`**. `fabench` is fabench's own silence-based segmentation.
  `paper` is the MFA-2026 (arXiv:2606.18466) segmentation used to reproduce
  its Table 5 (about 22,458 utterances). The two are distinct cache variants
  (`buckeye__<protocol>.jsonl`).

The public API is `iter_utterances`, plus `parse_tier`, `segment_track` and
`segment_track_paper` (see `processor.py`).
