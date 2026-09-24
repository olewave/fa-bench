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
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">52.3</td><td>66.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.289</td><td>0.260</td><td style="border-left:2px solid rgba(128,128,128,.55)">57.8</td><td>63.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.272</td><td>0.257</td></tr>
<tr><td>CTC</td><td>WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.7</td><td>57.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.159</td><td>0.163</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.1</td><td>57.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.159</td><td>0.160</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.3</td><td>56.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.178</td><td>0.180</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.5</td><td>55.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.178</td><td>0.176</td></tr>
<tr><td>Attention</td><td>stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">63.5</td><td>68.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.289</td><td>0.286</td><td style="border-left:2px solid rgba(128,128,128,.55)">64.0</td><td>67.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.292</td><td>0.294</td></tr>
<tr><td>Attention</td><td>CrisperWhisper</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.0</td><td>73.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.464</td><td>0.454</td><td style="border-left:2px solid rgba(128,128,128,.55)">38.7</td><td>48.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.506</td><td>0.448</td></tr>
<tr><td>Attention</td><td>Qwen3</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.1</td><td>52.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.388</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.4</td><td>48.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.396</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.5</td><td>69.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.600</td><td>0.474</td><td style="border-left:2px solid rgba(128,128,128,.55)">27.7</td><td>60.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.597</td><td>0.494</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.2</td><td>116.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.609</td><td>0.404</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.6</td><td>110.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.613</td><td>0.419</td></tr>
<tr><td>HMM</td><td>MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.0</td><td>31.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.698</td><td>0.614</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>30.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.695</td><td>0.628</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.5</td><td>34.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.726</td><td>0.618</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.1</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.730</td><td>0.636</td></tr>
<tr><td>Closed</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">17.4</td><td>33.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.788</td><td>0.701</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>32.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.783</td><td>0.713</td></tr>
</tbody>
</table>

⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its own training data. Its row is not a held-out result — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: word-buckeye -->

