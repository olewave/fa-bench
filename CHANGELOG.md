# Changelog

Every release of FA-Bench, newest first. A benchmark's numbers move when its
scoring does, so each release lists first the changes that move published
numbers, and names the snapshot it was scored with. Two snapshots can
be compared only when no such change lies between them.

## [2.0.0] - 2026-10-28

FA-Bench is licensed under the Apache License 2.0 from this release. Releases
1.0.0 to 1.1.3 were published under PolyForm Noncommercial 1.0.0 and are no
longer distributed, and 2.0.0 reproduces every headline number of the October
2026 snapshot. The major number marks that boundary, and this release also
removes public code, which no minor release would do. FA-Bench now ships the
scorer, the system adapters and the data loaders. The analysis metrics, the
full report, the result tables and the code that builds them leave with
`fabench.analyze`, and the numbers are published on the leaderboard. No change
moves a headline number of the October 2026 snapshot, and `tests/repro/`
rebuilds every one of them from the frozen October system outputs.

### Licence

- `LICENSE` is the Apache License 2.0. `NOTICE` names Olewave and the
  third-party material in the tree, and `CITATION.cff` cites the paper,
  arXiv 2609.32396. Every source file carries a two-line SPDX header.
- `CONTRIBUTING.md` takes contributions under the project licence.
- The distribution is named `fa-bench`. The import name stays `fabench`. The
  wheel and the sdist carry every licence and notice file.

### Added

- Word timestamp columns, `wts_*`. Every reference word owns a start and an
  end. A timestamp is a hit when the system returned the same word, matched by
  label, and placed that timestamp within the tolerance. Recall divides by two
  per reference word and precision by two per system word, so a recognition
  error costs only the word it hit. `wts_f1` leads the word tier from this
  release, and `wts_start_mae_ms` and `wts_end_mae_ms` report the two edges
  apart. Every column this release keeps is unchanged.
- `fabench prepare` builds the four degraded conditions from your staged
  corpora. It writes the Kaldi data directories the noise recipe reads from
  the tracked split lists, so the recipe no longer needs files from outside
  the repository, and it records a sha256 manifest of every input and output.
  Each Buckeye recording is one line of those directories, since the noise is
  drawn and mixed per recording. Its noise draws match the published
  conditions line for line. See `datasets/prep/README.md` for how close the
  audio comes.
- `datasets/prep/reference_audio_202610.sha256` holds the sha256 of every
  degraded audio file of the published conditions, 2,764 in all, and
  `datasets/prep/compare_reference.py` checks a local build against it.
  `datasets/prep/README.md` says what an SNR means in these conditions.
- A cloud recipe can set `data_opt_out`. Deepgram then sends `mip_opt_out`
  and IBM its learning opt-out header, and both recipes turn it on, since the
  corpora's audio is licensed. The option stays outside the response cache
  key, so every cached response and every published number stays as it was.
- `tests/repro/test_records_202610.py` rebuilds the 40 cells of the October
  2026 snapshot from frozen system outputs and compares every headline row
  with its sha256 in `tests/repro/202610/headline_sha256.json`, so the check
  is exact to the last digit and the numbers stay off the repository. It runs only when
  `FABENCH_REPRO_INPUTS` names those inputs, which stay on the machine that
  holds them.
- `score_pair` and `aggregate` take an `extras` list, which FA-Bench itself
  never fills. Each extra sees the alignments a pair was scored on, or a
  finished row with the scores behind it, so a further metric can be computed
  without aligning twice. `runner.score_utts` returns the scores of a run.
- `evals/systems.py` holds the display name, family, pipeline and caveat flag
  of every system, for the leaderboard and the repro test alike.
- `FABENCH_PY` names the Python every driver runs.

### Changed

- FA-Bench needs Python 3.11 or newer. The GitHub pipeline runs the tests and
  the self-test on 3.11 and 3.12.
- Each leaderboard row holds the headline columns at 20 ms and the utterance
  counts `n_utts`, `n_absent` and `n_empty`. On the word tier these are
  `wts_f1`, `wts_precision`, `wts_recall`, `wts_mae_ms`, `wts_start_mae_ms`
  and `wts_end_mae_ms` with their counts, `wbe_ms` with `n_word_boundaries`,
  `wbnd_f1_all_20ms` with its denominators, and `wer`. On the phone tier they
  are `mae_ms` with `n_boundaries`, `bnd_f1_all_20ms` with its denominators,
  and `per`. Each is computed as before, and every one the October records
  hold equals its October value.
- `fabench report` writes a short `report.md` of those columns, and
  `per_type.parquet` is no longer written.
- The self-test and gate checks that read an analysis metric read a headline
  one now, each with an answer fixed in advance.
- `run_all.sh` scores each tool into its own cell and no longer pools a
  rescore into `summary/`.
- `fabench run` fetches MUSAN only when a requested condition draws from it.
  A clean run no longer downloads 11 GB.
