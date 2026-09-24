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

<!-- BEGIN GENERATED: word-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">System</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>CTC</td><td>NeMo-FA 80 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">87.8</td><td>89.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.220</td><td>0.221</td><td style="border-left:2px solid rgba(128,128,128,.55)">88.7</td><td>89.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.215</td><td>0.216</td></tr>
<tr><td>CTC</td><td>NeMo-FA 40 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">65.3</td><td>68.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.222</td><td>0.224</td><td style="border-left:2px solid rgba(128,128,128,.55)">66.1</td><td>67.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.220</td><td>0.225</td></tr>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">52.4</td><td>67.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.286</td><td>0.256</td><td style="border-left:2px solid rgba(128,128,128,.55)">57.9</td><td>63.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.268</td><td>0.253</td></tr>
<tr><td>CTC</td><td>WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.8</td><td>57.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.160</td><td>0.163</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.2</td><td>57.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.159</td><td>0.160</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.6</td><td>56.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.178</td><td>0.180</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.6</td><td>56.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.178</td><td>0.176</td></tr>
<tr><td>CTC</td><td>MMS-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.9</td><td>44.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.240</td><td>0.238</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.7</td><td>44.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.237</td><td>0.235</td></tr>
<tr><td>Attention</td><td>stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">63.6</td><td>68.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.289</td><td>0.287</td><td style="border-left:2px solid rgba(128,128,128,.55)">64.1</td><td>67.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.292</td><td>0.294</td></tr>
<tr><td>Attention</td><td>CrisperWhisper</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.0</td><td>73.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.465</td><td>0.455</td><td style="border-left:2px solid rgba(128,128,128,.55)">38.8</td><td>48.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.506</td><td>0.448</td></tr>
<tr><td>Attention</td><td>Qwen3-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.4</td><td>53.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.436</td><td>0.389</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.5</td><td>48.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.396</td></tr>
<tr><td>Frame</td><td>UnitY2</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.0</td><td>38.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.520</td><td>0.514</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.9</td><td>41.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.505</td><td>0.501</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.6</td><td>69.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.601</td><td>0.475</td><td style="border-left:2px solid rgba(128,128,128,.55)">27.8</td><td>60.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.598</td><td>0.494</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.2</td><td>116.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.610</td><td>0.404</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.6</td><td>110.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.614</td><td>0.419</td></tr>
<tr><td>HMM</td><td>MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.3</td><td>31.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.699</td><td>0.615</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>30.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.696</td><td>0.629</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.9</td><td>34.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.727</td><td>0.619</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.2</td><td>33.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.731</td><td>0.637</td></tr>
<tr><td>API</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">17.5</td><td>33.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.789</td><td>0.702</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>32.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.783</td><td>0.714</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: word-buckeye -->

