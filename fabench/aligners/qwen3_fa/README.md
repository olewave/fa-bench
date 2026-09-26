# Qwen3-FA aligner

[Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)
is an LLM-based forced aligner. Audio plus the reference transcript go in, and
word times come out. Do not confuse it with Qwen3-ASR, which is a different
model that decodes its own transcript. This one is given the words, so it
belongs in track 1 beside MFA and Olign rather than with the timestamped ASRs.

- **Modes.** A (text-driven). **Granularity.** Word only. It has no phone
  tier, so it is absent from the phone tables by construction, as WhisperX
  is. **Confidence.** None.

## Requirements

```bash
evals/aligners/qwen3_fa/download_and_install.sh    # own venv, qwen-asr==0.0.6
```

A private venv is required rather than preferred. `qwen_asr` needs
transformers 4.57.6 against the shared `.venv`'s 5.14.1, and mixing the two
fails on a native extension (`cffi` vs `_cffi_backend`) that no `sys.path`
ordering resolves. The adapter therefore runs it in its own interpreter
through `worker.py`, batched so the model loads once per cell.

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
    timeout_s: 21600     # a Buckeye cell is about 2.4 h, and a short timeout loses it all
```

## Caveats

- **Zero-duration words are passed through unchanged.** The model reports
  times on an 80 ms grid, so a word shorter than one step comes back with
  `end_time == start_time`. That is 3.0% of its words on clean TIMIT test,
  5.9% on clean Buckeye test and 10.8% under noise. It is the model's actual
  output, and inventing a duration would fabricate a boundary it never
  produced. The per-utterance count is recorded in `meta`.
- **Coarse by design.** The 80 ms grid, 8× coarser than MFA's or Olign's
  10 ms, is the dominant term in its word-boundary error rather than an
  edge-placement defect. Only half of the reference boundaries fall within
  20 ms of such a step, so its F1 at 20 ms is capped near 0.5 before
  anything else is measured.
- Results are only emitted when the batch worker finishes, so a timeout kills
  the whole cell rather than truncating it. Hence the large `timeout_s`.
