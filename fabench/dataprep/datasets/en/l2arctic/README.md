# L2-ARCTIC data processor

Non-native (**L2**) accented English, with manual phone boundaries for a
subset. The layout is `<speaker>/annotation/*.TextGrid` for the
hand-corrected gold and `<speaker>/wav/*.wav` for the audio.

- **License.** Open for research (psi.engr.tamu.edu/l2-arctic). Download it
  and set the root. fabench never fetches it.
- **Register.** Read speech, L2.

## Config

```yaml
datasets:
  gold:
    l2arctic:
      root: /path/to/l2arctic      # corpus root (<speaker>/annotation/*.TextGrid)
      subset: manual               # manual = speakers with hand-corrected TextGrids
```

The public API is `iter_utterances` (see `processor.py`). TextGrid parsing
uses `praatio`.
