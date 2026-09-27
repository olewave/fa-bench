# Changelog

Every release of FA-Bench, newest first. A benchmark's numbers move when its
scoring does, so each release lists first the changes that move published
numbers, and names the records snapshot it was scored with. Two snapshots can
be compared only when no such change lies between them.

## [Unreleased]

### Added

- The paper as `docs/paper.pdf`, linked from the top of the README by a PDF
  icon beside the title, a badge and a sentence in the introduction.
- `tools/ci.sh` runs the three CI jobs on a clean export of HEAD, in a
  Python 3.12 environment holding only what CI installs. GitHub and GitLab
  call the same script, and ruff is pinned to 0.16.9.

### Fixed

- Two workers kept an import they no longer use, which failed the lint job.
- `evals/README.md` again says the top-level `run_all.sh` uses the same
  option parser. The house-style rewrite had dropped it.

## [1.1.0] - 2026-09-26

Records snapshot `records/202609/`. This release was first tagged on
2026-09-25 and re-cut on 2026-09-26 with further scorer fixes, so numbers
taken from the first tag are superseded.

### Changes that move published numbers

- **Word MAE counts each boundary once.** A boundary shared by two words was
  counted twice, which weighted the easy interior double. MAE rose by 3 to
  5 ms.
- **Word F1 is label-checked.** A word boundary counts only when the words on
  both sides match the reference and its time is within the tolerance, the
  two utterance edges included. It paired boundaries by time alone.
- **Phone boundary F1 checks the phone labels on both sides**, as the word
  tier does.
- **An utterance a system returns nothing for is charged.** Whether it wrote
  no record or an empty one, every boundary of that utterance counts against
  F1 recall and every word and phone in it as a deletion in WER and PER. MAE
  is still over what came back. Before, such utterances left the evaluation,
  so a system that failed on hard material scored as if it had not. MFA, for
  one, returns nothing for up to 354 of Buckeye test's 4,513 utterances under
  noise.
- **A one-step recognizer is scored on the words it wrote.** The eight
  commercial endpoints had their words rewritten onto the reference spelling
  when saved (`boats` became the reference's `boat's`), and the open
  recognizers never had.
- **Word MAE matches words without regard to case**, as F1 and WER already
  did. It moved by at most 0.14 ms.
- **TIMIT's degraded audio is cut to the clean length.** Each file carried
  about 475 ms of noise after its last word, which charged a system that
  timed words into it. The TIMIT noisy cells were re-run, apart from
  ElevenLabs, which a spot check found unchanged, and NeuFA, whose output is
  cut at the clean length.
- **TIMIT's SA sentences are excluded, and Buckeye is re-split** 24/8/8 by
  speaker, balanced for sex and age.
- **The records' Noisy column averages unrounded values**, so it matches the
  paper to the last digit.

### Added

- Track 2, timestamped ASR. One-step recognizers, including eight commercial
  endpoints, and cascades that re-align a recognizer's transcript with a
  Track 1 aligner.
- NeuFA, scored from output its authors produced with a checkpoint they have
  not released.
- Boundary classes by position and by how many adjacent labels match.
- Leaderboard columns `n_absent` and `n_empty`, and an Utterance completion
  note on every records page that says who returned nothing for how much.
- Records gain the version and checkpoint of every system, the commercial
  endpoints with the model requested and the days of the calls, training data
  and overlap for every system, and the output quirks the scores keep.
- `evals/publish_records.py --release <tag>`, so a snapshot names the public
  release it was scored with.

### Changed

- Every README and the records prose are rewritten in one house style, with
  stale facts corrected along the way. There are eight commercial endpoints,
  eight Track 1 systems emit phones, ElevenLabs has twelve of its twenty
  cells, and NeuFA's rows come from its authors' checkpoint.

### Fixed

- The MFA adapter finds the micromamba its install script puts under
  `mamba_root`, and `fabench run` reads a recipe's relative paths against the
  recipe folder.
- `max_calls: 0` means no API calls, a cache-only replay. It read as no
  limit.
- The noise scripts exit non-zero when nothing was built or found.
- Audio files are written atomically.
- Machine-specific paths and account ids left the tracked recipes. They come
  from `.fabench.env`.

## [1.0.0] - 2026-08-17

First public release. Track 1 forced alignment on TIMIT and Buckeye, word
and phone tiers, clean audio and four degradations. Records snapshot
`records/202608/`.

[Unreleased]: https://github.com/olewave/fa-bench/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/olewave/fa-bench/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/olewave/fa-bench/releases/tag/v1.0.0
