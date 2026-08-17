# CrisperWhisper (timestamped ASR)

Whisper variant tuned for verbatim, well-placed word timestamps
([Interspeech 2024, arXiv:2408.16589](https://arxiv.org/abs/2408.16589);
[github.com/nyrahealth/CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper)).

**This is track 2: it ignores the reference transcript and decodes its own.**
Its rows therefore mix recognition error with timing error — a misrecognised
word leaves the matched path and depresses recall instead of worsening MAE. Read
boundary F1 (label-agnostic) as the primary metric here and MAE as secondary,
the inverse of the aligner tables, and do not rank it head-to-head against MFA,
olign, or Qwen3-FA.

The same model also runs in **track 1** as
[`crisperwhisper_fa`](../../aligners/crisperwhisper_fa/README.md), driven
through its native `forced_align()` on the reference. The pair isolates exactly
what the recognition step costs.

- **Modes:** A. **Granularity:** word only. **Confidence:** no.

## Requirements

```bash
egs/timestamp_asrs/crisperwhisper/download_and_install.sh   # own venv
```

`transformers` is version-pinned there: CrisperWhisper's timestamps come out of
the model's attention, so the library release is part of the measurement rather
than an implementation detail.

## Config

```yaml
- name: crisperwhisper
  adapter: crisperwhisper
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: nyrahealth/CrisperWhisper
```

Runs in its own interpreter (`fabench/timestamp_asrs/subprocess_asr.py`). Give
it a generous `timeout_s`: measured ~5.9 s/item, and results are only emitted
when the worker finishes, so a short timeout loses the whole cell.
