# Buckeye — word-level, forced aligners

Track 1: every system here is handed the reference transcript, so only its
timing is measured. Systems that decode their own words are scored
separately under `records/<yyyymm>/en/asr/word/buckeye/`.

## About Buckeye

Buckeye is conversational speech — 40 speakers from Columbus, Ohio, in
open-ended interviews. Like TIMIT it ships **hand-checked time-aligned labels on
both tiers** (`.phones`, `.words`), the phonetic tier aligned automatically then
corrected by hand. What it adds is that the labels describe speech as
*produced*: talkers reduce, delete and merge, and the annotators transcribed
what was said — so these boundaries are genuinely ambiguous ones.

Its edit columns are **not** comparable with TIMIT's, which annotates at a
different granularity (see the note at the end of this page). The interviews are
cut into utterance-sized chunks at silences and interviewer turns, but
**boundary times are used exactly as annotated**.

Buckeye ships **no official split**; these are an FA-Bench convention: **dev
(8 speakers, 4,456 utterances)** and **test (8 speakers, 4,513 utterances)**,
both held out, the other 24 speakers reserved for training.

## Word-level

Two tracks, and they are **not** comparable head-to-head:

| Track | Given | Measures | Systems |
|---|---|---|---|
| **1 — FA on the reference transcript** | audio **+ the reference words** | timing error alone | the forced aligners below |
| **2 — FA on an ASR result** | audio only; the system decodes its own words | timing error **plus** recognition error | timestamped ASRs, table after |

MAE is over word boundaries. `F1` counts a word boundary only when the words on
both sides of it match the reference and it lies within 20 ms, the two utterance
edges included. Why the two tracks cannot be ranked together, and what each
metric is blind to, is in the [methodology page](../../../README.md#word-level).

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

<!-- BEGIN GENERATED: word-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">System</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>CTC</td><td>NeMo-FA 80 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">90.2</td><td>92.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.220</td><td>0.222</td><td style="border-left:2px solid rgba(128,128,128,.55)">91.4</td><td>93.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.212</td><td>0.216</td></tr>
<tr><td>CTC</td><td>NeMo-FA 40 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">61.4</td><td>64.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.208</td><td>0.212</td><td style="border-left:2px solid rgba(128,128,128,.55)">62.8</td><td>65.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.210</td><td>0.215</td></tr>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">49.7</td><td>63.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.315</td><td>0.294</td><td style="border-left:2px solid rgba(128,128,128,.55)">57.2</td><td>61.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.301</td><td>0.289</td></tr>
<tr><td>CTC</td><td>WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.3</td><td>51.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.162</td><td>0.166</td><td style="border-left:2px solid rgba(128,128,128,.55)">41.7</td><td>52.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.165</td><td>0.166</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.2</td><td>51.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.179</td><td>0.178</td><td style="border-left:2px solid rgba(128,128,128,.55)">42.4</td><td>51.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.180</td><td>0.175</td></tr>
<tr><td>CTC</td><td>MMS-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">35.4</td><td>40.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.225</td><td>0.223</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.1</td><td>41.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.225</td><td>0.222</td></tr>
<tr><td>Attention</td><td>stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">69.4</td><td>74.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.292</td><td>0.294</td><td style="border-left:2px solid rgba(128,128,128,.55)">71.2</td><td>75.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.294</td><td>0.295</td></tr>
<tr><td>Attention</td><td>CrisperWhisper</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.8</td><td>73.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.462</td><td>0.456</td><td style="border-left:2px solid rgba(128,128,128,.55)">43.1</td><td>52.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.487</td><td>0.442</td></tr>
<tr><td>Attention</td><td>Qwen3-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.7</td><td>54.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.440</td><td>0.392</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>50.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.432</td><td>0.392</td></tr>
<tr><td>Attention</td><td>NeuFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.0</td><td>61.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.726</td><td>0.610</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.9</td><td>59.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.700</td><td>0.605</td></tr>
<tr><td>Frame</td><td>UnitY2</td><td style="border-left:2px solid rgba(128,128,128,.55)">35.6</td><td>44.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.497</td><td>0.490</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.6</td><td>49.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.475</td><td>0.471</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.7</td><td>114.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.626</td><td>0.438</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.9</td><td>111.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.620</td><td>0.444</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.0</td><td>67.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.606</td><td>0.472</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.1</td><td>60.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.607</td><td>0.495</td></tr>
<tr><td>HMM</td><td>MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.0</td><td>32.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.661</td><td>0.583</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.5</td><td>32.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.650</td><td>0.591</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.6</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.677</td><td>0.578</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.3</td><td>35.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.683</td><td>0.597</td></tr>
<tr><td>API</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.4</td><td>36.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.755</td><td>0.653</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.5</td><td>36.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.744</td><td>0.659</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: word-buckeye -->

