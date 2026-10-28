# datasets, the canonical dataset config and split definitions

One folder per corpus, grouped by language, with a language-level config
beside them.

```
datasets/languages/en/
  config.yaml          which corpora the benchmark evaluates, on which subset
  <corpus>/
    config.yaml        that corpus's own config (root, default subset, options)
    split/<name>.list  membership, one "<speaker_id> <utterance_id>" per line
    speakers.tsv       corpus speaker table, where the stratification needs it
datasets/prep/         how a staged copy became this data, with the commands
                       and their parameters (ingest, noise augmentation, shadow roots)
```

This folder says what the data **is**. [`prep/`](prep/README.md) says how it
was **produced**, meaning the invocations. The scripts themselves live in
`fabench/dataprep/`.

## How the config composes

`load_config()` builds `datasets.gold` from three layers, lowest first,
merging per key.

1. **`<lang>/<corpus>/config.yaml`** holds everything intrinsic to the corpus.
   That is a null `root`, the corpus's default `subset`, and options such as
   `protocol` (Buckeye) or `merge_closures` (TIMIT), each with its rationale.
2. **`<lang>/config.yaml`** holds the benchmark's default selection, which
   corpora are enabled and at which subset.
3. **The run config** always wins. This is how `evals/gen_config.py` pins one
   corpus per cell, and where a staged `root` belongs.

So a run config states only what it changes, and a plain `fabench run`
evaluates the default selection. Adding a dataset never lengthens any config.
Drop in the folder, wire the processor (see
[CONTRIBUTING](../CONTRIBUTING.md)), and name it in `<lang>/config.yaml`.

## Staging

The gold corpora are licensed, and you stage them yourself. FA-Bench never
downloads TIMIT (LDC) or Buckeye (OSU registration). Stage your licensed
copies and point `root` at them in the gitignored `.fabench.env`, as
`FABENCH_<CORPUS>_ROOT`. That is what `fabench init` writes. With no root set,
ingest fails loudly with the acquisition instructions rather than fetching
anything.

Two guards back this policy.

- **Machine-aligned corpora are invalid as gold**, and the ban is built into
  the code (`fabench/config.py::EXCLUDED_AS_GOLD_DEFAULT`, sanity gate #7), so
  no config copy can drop it. An optional `datasets.excluded_as_gold` list
  extends the ban. It can never shrink it.
- **The licensed annotation itself never enters git.** The `split/*.ref.jsonl`
  files are the gold references, materialised next to the lists for locality.
  They are TIMIT `.PHN` and Buckeye `.phones` reformatted. Both licences forbid
  redistribution, and the rule in `.gitignore` keeps them out of history.

## Splits

Split membership is defined by the `.list` files. Read them, and never
re-derive membership from speaker-id patterns. The TIMIT lists exclude the two
SA sentences everywhere, because the corpus states they must not be used for
training or test. Buckeye's 60/20/20 split is by speaker, stratified on the
corpus's own sex × age design. Each `split/README.md` documents where its
split came from.

## Related

Noise sources are configured with the code that consumes them, in
`fabench/noise/config.yaml`, which covers the MUSAN fetch and cache, babble
construction and the condition matrix.
