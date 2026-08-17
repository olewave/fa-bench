# L2-ARCTIC data processor

Non-native (**L2**) accented English, with manual phone boundaries for a subset.
Layout: `<speaker>/annotation/*.TextGrid` holds the hand-corrected gold;
`<speaker>/wav/*.wav` the audio.

- **License:** open for research (psi.engr.tamu.edu/l2-arctic). Download and set
  the root — fabench never fetches it.
- **Register:** read (L2).

## Config

```yaml
datasets:
  gold:
    l2arctic:
      root: /path/to/l2arctic      # corpus root (<speaker>/annotation/*.TextGrid)
      subset: manual               # manual = speakers with hand-corrected TextGrids
```

Public API: `iter_utterances` (see `processor.py`). TextGrid parsing uses
`praatio`.