- The MUSAN download and unpacking are rewritten. The tarball still lands only
  when its size matches, and the unpacked tree still appears only when it is
  complete, now from a staging directory that is always removed.
- `tools/build_wav_reverberate.sh` builds from a fresh Kaldi checkout again,
  and builds `wav-to-duration` too.
- The shadow step writes its WAV files with ffmpeg's bit-exact flags, so their
  headers carry no ffmpeg version and two builds from the same audio compare
  byte for byte.
- The README banner carries no Exif or C2PA metadata. Its image data is
  unchanged.
- The paper is linked on arXiv, and its PDFs are no longer in the repository.
- Examples and comments no longer quote corpus text.
- The README's leaderboard badge opens the live leaderboard at
  https://olewave.com/en/leaderboard/fa-bench in place of the records page.

- Olign 1.0 given audio alone is classed one-step, as every commercial ASR
  with timestamps is, since its words and times come back from one request.

### Removed

- The cross-vendor analysis tools, `fabench/analyze/`, the eight `evals/`
  scripts that read every system's per-utterance output side by side, and
  `evals/gen_paper_tables.py`. They are Olewave's own work and are no longer
  part of this repository.
- The analysis metrics, now part of Olewave's analysis work with the two
  items after this one. They are every column at 10, 25, 50 and 100 ms, the
  time-only boundary detection scores with over-segmentation and R-value, and
  every boundary class other than `all`. Tolerance accuracy, median and
  signed error and the bootstrap intervals go too. So do the S, D and I
  percentages, onset and offset MAE, ARR and insertion rate, the error tail
  share and the common-matched MAE. The wrong-hit share, the label variants of
  the boundary F1, calibration, latency, RTF, coverage, the speaker count and
  the underpowered flag complete the set. `fabench/metrics/` and
  `fabench/score/{calibration,latency,recall}.py` go with them.
- The full report. `fabench/report/tables.py` and `curves.py` built its
  per-type panel, degradation curves and calibration panel, and
  `per_type.parquet` fed it.
- The code that builds the records pages, `evals/update_public_tables.py`,
  `publish_records.py`, `report_parse.py`, `gen_tex_tables.py`,
  `gen_provenance.py` with its cache, and `rescore_all.sh`.
- The result tables of every snapshot under `records/`, August, September
  and October 2026, with their `Details.md` pages. They are part of Olewave's
  analysis work, and the numbers are on the leaderboard.
  `records/README.md` lists the snapshots and describes the corpora and the
  four conditions.
- `docs/metrics/word_timestamp.{EN,CN}.md`, which compared named systems
  under the word timestamp view. The README's Metrics section defines every
  `wts_*` column.
- The MFA-paper scoring protocol, `scoring.protocol: mfa_paper`, with
  `fabench/score/mfa_paper/` and its vendored mapping files. FA-Bench scores
  under its own protocol only, so the `scoring_protocol` column goes too.
- The Olign test that needed a live service. The Olign adapter speaks REST
  to the hosted endpoint, and a `transport` other than `rest` is an error.
- Two Olign 0.9 adapter options that no recipe set.
- Kaldi's unused `steps/libs/nnet3/` scripts.
- The GitHub workflows other than `ci.yml`. CI on GitHub runs `ci.yml` alone,
  with lint, the tests and the self-test.

### Fixed

- The cloud batch loop flags an exhausted quota on the worker thread that
  hit it, so no further call leaves before the main thread notices. The CI
  run on the 1.1.3 merge failed on the test for this, four calls past the
  wall on a loaded runner, and the test now expects exactly one.
- The noise recipe's manifest reads the corpus splits only. It used to read
  the noise corpora's own data directories as one more split.

## [1.1.3] - 2026-10-12

Records snapshot `records/202610/`, scored with this release. No change
moves a number published in `records/202609/`, which stands as scored for
1.1.0. The October snapshot adds PocketSphinx, Olign 1.0 and one cascade,
and its Olign rows are described below.

### Added

- Olign 1.0 as its own row beside Olign 0.9, on both tracks. On Track 1 it
  is given the reference transcript. On Track 2 it recognizes the words
  itself and then aligns them, so the tables call it two-step, as they do
  Qwen3-ASR. It is reached through Olewave's job API at
  `https://api.olewave.com/olign/v1`, with the key in `OLIGN_API_KEY`. The
  call lives with the cloud providers, which cache every response, retry
  and run requests concurrently. Recipes `evals/aligners/olign_v1/` and
  `evals/timestamp_asrs/olign_v1_asr/`.
- PocketSphinx as a Track 1 row, the HMM family's one member not built on
  Kaldi. It aligns the way `pocketsphinx align` does, with the bundled
  en-us model and CMUdict, and g2p_en for words outside the dictionary. It
  is built from a pinned main-branch commit rather than the PyPI wheel,
  because the alignment fixes that matter here landed after v5.1.1. An
  utterance that fails on the default beams is aligned again with the beams
  open. The utterances that still fail also fail upstream's own CLI, and
  they count against the row as every system's failures do. See
  `fabench/aligners/pocketsphinx/README.md`.
