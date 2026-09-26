# NeuFA aligner

NeuFA is neural end-to-end forced alignment with a bidirectional attention
mechanism (Li et al., ICASSP 2022,
[arXiv:2203.16838](https://arxiv.org/abs/2203.16838)). ASR-style and
TTS-style learning share one attention matrix, and per-phone [left, right]
boundaries are decoded from the attention weights on a 10 ms frame grid.

- **Modes.** A (text-driven, through its own cmudict plus sequitur G2P).
  **Granularity.** Word and phone. **Confidence.** None, since boundaries are
  threshold-decoded.

## Where its numbers come from

**The NeuFA rows in the results tables are scored from output its authors
produced**, with a checkpoint they trained for this benchmark,
`neufa-fabench-220k.pt` (SHA-256 `68b163eb…`), which is not released. They
ran the model and sent the hypothesis files, and FA-Bench scored them exactly
as it scores every other system. That checkpoint follows the repo's own
Buckeye division, 36 of 40 speakers, so 7 of the 8 speakers in each of
FA-Bench's Buckeye splits are in its training set. The records flag its
Buckeye rows for that reason. It does not train on TIMIT.

The recipe here loads an earlier checkpoint the authors supplied,
`neufa_en.pt`. They say it is wrong, so none of its output is published, and
running the recipe does not reproduce the published rows.

> ## ✋ Wanted, a public NeuFA checkpoint
>
> Nobody outside can reproduce the NeuFA rows, because the checkpoint behind
> them is unreleased. A checkpoint trained on FA-Bench's train splits would
> fix that, and it would be held out as well. FA-Bench scores on splits that
> are **speaker-disjoint** from train, with zero overlap in both corpora.
>
> | corpus | train | evaluated on | speaker overlap |
> |---|---|---|---|
> | TIMIT | 3,696 utts / 462 spk | dev (50 spk), core_test (24) | **0** |
> | Buckeye | 13,473 utts / 24 spk | dev (8 spk), test (8) | **0** |
>
> The lists are in `datasets/languages/en/{timit,buckeye}/split/train.list`
> and are the definition of the split. Read membership from them rather than
> from a speaker-id pattern. A checkpoint trained this way is on the same
> footing as every other row, and reports a held-out number.
>
> **This is not the recipe in the NeuFA repo, and the split has to govern
> both ends.** The repo defines its own train/test division (Buckeye by
> speaker-id pattern, everything except `s10*/s20*/s30*/s40*`) and finetunes
> against it. Replace that definition with FA-Bench's lists on the training
> side. The evaluation side is already handled, because the harness reads
> membership from the same `.list` files and never from a speaker pattern.
>
> ### What to send
>
> 1. the exported checkpoint (`python misc/export.py <ckpt> neufa.pt`) at a
>    URL we can fetch, or a PR pointing `params.model_path` at where it lives,
> 2. the training config, with the pretrain corpus, the epochs, and which of
>    `pretrain`, `finetune` and `semi` you ran, so the row can carry its
>    provenance the way every other row does,
> 3. anything you had to change in the adapter to load it.
>
> Open an issue or a PR. If you get a number, it belongs in the tables
> whether it beats MFA or not. A published negative result is worth as much
> here as a win.

## Requirements

The recipe is `evals/aligners/neufa/download_and_install.sh`. It builds the
environment and clones the repo, and you supply the checkpoint yourself,
since none is distributed. Train per the repo README (LibriSpeech pretrain,
then Buckeye finetune or semi) and export with
`python misc/export.py /path/to/checkpoint neufa.pt`. Point
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
    venv: venv
    repo_path: repo
    model_path: repo/neufa.pt      # your exported checkpoint
```

Phones are CMU ARPABET with stress digits, so the normalization source is
`arpabet`.

## Caveats

- **Boundaries are not constrained** to be positive-length or
  non-overlapping, as the repo README says itself. Neighbouring words and
  phones overlap in the authors' output, and the records say how the scorer
  reads a boundary in that case. The adapter drops degenerate
  (`right <= left`) phones. Word spans run from the first phone's left edge to
  the last phone's right edge, matching the repo's own `inference.py`.
- The repo uses generic top-level module names (`inference`, `model`,
  `hparams`, `data`, `g2p`). The adapter runs it in its own venv through a
  worker, so those names never meet FA-Bench's own modules.

For reference, the paper reports on its own Buckeye test split against its
own MFA baseline **word MAE 23.7 ms vs 25.8** and **phone MAE 15.7 ms vs
18.0** (medians 9.0 vs 12.3 and 9.1 vs 10.0). Those are the authors' numbers
under their protocol, and they are not comparable to the tables here.
