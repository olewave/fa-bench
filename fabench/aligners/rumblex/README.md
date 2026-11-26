# rumblex aligner

[rumblex](https://github.com/EdwardGlockner/rumblex) word alignment. The
encoder of `Reson8/Rumble-2-Flash` and the CTC head that ships with that
checkpoint, driven on the reference transcript (`rumblex.align`). **Word
only**, with no phones, so it appears only in the word-level tables and never
in the phone tables.

The head shares the ASR decoder's subword vocabulary and the encoder emits 13
frames a second, so the raw CTC path is on an 80 ms grid. rumblex then places
each word's start and end inside its frame with a small linear map on the
encoder states around it, fitted on LibriSpeech against Montreal Forced
Aligner times (43 KB, shipped in the package). The confidence is the lowest
CTC probability among a word's tokens.

- **Modes.** A. **Granularity.** Word. **Confidence.** Yes.

## Install

```bash
evals/aligners/rumblex/download_and_install.sh   # its own venv, pinned
```

## Config

```yaml
- name: rumblex
  adapter: rumblex
  enabled: true
  modes: [A]
  granularity: [word]
  params: { model: Reson8/Rumble-2-Flash, device: cuda }
```
