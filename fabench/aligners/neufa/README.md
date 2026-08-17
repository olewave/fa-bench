# NeuFA aligner

> ## ✋ Wanted: a NeuFA checkpoint. This is the one row the benchmark cannot fill itself.
>
> NeuFA has **no published checkpoint** — the authors ship source only, so
> running it means training it, and that is why it has no row in the results
> tables. If you train one, it goes in the benchmark.
>
> **Train on the train splits, and the leakage problem disappears.** FA-Bench
> scores on held-out splits that are **speaker-disjoint** from train — verified,
> zero overlap in both corpora:
>
> | corpus | train | evaluated on | speaker overlap |
> |---|---|---|---|
> | TIMIT | 3,696 utts / 462 spk | dev (50 spk), core_test (24), full_test (168) | **0** |
> | Buckeye | 13,473 utts / 24 spk | dev (8 spk), test (8) | **0** |
>
> The lists are in `datasets/languages/en/{timit,buckeye}/split/train.list` and are the
> definition of the split — read membership from them, not from a speaker-id
> pattern. A checkpoint trained this way is on the same footing as every other
> row, and reports a genuinely held-out number.
>
> **This is not the recipe in the NeuFA repo, and the split has to govern BOTH
> ends.** The repo defines its own train/test division (Buckeye by speaker-id
> pattern — everything except `s10*/s20*/s30*/s40*`) and finetunes against it,
> which overlaps 36 of 40 speakers with what FA-Bench scores. Replace that
> definition with FA-Bench's lists on the training side; the evaluation side is
> already handled, because the harness reads membership from the same `.list`
> files and never from a speaker pattern.
>
> Both ends matter for the same reason. Training on our split while evaluating
> on the repo's would report a number for a different test set than the tables
> use; evaluating on ours while training on the repo's would report a leaked
> one. Only using the same definition on both sides gives a row that means what
> the column header says.
>
> ### What to send
>
> 1. the exported checkpoint (`python misc/export.py <ckpt> neufa.pt`) at a URL
>    we can fetch, or a PR pointing `params.model_path` at where it lives;
> 2. the training config — pretrain corpus, epochs, and which of
>    `pretrain`/`finetune`/`semi` you ran, so the row can carry its provenance
>    the way every other row does;
> 3. anything you had to change in the adapter to load it.
>
> We add the `evals/aligners/neufa/` recipe, run the sweep, and the row appears in
> the phone and word tables with its training data stated. Open an issue or PR —
> and if you get a number, it belongs in the tables whether it beats MFA or not.
> A published negative result is worth as much here as a win.