- Qwen3-ASR → PocketSphinx as a Track 2 cascade, generated the way the
  other cascades are.
- The records snapshot `records/202610/`, with 19 forced aligners on
  Track 1 and 34 systems on Track 2. `records/latest` and the README point
  at it. ElevenLabs Scribe v2 has 12 of its 20 cells, since the account ran
  out of credit before the dev split under the four degradations, and
  ElevenLabs forced alignment is still unpublished for the same reason.
- Each Olign 0.9 hyp record keeps the `versions` object of the response
  that made it, for responses fetched since 2026-10-11.
- A leaderboard badge at the top of the README, ahead of the paper badge,
  that opens the current snapshot's results page.

### Changed

- The three cascades into Olign 0.9 on Track 2 were rerun against the
  Olign 0.9 service that produced its Track 1 row, so every Olign 0.9 row
  comes from the same service. Under noise their word MAE improves by 0.8
  to 1.6 ms and their F1 at 20 ms by 0.02 to 0.05. Clean cells move by
  0.3 ms or less.
- A cloud recipe's `base_url` is part of its response cache key, so a
  recipe aimed at one endpoint cannot replay the cached answers of another.
  No tracked recipe sets `base_url`, so no cached response is orphaned.
- The Olign live test runs only when it is configured.

### Fixed

- The cloud adapter drops a phone whose end is not after its start, as the
  Olign 0.9 adapter has since it was written. Olign 1.0 is the only cloud
  row with a phone tier and it had kept them, so the two versions of one
  system were scored under different rules. On Buckeye dev under additive
  noise the difference was close to 10 ms of phone MAE. No published number
  moves, since Olign 1.0 first appears in `records/202610/`.
- `evals/gen_cascade_configs.py` writes a base tool's relative paths
  relative to the cascade's directory, and decides what is a path by the
  key, as the composer does. A bare `venv: venv` was left pointing at
  nothing.
- `evals/run_cpu_cells.sh` printed an empty tool name in every status line.

## [1.1.2] - 2026-10-08

No change moves a published number. The records snapshot is still
`records/202609/`, as scored for 1.1.0.

### Added

- ElevenLabs forced alignment as a Track 1 row, `elevenlabs_fa`. Each
  utterance goes to ElevenLabs' `/v1/forced-alignment` endpoint with its
  reference transcript, and the row is scored on word boundaries beside MFA
  and Olign. It ships with `enabled: false` and no published numbers, because
  every request bills the account. See
  `fabench/aligners/elevenlabs_fa/README.md`.
- `cloud_check.py` takes `--text`, the words spoken in `--audio`, so it can
  check a forced aligner. `cloud_cost.py` prices the new row and counts its
  cache in `--actual`.
- A one-column, double-spaced copy of the paper,
  `docs/paper_for_reviewer.pdf`, which the README's paper links now
  open. Its tables are set larger and write every number with its leading
  zero, 0.40 where the paper has .40, and its Fig. 1 is larger.
  `evals/gen_paper_tables.py` writes its tables in the same run as the
  paper's, so the two cannot disagree. The two-column `docs/paper.pdf`
  stays, and a section at the end of the README links both and the paper
  on arXiv.

### Changed

- The commercial cloud adapter can send the reference transcript with the
  audio. When it does, the transcript is part of the response cache key. The
  Track 2 rows send none, so their keys and cached responses are unchanged.

### Fixed

- Olign is named Olign 0.9, the version that produced its numbers. The records
  in both snapshots, the Olign adapter's docs and the caption of the paper's
  word table had called it Olign 1.0. Only the name changes.
- `docs/paper.pdf` is the revised paper. Its title is now "FA-Bench: A
  Benchmark for Phone- and Word-Level Timestamp Accuracy in Forced Alignment
  and ASR on Clean and Noisy Speech", its word table names Olign 0.9, and the
  abstract and the introduction open with a new first sentence. The text
  gives Qwen3-FA's word F1 at 20 ms as 0.40, the value in its table, where
  it said 0.39. The tables are unchanged.

## [1.1.1] - 2026-09-29

No change moves a published number. The records snapshot is still
`records/202609/`, as scored for 1.1.0.

### Added

- The paper as `docs/paper.pdf`, linked from the top of the README by a PDF
  icon beside the title, a badge and a sentence in the introduction.
- `tools/ci.sh` runs the three CI jobs on a clean export of HEAD, in a
  Python 3.12 environment holding only what CI installs. GitHub and GitLab
  call the same script, and ruff is pinned to 0.16.9.

### Fixed

- The Olign adapter reaches the hosted endpoint. The endpoint rejects
  Python's default User-Agent, so the adapter names itself, and it sends the
  service token from `.fabench.env` when one is set. The default endpoint is `https://api.olewave.com/olign/v0.9`.
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
