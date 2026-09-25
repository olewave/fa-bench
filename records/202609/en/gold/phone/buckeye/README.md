# Buckeye — phone-level, forced aligners

Only systems that emit phone labels appear here; the word tier, which every
system reaches, is at `../../word/buckeye/README.md`.

## Phone-level

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble); each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows an em dash rather than a partial
mean. What the four conditions actually are is on the
[methodology page](../../../README.md#noise-robustness); why each is read against
Clean rather than against its neighbours sits with the per-condition tables in
[Details](Details.md).

<!-- BEGIN GENERATED: phone-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">System</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="6" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">PER (%)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.1</td><td>59.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.8</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.265</td><td>0.257</td><td style="border-left:2px solid rgba(128,128,128,.55)">50.2</td><td>54.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.1</td><td>32.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.255</td><td>0.252</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.9</td><td>44.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.6</td><td>27.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.273</td><td>0.267</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.5</td><td>41.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.5</td><td>28.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.266</td><td>0.261</td></tr>
<tr><td>Attention</td><td>NeuFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.6</td><td>54.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.4</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.473</td><td>0.398</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.6</td><td>46.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.460</td><td>0.399</td></tr>
<tr><td>Frame</td><td>FALCON</td><td style="border-left:2px solid rgba(128,128,128,.55)">38.1</td><td>107.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.4</td><td>0.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.589</td><td>0.461</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.6</td><td>99.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.7</td><td>0.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.585</td><td>0.464</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.7</td><td>59.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.6</td><td>33.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.427</td><td>0.350</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>50.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">31.7</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.424</td><td>0.360</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>113.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.8</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.449</td><td>0.310</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.9</td><td>104.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.9</td><td>34.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.445</td><td>0.313</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.3</td><td>27.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">25.2</td><td>25.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.523</td><td>0.472</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.3</td><td>26.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">25.9</td><td>26.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.519</td><td>0.474</td></tr>
<tr><td>API</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>26.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">26.9</td><td>27.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.533</td><td>0.486</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.7</td><td>24.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>28.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.522</td><td>0.483</td></tr>
</tbody>
</table>

Also evaluated, in [Details](Details.md): **MFA 2.0**.
⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-buckeye -->

### Utterance completion

<!-- BEGIN GENERATED: completion-buckeye -->
Every system scored every utterance in every split.
<!-- END GENERATED: completion-buckeye -->

**Read `OS`, `R-val` and the edit columns within a corpus, not across it.** The
two corpora annotate at different granularities, so aligners tend to
under-segment against TIMIT's gold and over-segment against Buckeye's. That is a
gold-convention difference, not a property of any aligner, and comparing the
columns across corpora measures the conventions instead.

---

