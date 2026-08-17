# Qwen3-FA aligner

[Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)
— an LLM-based forced aligner: audio plus the reference transcript in, word
times out. **Not** Qwen3-ASR, a different model that decodes its own
transcript; this one is given the words, so it belongs in track 1 beside MFA
and Olign rather than with the timestamped ASRs.

- **Modes:** A (text-driven). **Granularity:** word only — no phone tier, so
  it is absent from the phone tables by construction, exactly like WhisperX.
  **Confidence:** no.

## Requirements

```bash
egs/aligners/qwen3_fa/download_and_install.sh    # own venv, qwen-asr==0.0.6
```

A private venv is required, not a preference: `qwen_asr` needs
transformers 4.57.6 against the shared `.venv`'s 5.14.1, and mixing the two
fails on a native extension (`cffi` vs `_cffi_backend`) that no `sys.path`
ordering resolves. The adapter therefore runs it in its own interpreter via
`worker.py`, batched so the model loads once per cell.

## Config

```yaml
- name: qwen3_fa
  adapter: qwen3_fa
  enabled: true
  modes: [A]
  granularity: [word]
  params:
    venv: venv
    model: Qwen/Qwen3-ForcedAligner-0.6B
    language: English
    timeout_s: 21600     # a Buckeye cell is ~2.4 h; a short timeout loses it all
```

## Caveats

- **Zero-duration items are passed through unchanged.** On a measured TIMIT
  sample, 7.2% of items came back with `end_time == start_time`. That is the
  model's actual output; inventing a duration would fabricate a boundary it
  never produced. The per-utterance count is recorded in `meta`.
- **Coarse by design.** It emits on a 40 ms grid — 4× coarser than MFA's or
  Olign's 10 ms — which is the dominant term in its word-boundary error, not
  an edge-placement defect.
- Results are only emitted when the batch worker finishes, so a timeout kills
  the whole cell rather than truncating it. Hence the large `timeout_s`.
