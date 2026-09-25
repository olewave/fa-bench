# TIMIT — phone tier, ASR transcript

**September 2026.** Phone-level timestamps for systems whose **words were
recognised, not given**, scored on TIMIT (read US English) under clean audio and four degradations.

Only **two-step** systems appear here. A one-step timestamped ASR emits words and
their times and stops there, so it reaches the word tier and no further; a
cascade — an ASR decoding the utterance, then a forced aligner placing the words
it produced — inherits the aligner's phone tier. That is why this page carries a
subset of the roster on
[the word-tier page](../../word/timit/README.md).

This is **not** the gold phone tier. The systems on
[the gold-transcript phone page](../../../gold/phone/timit/README.md) are handed the
reference words, so their phones come from a correct transcript and their error
is timing alone. Here the phones are derived from whatever the recogniser
decoded: a misrecognised word takes its phones out of the matched path with it,
and the average is then over an easier subset. Read the word tier's WER column
first — it is the recognition error these numbers are conditioned on — and never
rank a row here against a gold-transcript row.

## Phone-level

<!-- BEGIN GENERATED: phone2-timit -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">Pipeline</th><th rowspan="3">System</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Dev</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Core-test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">41.7</td><td>54.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.4</td><td>34.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.197</td><td>0.186</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.1</td><td>63.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.183</td><td>0.181</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.3</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.214</td><td>0.215</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>34.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>36.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.207</td><td>0.207</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>46.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>30.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.388</td><td>0.352</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.8</td><td>51.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>32.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.361</td><td>0.329</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.9</td><td>145.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.5</td><td>28.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.483</td><td>0.306</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.2</td><td>160.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.455</td><td>0.282</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.3</td><td>21.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.0</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.376</td><td>0.363</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.9</td><td>20.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>35.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.358</td><td>0.344</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.7</td><td>19.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.9</td><td>33.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.417</td><td>0.391</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.6</td><td>19.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.7</td><td>35.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.394</td><td>0.369</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.7</td><td>18.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.0</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.417</td><td>0.392</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.6</td><td>19.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>35.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.394</td><td>0.371</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.1</td><td>13.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.8</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.431</td><td>0.405</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.3</td><td>14.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>36.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.408</td><td>0.381</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.1</td><td>13.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.3</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.433</td><td>0.408</td><td style="border-left:2px solid rgba(128,128,128,.55)">7.5</td><td>13.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.411</td><td>0.384</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.1</td><td>13.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.5</td><td>33.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.434</td><td>0.409</td><td style="border-left:2px solid rgba(128,128,128,.55)">7.5</td><td>13.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.411</td><td>0.386</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone2-timit -->

_Analysis to be written._