NeuFA — neural end-to-end forced alignment with a bidirectional attention
mechanism (Li et al., ICASSP 2022, [arXiv:2203.16838](https://arxiv.org/abs/2203.16838)).
ASR- and TTS-style learning share one attention matrix; per-phone
[left, right] boundaries are decoded from the attention weights on a 10 ms
frame grid. The paper reports, on its Buckeye test split against its MFA
baseline: **word MAE 23.7 ms vs 25.8**, **phone MAE 15.7 ms vs 18.0**
(medians 9.0 vs 12.3 and 9.1 vs 10.0). Those are the authors' numbers under
their protocol — not FA-Bench results.

- **Modes:** A (text-driven via its own cmudict+sequitur G2P). **Granularity:**
  word + phone. **Confidence:** no (boundaries are threshold-decoded).

## Requirements

```bash
git clone https://github.com/thuhcsi/NeuFA tools/NeuFA
cd tools/NeuFA && git submodule update --init --recursive
pip install torch librosa sequitur-g2p        # into the env running FA-Bench
```

**No pretrained checkpoint is distributed.** Train per the repo README
(LibriSpeech pretrain → Buckeye finetune/semi) and export with
`python misc/export.py /path/to/checkpoint neufa.pt`; point
`params.model_path` at the exported file. The adapter drives the repo's own
`inference.NeuFA` class, so the checkpoint must be one `inference.py` itself
can load.

## Config

```yaml
- name: neufa
  adapter: neufa
  enabled: true
  modes: [A]
  granularity: [word, phone]
  emits_confidence: false
  params:
    repo_path: tools/NeuFA
    model_path: tools/NeuFA/neufa.pt
    device: cuda
```

Phones are CMU ARPABET with stress digits → `arpabet` normalization source.

## Caveats

- **The repo's recipe leaks; FA-Bench's train split does not.** The published
  recipe finetunes on the Buckeye *train* speakers as the repo defines them
  (everything except `s10*/s20*/s30*/s40*`), which against full-Buckeye gold is
  36 of 40 speakers. FA-Bench does not score full-Buckeye: it scores `dev` and
  `test`, 8 speakers each, with **zero** overlap against
  `datasets/languages/en/buckeye/split/train.list`. Train on that list and the number is
  held-out. Report training provenance either way (same policy as MAPS's
  TIMIT+Buckeye overlap).
- **Boundaries are not constrained** to be positive-length or non-overlapping
  (the repo README says so itself). The adapter drops degenerate
  (`right <= left`) phones; word spans are first-phone-left → last-phone-right,
  matching the repo's own `inference.py`.
- The repo uses generic top-level module names (`inference`, `model`,
  `hparams`, `data`, `g2p`) which are put on `sys.path` — same shadowing
  caveat as the Charsiu adapter.

## Status: NOT EVALUATED — no checkpoint exists, not a bug and not a blocker

There is no NeuFA row in the results tables. That is a decision, not an
oversight, and there is no `evals/aligners/neufa/` recipe for the same reason —
nothing a sweep could run.

**No checkpoint exists.** Verified against the GitHub API on 2026-08-07, not
just inferred from the README:

| Probe | Result |
|---|---|
| `/repos/thuhcsi/NeuFA/releases` | `[]` — no release assets |
| `/repos/thuhcsi/NeuFA/tags` | `[]` |
| repo size | **50 KB** — source only; a `.pt` would be tens of MB |
| `pushed_at` | 2025-01-17 (dormant, not abandoned; 5 open issues) |

The repo's own instructions confirm it: set `hparams.py` to `pretrain` /
`finetune` / `semi`, train, then export with `misc/export.py`. Running NeuFA
means training NeuFA.

**Training it THE DOCUMENTED WAY would not produce a comparable number** —
though training it on FA-Bench's train splits would; see the top of this page.
The published recipe finetunes on Buckeye, so a recipe-trained checkpoint has
seen 36 of the 40 speakers in FA-Bench's Buckeye gold — including the test
split. It would be scoring on data it trained on. That is a different quantity
from what every other row in the table reports, and putting the two side by
side would mislead however the number came out.

Ways forward, best first:

1. **Train on FA-Bench's train splits** — the ask at the top of this page.
   Speaker-disjoint from everything it is scored on, so the number is genuinely
   held-out and ranks beside every other row. This is the footing olign is on.
   It did not exist as an option when the paragraph above was written, which
   assumed full-corpus gold, where any Buckeye finetune leaks.
2. **LibriSpeech-only checkpoint** — also leakage-free and closest to the
   paper's pretrain stage, but it skips the finetune the published figures
   depend on and will likely trail them.
3. **Leave it unevaluated** (current). Cite the paper's own figures as the
   authors' numbers under the authors' protocol, never as FA-Bench results.
4. **Repo-recipe checkpoint, flagged** — cheapest path to a number, but it can
   only be reported as train/test-overlapping and cannot be ranked.

For reference, the paper reports on its own Buckeye test split against its own
MFA baseline: word MAE **23.7 ms vs 25.8**, phone MAE **15.7 ms vs 18.0**
(medians 9.0 vs 12.3, 9.1 vs 10.0). Those are the authors' numbers under their
protocol — not FA-Bench results, and not comparable to the tables here.
