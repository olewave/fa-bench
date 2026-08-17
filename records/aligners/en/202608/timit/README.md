# TIMIT — results

Scored with the fabench protocol — manner-matched pairing on a common
10 ms grid — under clean audio and the four degradations. MAE in ms,
lower is better.

Metric definitions and cross-corpus results are in the [methodology](../README.md).

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
blind to, is in the [methodology page](../README.md#word-level).

### Track 1 — forced alignment on the reference transcript

**WhisperX, Qwen3 and stable-ts appear only here**, having no phone tier at
all. A system already placing word boundaries poorly has less room to get
worse, so a small delta on a large clean number is not robustness.

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble); each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows an em dash rather than a partial
mean. What the four conditions actually are is on the
[methodology page](../README.md#noise-robustness); why each is read against
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
<tr><td>CTC</td><td>TorchAudio †</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.5</td><td>51.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.145</td><td>0.145</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.3</td><td>51.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.163</td><td>0.160</td></tr>
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

† **TorchAudio's phone tier is withheld.** It is the only system handed the reference phone sequence rather than deriving its own, so it cannot substitute or insert a phone and its edit columns are not comparable with the rest — see [how each system's phones reach TIMIT-39](../README.md#how-each-systems-phones-reach-timit-39). Its word tier is unaffected.

⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its own training data. Its row is not a held-out result — see [training data and overlap](../README.md#training-data-and-overlap).

<!-- END GENERATED: word-timit -->

### Track 2 — forced alignment on an ASR result

These decode their own transcript, so a misrecognised word leaves the matched
path entirely and the timing error carries recognition error with it. `WER (%)`
is here for exactly that reason: without it a poor MAE cannot be attributed
between recognition and alignment. Compare these against each other, not
against a track-1 aligner that was handed the words.

**This track is still filling up.** It currently holds the two systems whose
recipes are installed; more timestamped ASRs are being added, and each will
appear here once it has run every cell. A system missing from this table has
not been judged and found wanting — it has not been run yet. The
[coverage table](../README.md#which-subset-the-numbers-cover) on the
methodology page always names exactly who was scored.

<!-- BEGIN GENERATED: word2-timit -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="2">Family</th><th rowspan="2">System</th><th colspan="3" style="border-left:1px solid rgba(128,128,128,.35)">TIMIT Dev</th><th colspan="3" style="border-left:1px solid rgba(128,128,128,.35)">TIMIT Core-test</th></tr>
<tr><th style="border-left:1px solid rgba(128,128,128,.35)">MAE<br>(ms)</th><th>WER<br>(%)</th><th>F1</th><th style="border-left:1px solid rgba(128,128,128,.35)">MAE<br>(ms)</th><th>WER<br>(%)</th><th>F1</th></tr>
</thead>
<tbody>
<tr><td>Transducer</td><td>Parakeet-TDT</td><td style="border-left:1px solid rgba(128,128,128,.35)">74.5</td><td>1.8</td><td>0.223</td><td style="border-left:1px solid rgba(128,128,128,.35)">73.9</td><td>2.4</td><td>0.212</td></tr>
<tr><td>Attention</td><td>CrisperWhisper</td><td style="border-left:1px solid rgba(128,128,128,.35)">28.3</td><td>3.3</td><td>0.552</td><td style="border-left:1px solid rgba(128,128,128,.35)">28.1</td><td>3.6</td><td>0.534</td></tr>
</tbody>
</table>

<!-- END GENERATED: word2-timit -->

## Phone-level

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble); each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows an em dash rather than a partial
mean. What the four conditions actually are is on the
[methodology page](../README.md#noise-robustness); why each is read against
Clean rather than against its neighbours sits with the per-condition tables in
[Details](Details.md).

<!-- BEGIN GENERATED: phone-timit -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">System</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Dev</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Core-test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>CTC</td><td>TorchAudio †</td><td style="border-left:2px solid rgba(128,128,128,.55)">—</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">—</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">—</td><td>—</td><td style="border-left:2px solid rgba(128,128,128,.55)">—</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">—</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">—</td><td>—</td></tr>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">43.1</td><td>60.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.3</td><td>34.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.463</td><td>0.447</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.4</td><td>70.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.470</td><td>0.463</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.5</td><td>42.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.663</td><td>0.624</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>46.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.656</td><td>0.614</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.9</td><td>143.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.4</td><td>28.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.773</td><td>0.530</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.0</td><td>156.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.763</td><td>0.519</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.7</td><td>23.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>32.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.764</td><td>0.730</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.9</td><td>25.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>34.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.762</td><td>0.730</td></tr>
<tr><td>Closed</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.9</td><td>19.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.1</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.824</td><td>0.795</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>20.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.826</td><td>0.794</td></tr>
</tbody>
</table>

Also evaluated, in [Details](Details.md): **MFA 2.0**.
† **TorchAudio's phone tier is withheld.** It is the only system handed the reference phone sequence rather than deriving its own, so it cannot substitute or insert a phone and its edit columns are not comparable with the rest — see [how each system's phones reach TIMIT-39](../README.md#how-each-systems-phones-reach-timit-39). Its word tier is unaffected.

⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its own training data. Its row is not a held-out result — see [training data and overlap](../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-timit -->

### Utterance completion

<!-- BEGIN GENERATED: completion-timit -->
Every system scored every utterance in every split.
<!-- END GENERATED: completion-timit -->

---

