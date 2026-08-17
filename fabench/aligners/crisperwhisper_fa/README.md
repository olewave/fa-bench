# CrisperWhisper as a forced aligner

`nyrahealth/CrisperWhisper` is a Whisper derivative fine-tuned for **verbatim**
transcription with tight word timings — it keeps disfluencies and filled pauses
that standard Whisper silently normalises away. The package exposes
`forced_align(audio, text, language=...)` as a native API, so it can be driven
as a track-1 forced aligner rather than only as an ASR.

Two FA-Bench tools share one model, one venv and one `worker.py`, differing
only in the mode passed as `argv[3]`:

| Tool | Mode | Input | Contract |
|---|---|---|---|
| `fabench.timestamp_asrs.crisperwhisper` | `transcribe` | audio only | decodes its own words — track 2 |
| `fabench.aligners.crisperwhisper_fa` | `forced_align` | audio + reference | times for YOUR words — track 1 |

Only the aligner is comparable to MFA/olign. The ASR's errors mix recognition
with timing: a misrecognised word leaves the matched path entirely.

## The 30-second window, and why it wrecked the mean

Whisper pads **every** input to a fixed 30 s window. When the decoder loses a
token, CrisperWhisper attaches it to the trailing silence instead of failing.
The worker took `forced_align` output verbatim, so a timestamp far outside the
audio reached the scorer as a valid boundary.

Measured on `timit/core_test` (192 utterances), **11 (5.7%)** placed at least
one word past the end of the audio. The worst case, `dr4_mlll0_si1993` — a
**2.48 s** file:

```
  audio  0                1                2         2.48 s                              30 s
         |════════════════|════════════════|═════════|                                    |

                                                     └─ real audio ends       Whisper pad ┘

  GOLD   should     she    wake    him
         [0.76─0.99][0.99─1.15][1.15─1.41][1.41─1.56]

  HYP    should     she    wake                                              him
         [0.78─1.01][1.01─1.17][1.17─1.36]                              [29.32─29.62]
          ✓ +20ms    ✓ +20ms    ✓ −50ms                                  ✗ +27,910 ms
                                                                              ▲
                        three words within 20 ms of gold ────────────────────┘
                        then the last one lands in the padding
```

The first three words are as good as MFA's. The fourth is 27.9 s late, in
silence that is not part of the recording at all.

Those few utterances dominated the average completely:

| | Median | Mean | P90 | P99 | Max |
|---|---|---|---|---|---|
| before the guard | 30.3 | **223.9** | 53 | 4631 | 6991 |
| after the guard | 28.6 | **31.0** | — | — | **95** |
| MFA, same cell | 16.0 | 17.3 | 26 | 40 | 43 |

So the published 219–239 ms was never a measure of alignment quality — it was a
5.7% catastrophic-failure rate. The median of ~30 ms, competitive with charsiu
and behind MFA's 16, is the honest description of the other 94%.

## The guard

`evals/timestamp_asrs/crisperwhisper/worker.py` reads the audio duration and
drops any word whose start or end falls outside `0..duration` (+50 ms
tolerance), logging the item.

A dropped word has no hypothesis and scores as a **deletion**, which `Del%`
already accounts for. That is the honest outcome: the model genuinely failed to
place it, and a deletion says so, where a 29 s boundary claims a measurement
that was never made.

**Do not read the guard as a fix to the model.** It stops a decode failure
being scored as alignment, nothing more. The underlying behaviour — losing a
token into the padding on ~6% of short utterances — is unchanged, and is worth
knowing about before deploying this model on short audio.

## Cost

~5.9 s/utterance on a 3090 (measured: TIMIT full_test, 1344 items, 7632–8180 s).
That is ~200× parakeet_tdt, which does Buckeye's 4,456 utterances in 128 s. Its
Buckeye cells need ~7.3 h each, which is why `timeout_s: null` (no timeout) is
set — the batch worker emits nothing until it finishes, so a timeout destroys
the run rather than truncating it. Both variants once spent 4 h on `buckeye_dev`
and wrote 0 records.

For the same reason it is **excluded from the noise sweep**: its 16
Buckeye-sized noisy cells were 139 of that sweep's 152 projected GPU-hours (91%).
