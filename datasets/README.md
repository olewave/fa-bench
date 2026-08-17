# datasets/ — canonical dataset config and split definitions

One folder per corpus, grouped by language, with a language-level config
alongside:

```
datasets/languages/en/
  config.yaml          which corpora the benchmark evaluates, on which subset
  <corpus>/
    config.yaml        that corpus's own config (root, default subset, options)
    split/<name>.list  membership: one "<speaker_id> <utterance_id>" per line
    speakers.tsv       corpus speaker table, where the stratification needs it
datasets/prep/         how a staged copy BECAME this data: the commands, with
                       their parameters (ingest, noise augmentation, shadow roots)
```

This folder says what the data **is**; [`prep/`](prep/README.md) says how it was
**produced** — the invocations, not the scripts, which live in
`fabench/dataprep/`.

## How the config composes

`load_config()` builds `datasets.gold` from these layers, lowest first, merging
per key:

1. **`<lang>/<corpus>/config.yaml`** — everything corpus-intrinsic: a null
   `root`, the corpus's default `subset`, and options like `protocol`
   (Buckeye) or `merge_closures` (TIMIT), with their rationale.
2. **`<lang>/config.yaml`** — the benchmark's default *selection*: which
   corpora are enabled and at which subset.
3. **the run config** — always wins. This is how `evals/gen_config.py` pins one
   corpus per cell, and where a staged `root` belongs.

So a run config states only what it changes; a plain `fabench run` evaluates
the default selection. Adding a dataset never lengthens any config: drop the
folder, wire the processor (see [CONTRIBUTING](../CONTRIBUTING.md)), and name
it in `<lang>/config.yaml`.

## Staging: gold corpora are licensed and USER-STAGED

FA-Bench never downloads TIMIT (LDC) or Buckeye (OSU registration). Stage your
licensed copies and point `root` at them — in the gitignored `.fabench.env` as `FABENCH_<CORPUS>_ROOT` (what `fabench init` writes).
With no root set, ingest fails loud with the acquisition instructions rather
than fetching anything.

Two guards back this policy:

- **Machine-aligned corpora are invalid as gold** and the ban is built into
  the code (`fabench/config.py::EXCLUDED_AS_GOLD_DEFAULT`, sanity gate #7) so
  no config copy can drop it. An optional `datasets.excluded_as_gold:` list
  EXTENDS the ban; it can never shrink it.
- **The licensed annotation itself never enters git.** `split/*.ref.jsonl`
  (gold references materialised next to the lists for locality) are TIMIT
  `.PHN` / Buckeye `.phones` reformatted, and both licenses forbid
  redistribution — the ignore rule in `.gitignore` keeps them out of history.

## Splits

Split membership is defined by the `.list` files, not by speaker-id patterns —
read them, never re-derive. TIMIT lists exclude the two SA sentences everywhere
(the corpus states they must not be used for training or test); Buckeye's
60/20/20 split is by speaker, stratified on the corpus's own sex × age design.
Per-split provenance is documented in each `split/README.md`.

## Related

Noise sources are not datasets in this sense — their defaults live with the
code that consumes them, in `fabench/noise/config.yaml` (MUSAN fetch/cache,
babble construction, and the condition matrix).
