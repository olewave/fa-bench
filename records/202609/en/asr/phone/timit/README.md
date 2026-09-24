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
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">43.0</td><td>60.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.4</td><td>34.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.463</td><td>0.447</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.4</td><td>70.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.470</td><td>0.463</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.0</td><td>32.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.488</td><td>0.487</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.2</td><td>32.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>36.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.503</td><td>0.500</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.6</td><td>42.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>30.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.663</td><td>0.623</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.8</td><td>45.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>32.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.656</td><td>0.614</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">17.0</td><td>143.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.5</td><td>28.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.772</td><td>0.530</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.0</td><td>157.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.763</td><td>0.519</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.8</td><td>27.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.0</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.710</td><td>0.682</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.2</td><td>25.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>35.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.715</td><td>0.689</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.0</td><td>24.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.0</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.762</td><td>0.728</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.9</td><td>25.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>35.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.762</td><td>0.730</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.8</td><td>24.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.9</td><td>33.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.764</td><td>0.728</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.8</td><td>25.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.7</td><td>35.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.763</td><td>0.727</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.9</td><td>19.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.8</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.817</td><td>0.769</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>21.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>36.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.821</td><td>0.767</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.9</td><td>19.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.3</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.821</td><td>0.770</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.5</td><td>20.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.824</td><td>0.768</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.9</td><td>19.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.5</td><td>33.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.819</td><td>0.771</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.5</td><td>20.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.824</td><td>0.772</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone2-timit -->

_Analysis to be written._
