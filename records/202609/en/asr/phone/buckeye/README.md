# BUCKEYE — phone tier, ASR transcript

**September 2026.** Phone-level timestamps for systems whose **words were
recognised, not given**, scored on Buckeye (conversational US English) under clean audio and four degradations.

Only **two-step** systems appear here. A one-step timestamped ASR emits words and
their times and stops there, so it reaches the word tier and no further; a
cascade — an ASR decoding the utterance, then a forced aligner placing the words
it produced — inherits the aligner's phone tier. That is why this page carries a
subset of the roster on
[the word-tier page](../../word/buckeye/README.md).

This is **not** the gold phone tier. The systems on
[the gold-transcript phone page](../../../gold/phone/buckeye/README.md) are handed the
reference words, so their phones come from a correct transcript and their error
is timing alone. Here the phones are derived from whatever the recogniser
decoded: a misrecognised word takes its phones out of the matched path with it,
and the average is then over an easier subset. Read the word tier's WER column
first — it is the recognition error these numbers are conditioned on — and never
rank a row here against a gold-transcript row.

## Phone-level

<!-- BEGIN GENERATED: phone2-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">Pipeline</th><th rowspan="3">System</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">51.8</td><td>70.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.6</td><td>35.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.515</td><td>0.499</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.2</td><td>63.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.6</td><td>35.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.511</td><td>0.498</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>41.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.5</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.513</td><td>0.502</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.9</td><td>40.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.0</td><td>31.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.509</td><td>0.500</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.1</td><td>121.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.1</td><td>37.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.710</td><td>0.506</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.1</td><td>114.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.8</td><td>37.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.713</td><td>0.515</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">24.2</td><td>56.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.1</td><td>37.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.682</td><td>0.584</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.1</td><td>48.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>36.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.686</td><td>0.603</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.6</td><td>30.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.1</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.753</td><td>0.702</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.7</td><td>28.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>29.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.748</td><td>0.710</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.1</td><td>32.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.9</td><td>30.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.802</td><td>0.733</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.1</td><td>29.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.802</td><td>0.742</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.6</td><td>29.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">26.8</td><td>29.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.810</td><td>0.740</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.3</td><td>27.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.1</td><td>29.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.808</td><td>0.746</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.8</td><td>27.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.8</td><td>34.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.837</td><td>0.752</td><td style="border-left:2px solid rgba(128,128,128,.55)">14.0</td><td>25.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.2</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.833</td><td>0.758</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.6</td><td>27.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.0</td><td>31.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.839</td><td>0.757</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.6</td><td>24.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">29.2</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.838</td><td>0.766</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.7</td><td>26.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.9</td><td>31.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.846</td><td>0.763</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.9</td><td>23.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.4</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.842</td><td>0.768</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone2-buckeye -->

_Analysis to be written._
