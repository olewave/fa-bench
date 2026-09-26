# Buckeye, phone tier, ASR transcript

**September 2026.** Phone-level timestamps for systems whose **words were
recognised rather than given**, scored on Buckeye (conversational US English) under clean audio and four degradations.

Only **two-step** systems appear here. A one-step timestamped ASR emits words and
their times and stops there, so it reaches the word tier and no further. A
cascade, an ASR decoding the utterance and then a forced aligner placing the
words it produced, inherits the aligner's phone tier. That is why this page carries a
subset of the roster on
[the word-tier page](../../word/buckeye/README.md).

This is **not** the gold phone tier. The systems on
[the gold-transcript phone page](../../../gold/phone/buckeye/README.md) are handed the
reference words, so their phones come from a correct transcript and their error
is timing alone. Here the phones are derived from whatever the recogniser
decoded. A misrecognised word takes its phones out of the matched path with it,
and the average is then over an easier subset. Read the word tier's WER column
first, since it is the recognition error these numbers are conditioned on, and
never rank a row here against a gold-transcript row.

## Phone-level

<!-- BEGIN GENERATED: phone2-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">Pipeline</th><th rowspan="3">System</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.0</td><td>63.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.6</td><td>35.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.257</td><td>0.239</td><td style="border-left:2px solid rgba(128,128,128,.55)">44.2</td><td>57.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.6</td><td>35.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.253</td><td>0.238</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.2</td><td>40.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.5</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.267</td><td>0.251</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.1</td><td>38.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.0</td><td>31.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.260</td><td>0.250</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.5</td><td>114.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.1</td><td>37.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.436</td><td>0.296</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.9</td><td>108.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.8</td><td>37.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.303</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">23.2</td><td>52.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.1</td><td>37.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.417</td><td>0.338</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.2</td><td>45.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>36.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.417</td><td>0.352</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.3</td><td>27.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.3</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.471</td><td>0.417</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.6</td><td>26.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.3</td><td>32.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.466</td><td>0.426</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.4</td><td>29.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.503</td><td>0.434</td><td style="border-left:2px solid rgba(128,128,128,.55)">17.6</td><td>27.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>32.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.502</td><td>0.446</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.8</td><td>26.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.7</td><td>34.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.509</td><td>0.435</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.4</td><td>25.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.1</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.507</td><td>0.445</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>24.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.0</td><td>31.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.520</td><td>0.450</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>22.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.2</td><td>31.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.516</td><td>0.457</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.3</td><td>23.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.9</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.513</td><td>0.436</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>22.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.509</td><td>0.444</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.0</td><td>23.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.5</td><td>32.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.525</td><td>0.450</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.3</td><td>21.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.1</td><td>31.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.520</td><td>0.455</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone2-buckeye -->

_Analysis to be written._
