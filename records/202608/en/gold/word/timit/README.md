# TIMIT — word-level, forced aligners

Track 1: every system here is handed the reference transcript, so only its
timing is measured. Systems that decode their own words are scored
separately under `records/<yyyymm>/en/asr/word/timit/`.

## About TIMIT

TIMIT is read speech from 630 American English speakers. What makes it the gold
here is what ships beside the audio: `.PHN` and `.WRD` give time-aligned labels
on **both** the phone and the word tier, hand-corrected rather than produced by
an aligner — otherwise the benchmark would be scoring aligners against an
aligner. Two annotated tiers are also why one corpus serves the phone and word
tables without either being derived from the other.

Boundaries are used exactly as annotated; only the *labels* fold into the shared
TIMIT-39 inventory. Scored here: **dev (50 speakers, 400 utterances)**, a Kaldi
convention rather than a TIMIT-defined split, and TIMIT's own **core test
(24 speakers, 192 utterances)**. Both are held out.

## Word-level

Two tracks, and they are **not** comparable head-to-head:

| Track | Given | Measures | Systems |
|---|---|---|---|
| **1 — FA on the reference transcript** | audio **+ the reference words** | timing error alone | the forced aligners below |
| **2 — FA on an ASR result** | audio only; the system decodes its own words | timing error **plus** recognition error | timestamped ASRs, table after |

MAE is over word boundaries; `P/R` and `F1` are word-boundary detection at
20 ms. Why the two tracks cannot be ranked together, and what each metric is
blind to, is in the [methodology page](../../../README.md#word-level).

### Track 1 — forced alignment on the reference transcript

**WhisperX, Qwen3 and stable-ts appear only here**, having no phone tier at
all. A system already placing word boundaries poorly has less room to get
worse, so a small delta on a large clean number is not robustness.

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble); each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows an em dash rather than a partial
mean. What the four conditions actually are is on the
[methodology page](../../../README.md#noise-robustness); why each is read against
Clean rather than against its neighbours sits with the per-condition tables in
[Details](Details.md).

<!-- BEGIN GENERATED: word-timit -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">System</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Dev</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Core-test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">49.2</td><td>69.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.271</td><td>0.246</td><td style="border-left:2px solid rgba(128,128,128,.55)">50.6</td><td>78.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.281</td><td>0.263</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.5</td><td>51.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.145</td><td>0.145</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.3</td><td>51.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.163</td><td>0.160</td></tr>
<tr><td>CTC</td><td>WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.6</td><td>49.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.130</td><td>0.131</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.0</td><td>48.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.139</td><td>0.144</td></tr>
<tr><td>Attention</td><td>stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">91.4</td><td>86.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.163</td><td>0.180</td><td style="border-left:2px solid rgba(128,128,128,.55)">88.7</td><td>84.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.179</td><td>0.200</td></tr>
<tr><td>Attention</td><td>Qwen3</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.8</td><td>36.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.430</td><td>0.402</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.8</td><td>36.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.437</td><td>0.403</td></tr>
<tr><td>Attention</td><td>CrisperWhisper</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.5</td><td>29.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.552</td><td>0.529</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.8</td><td>29.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.531</td><td>0.525</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.2</td><td>55.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.541</td><td>0.474</td><td style="border-left:2px solid rgba(128,128,128,.55)">24.6</td><td>56.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.557</td><td>0.486</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.5</td><td>141.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.617</td><td>0.398</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.4</td><td>157.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.626</td><td>0.392</td></tr>
<tr><td>HMM</td><td>MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">24.6</td><td>33.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.674</td><td>0.627</td><td style="border-left:2px solid rgba(128,128,128,.55)">23.4</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.679</td><td>0.643</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.2</td><td>31.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.729</td><td>0.675</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.8</td><td>31.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.730</td><td>0.682</td></tr>
<tr><td>Closed</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.0</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.807</td><td>0.756</td><td style="border-left:2px solid rgba(128,128,128,.55)">14.7</td><td>32.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.820</td><td>0.761</td></tr>
</tbody>
</table>

⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its own training data. Its row is not a held-out result — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: word-timit -->

