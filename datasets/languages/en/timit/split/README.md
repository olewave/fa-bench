# TIMIT splits

Four splits, one `.list` file each. Every line is:

```
<speaker_id> <utterance_id>
```

so a user of the dataset can see exactly which files belong to each split
without running any code. `fabench/dataprep/datasets/en/timit/processor.py` reads these
files — membership is defined here, not in the code.

## The four splits

| List | Speakers | Utterances | Per speaker | What it is |
|---|---|---|---|---|
| `train.list` | **462** | 3,696 | 8 | all of TIMIT `TRAIN/` |
| `dev.list` | **50** | 400 | 8 | carved from `TEST/`; **not** defined by TIMIT |
| `core_test.list` | **24** | 192 | 8 | TIMIT's own core test, 2M+1F per dialect region |

`train` and the test splits are disjoint by speaker: TIMIT guarantees no speaker
appears in both portions.

`dev` and `core_test` are both carved from the same 168-speaker `TEST/`
portion and are disjoint from each other. Together they cover 74 of 168
speakers — **94 test speakers (752 utterances) are in neither**.

## SA sentences are excluded from all four

Every speaker in TIMIT reads the same two SA ("dialect") sentences, so those
sentences are text-overlapped with training by construction. The corpus is
explicit — `DOC/TESTSET.DOC`:

> To avoid overlap with the training material the 2 SA sentences have been
> excluded from the core and complete test sets. **THESE SENTENCES ARE INCLUDED
> ON THE CD-ROM, BUT SHOULD NOT BE USED FOR TRAINING OR TEST PURPOSES.**

Hence 8 sentences per speaker (5 SX + 3 SI), not 10. Verifiable directly:

```
$ grep -v '^#' train.list | grep -c '_sa[12]$'
0
$ grep -v '^#' train.list | sed 's/.*_\(s[ixa]\).*/\1/' | sort | uniq -c
   1386 si
   2310 sx
```

This is why the counts are 3,696 and 1,344 rather than the 4,620 and 1,680 you
get by taking every `.PHN` on disk. Published work that reports on 6,300
utterances is using an "all utterances as is" protocol that knowingly includes
the SA sentences; those numbers are not comparable to these splits.

## Historical reasons

### `core_test` — the corpus's own

Defined by TIMIT itself in `DOC/TESTSET.DOC`, which prints the 24 speakers in a
table by dialect region: 2 male and 1 female from each of the 8 regions. The
document calls it *"the minimum recommended set for test purposes."*
`core_test.list` is transcribed verbatim from that table; all 24 were verified
present in the corpus.

Phone-recognition results have been reported on these 24 speakers since the
late 1980s, which is why nearly every paper in the area uses it and why a
result on any other subset is hard to compare.

### Removed: `full_test`, TIMIT's complete 168-speaker test set

TIMIT's complete test set is the *text-closure* of `core_test` — every speaker
who read any text a core speaker read (`DOC/TESTSET.DOC`). That makes it a
strict **superset of both other evaluation splits**: all 24 `core_test`
speakers and all 50 `dev` speakers are inside it.

So it cannot be reported as a third cell beside them. A configuration chosen on
`dev` would be scored on a set that contains `dev`, and its row would not be
independent of the `core_test` row. It was dropped on 2026-08-12; `dev` and
`core_test` remain, and they are speaker-disjoint from each other and from
`train`.

### `dev` — a community convention, not TIMIT's

**TIMIT defines no development set.** The corpus documents only
train / core-test / complete-test. Every train/dev/test three-way split in this
literature is layered on top by the community.

`dev.list` is taken verbatim from Kaldi's `egs/timit/s5/conf/dev_spk.list` —
50 speakers, the list most people actually copy. Kaldi's companion
`test_spk.list` was checked against `DOC/TESTSET.DOC` and is **identical** to
TIMIT's core test, which confirms Kaldi originates the *dev* convention only
and takes the test set from the corpus.

The convention itself is usually traced further back, to Halberstadt & Glass at
MIT in the late 1990s (principally Halberstadt's 1998 PhD thesis).
**That attribution is unverified here** — see `docs/literature_review.md`,
which tags every claim by how it was established and lists the citations still
to check.

### `train` — all of `TRAIN/`

462 speakers, no selection applied beyond dropping SA. The commonly quoted
3,696 is exactly this.

## Known wart: dev is not text-disjoint from core_test

Because TIMIT's complete test set is the text-closure of `core_test`, **every** speaker in
`TEST/` — and therefore every dev speaker — reads the same 5 SX sentences as
some core-test speaker. `dev` and `core_test` are speaker-disjoint but share
100% of their SX texts.

For phone recognition this is mild: you tune on the same sentence texts you
test on, in different voices. **For forced alignment it is sharper**, because
the reference transcript is an *input* — a model selected on `dev` has already
seen the exact word sequences it will be tested on.

This is inherent to TIMIT's construction, not a mistake in any particular
recipe, but it is rarely stated. Text-disjointness from `core_test` cannot be
achieved within `TEST/` at all; it would require holding out `TRAIN` speakers
instead.

## Regenerating

The lists are generated from the corpus plus two external sources:

- `core_test` ← `$TIMIT/DOC/TESTSET.DOC`, Table 1
- `dev` ← Kaldi `egs/timit/s5/conf/dev_spk.list`
- `train` ← the `TRAIN/` tree

They are committed because the corpus is licence-gated and the Kaldi list is an
external dependency; a user staging TIMIT should get identical splits without
needing either source.
