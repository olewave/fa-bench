# TIMIT, word-level, forced aligners

Track 1. Every system here is handed the reference transcript, so only its
timing is measured. Systems that decode their own words are scored
separately under `records/<yyyymm>/en/asr/word/timit/`.

## About TIMIT

TIMIT is read speech from 630 American English speakers. What makes it the gold
here is what ships beside the audio. `.PHN` and `.WRD` give time-aligned labels
on **both** the phone and the word tier, hand-corrected rather than produced by
an aligner. Otherwise the benchmark would be scoring aligners against an
aligner. Two annotated tiers are also why one corpus serves the phone and word
tables without either being derived from the other.

Boundaries are used exactly as annotated, and only the *labels* fold into the
shared TIMIT-39 inventory. Scored here are **dev (50 speakers, 400
utterances)**, a Kaldi convention rather than a TIMIT-defined split, and TIMIT's
own **core test (24 speakers, 192 utterances)**. Both are held out.

## Word-level

Two tracks, and they are **not** comparable head-to-head.

| Track | Given | Measures | Systems |
|---|---|---|---|
| **1, FA on the reference transcript** | audio **+ the reference words** | timing error alone | the forced aligners below |
| **2, FA on an ASR result** | audio only, and the system decodes its own words | timing error **plus** recognition error | timestamped ASRs, on their own page |

MAE is over word boundaries. `F1` counts a word boundary only when the words on
both sides of it match the reference and it lies within 20 ms, the two utterance
edges included. Why the two tracks cannot be ranked together, and what each
metric is blind to, is in the [methodology page](../../../README.md#word-level).

### Track 1, forced alignment on the reference transcript

**CrisperWhisper, MMS-FA, NeMo-FA, Qwen3-FA, stable-ts, UnitY2 and WhisperX
appear only here**, having no phone tier at all. A system already placing word boundaries poorly has less room to get
worse, so a small delta on a large clean number is not robustness.

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble), and each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows a dash rather than a partial
mean. What the four conditions are is on the
[methodology page](../../../README.md#noise-robustness). Why each is read against
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
<tr><td>CTC</td><td>NeMo-FA 80 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">76.2</td><td>77.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.192</td><td>0.191</td><td style="border-left:2px solid rgba(128,128,128,.55)">79.2</td><td>79.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.186</td><td>0.183</td></tr>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.9</td><td>53.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.261</td><td>0.230</td><td style="border-left:2px solid rgba(128,128,128,.55)">51.0</td><td>56.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.272</td><td>0.244</td></tr>
<tr><td>CTC</td><td>NeMo-FA 40 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.5</td><td>46.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.156</td><td>0.174</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.4</td><td>47.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.174</td><td>0.183</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.3</td><td>42.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.190</td><td>0.181</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.8</td><td>42.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.210</td><td>0.192</td></tr>
<tr><td>CTC</td><td>WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.5</td><td>38.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.176</td><td>0.166</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.2</td><td>39.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.180</td><td>0.170</td></tr>
<tr><td>CTC</td><td>MMS-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">30.5</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.266</td><td>0.259</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.1</td><td>31.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.275</td><td>0.264</td></tr>
<tr><td>Attention</td><td>stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">98.7</td><td>95.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.169</td><td>0.181</td><td style="border-left:2px solid rgba(128,128,128,.55)">96.8</td><td>94.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.177</td><td>0.195</td></tr>
<tr><td>Attention</td><td>NeuFA ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">55.2</td><td>84.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.533</td><td>0.456</td><td style="border-left:2px solid rgba(128,128,128,.55)">56.9</td><td>88.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.523</td><td>0.446</td></tr>
<tr><td>Attention</td><td>CrisperWhisper ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.4</td><td>36.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.457</td><td>0.437</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.1</td><td>36.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.437</td><td>0.430</td></tr>
<tr><td>Attention</td><td>Qwen3-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.7</td><td>38.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.403</td><td>0.380</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.2</td><td>38.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.399</td><td>0.377</td></tr>
<tr><td>Frame</td><td>UnitY2</td><td style="border-left:2px solid rgba(128,128,128,.55)">53.8</td><td>55.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.335</td><td>0.325</td><td style="border-left:2px solid rgba(128,128,128,.55)">52.2</td><td>53.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.343</td><td>0.346</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.3</td><td>39.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.522</td><td>0.476</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.1</td><td>40.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.540</td><td>0.487</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">25.4</td><td>95.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.711</td><td>0.406</td><td style="border-left:2px solid rgba(128,128,128,.55)">25.5</td><td>110.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.715</td><td>0.403</td></tr>
<tr><td>HMM</td><td>MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.1</td><td>33.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.578</td><td>0.560</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.3</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.583</td><td>0.572</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>29.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.647</td><td>0.621</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.8</td><td>30.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.644</td><td>0.624</td></tr>
<tr><td>API</td><td>Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.4</td><td>32.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.767</td><td>0.664</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.2</td><td>33.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.782</td><td>0.669</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **NeuFA**'s training recipe trains on 36 Buckeye speakers and holds out only 10, 20, 30 and 40, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. It does not train on TIMIT. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **CrisperWhisper** names TIMIT among the datasets with word timestamps it used, and chose its alignment heads on TIMIT, without saying which part. Both our TIMIT splits come from TIMIT `TEST/`, so its TIMIT rows are held out only if it used the training part. It names no Buckeye data. See [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: word-timit -->

### Utterance completion

<!-- BEGIN GENERATED: completion-word-timit -->
Utterances each system returned **nothing** for, with no record or an empty one. Boundary F1, WER and PER count everything in them as missed. MAE is over the utterances that came back, so it leaves these out.

- **MFA 2.0**. Dev 0 of 400 clean, then 0, 7, 2, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 6, 0, 0 under reverb, noise, music and babble.
- **MFA 3.4**. Dev 0 of 400 clean, then 0, 4, 1, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 2, 0, 0 under reverb, noise, music and babble.
<!-- END GENERATED: completion-word-timit -->
