# Vendored Kaldi augmentation scripts

Copied verbatim from Kaldi's `egs/wsj/s5`, with **one** patch (below).

## Licence

These files are Kaldi's, **Apache License 2.0** — the repo-root PolyForm
Noncommercial LICENSE does not apply to this directory. Kaldi's own `COPYING`
(the Apache text plus Kaldi's contributor notice) is vendored alongside, which
is what Apache-2.0 §4 requires of redistribution: keep the licence and the
notices with the code.

## Source

| | |
|---|---|
| repo | a private Kaldi fork; these files are unmodified from upstream [kaldi-asr/kaldi](https://github.com/kaldi-asr/kaldi) apart from the patch below |
| path | `egs/wsj/s5/steps/{data,libs}` |
| last upstream commit touching `steps/data` | `48d2115e4bc6f1815186cd86095ee5d7b852d267` (2020-01-29) — *"[scripts,egs] Fix shebangs on bash scripts to #!/usr/bin/env bash, for portability (#3881)"* |
| checkout HEAD when vendored | `8c881624ee2d0d3246b92fbf3f6e9cfb3d35cb80` (fork's, not resolvable upstream) |
| vendored on | 2026-08-07 |

## Why vendored rather than symlinked

`fabench/dataprep/noisemix/make_noisy.sh` previously ran from a staging tree that symlinked
the shared checkout. That made the pipeline depend on a tree that can move,
change, or (as happened) contain committed merge conflicts. Vendoring pins the
exact code these datasets were built with, so a rebuild in six months produces
the same audio.

`wav-reverberate` — the binary doing the actual mixing — is **not** vendored; it
comes from the Kaldi build on `PATH`. Only the orchestration scripts are here.

## The one patch

`imp` was **removed in Python 3.12**. Both scripts did:

```python
data_lib = imp.load_source('dml', 'steps/data/data_dir_manipulation_lib.py')
```

replaced with an `importlib.util` equivalent that resolves the sibling module
relative to the file rather than the working directory. Marked in-file with
`# VENDOR PATCH`. Files touched: `augment_data_dir.py`,
`reverberate_data_dir.py`. Nothing else is modified.

To find every local change:

```
grep -rn "VENDOR PATCH" fabench/dataprep/noisemix/kaldi/
diff -r fabench/dataprep/noisemix/kaldi/steps/data <kaldi>/egs/wsj/s5/steps/data
```

## What is NOT vendored, and why

`utils/` stays a symlink to the live checkout. It is large, broadly shared, and
its `fix_data_dir.sh` had a committed merge conflict that has since been
resolved upstream — pinning a copy would just re-freeze a bug. If `utils/`
proves unstable too, vendor it the same way and record it here.

## Known upstream quirks (not bugs we introduced)

* `augment_data_dir.py` raises on its closing `utils/fix_data_dir.sh` call when
  speaker-ids are not utt-id prefixes — true of TIMIT (`dr1_felc0_si1386` vs
  speaker `felc0`). `wav.scp` is fully written first, so the driver judges
  success by the artefact.
* The emitted `wav.scp` commands embed nested shell commands inside single
  quotes; they must be handed to a shell verbatim (see
  `fabench/dataprep/noisemix/materialise.py`).
* Reverb commands reference `RIRS_NOISES/...` **relatively**, so the working
  directory must contain that path or symlink.
