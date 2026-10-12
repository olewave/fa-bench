# PocketSphinx aligner

CMU's PocketSphinx run as a forced aligner. Its bundled US English model is a
phonetically tied mixture HMM (CMUSphinx en-us 5.2) on 10 ms frames. That puts
it in the HMM family beside MFA, as the one HMM row not built on Kaldi.

- **Modes.** A. **Granularity.** Word and phone. **Confidence.** None.
  **Device.** CPU, about 0.05 s an utterance.

## Install

```bash
evals/aligners/pocketsphinx/download_and_install.sh   # builds from GitHub, pinned commit
```

The script clones github.com/cmusphinx/pocketsphinx and builds it into its own
environment. The pin sits past the last PyPI release (v5.1.1), because the main
branch carries alignment fixes that release lacks. They include a two-pass
phone alignment and two boundary fixes in the state alignment search.

## Config

```yaml
name: pocketsphinx
adapter: pocketsphinx
enabled: true
modes: [A]
granularity: [word, phone]
params: { venv: venv, model: en-us }
```

## How it aligns

The worker does what `pocketsphinx align` does. It sets the transcript as a
chain of words, decodes once for the words and runs a second pass over the same
samples for the phones. There is no language model and bestpath is off. The
search may put a pause or a filler between any two words, and a word may take
any of its pronunciations in the dictionary.

Phones come out as ARPAbet without stress, so the normalization source is
`arpabet`. Silence and filler segments are dropped before scoring.

Words outside CMUdict get a pronunciation from g2p_en 2.1.0, the same G2P that
MAPS uses. That covers about 1 to 1.6 percent of Buckeye tokens and almost none
of TIMIT's. The largest group is Buckeye's `yknow`, which g2p_en reads as
IH K N OW. Each record counts these words in `n_g2p_words`. A token g2p_en
cannot pronounce is left out and scores as a deletion, and `n_unpronounceable`
counts those.

An utterance whose word pass runs off the default beams is aligned again with
wider ones, and its record carries `retry_beam`. The default beams stay in
force for every other utterance.

## Training data

The model's announcement says it was trained from "a big amount of speech data"
and names no corpus. An overlap with TIMIT or Buckeye can be neither shown nor
ruled out.
