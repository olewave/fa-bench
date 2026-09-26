# Buckeye, phone-level, forced aligners

Only systems that emit phone labels appear here. The word tier, which every
system reaches, is at `../../word/buckeye/README.md`.

## Phone-level

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble), and each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows a dash rather than a partial
mean. What the four conditions are is on the
[methodology page](../../../README.md#noise-robustness). Why each is read against
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
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.1</td><td>59.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.8</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.265</td><td>0.257</td><td style="border-left:2px solid rgba(128,128,128,.55)">50.2</td><td>54.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.1</td><td>32.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.255</td><td>0.251</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.9</td><td>44.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.6</td><td>27.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.273</td><td>0.267</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.5</td><td>41.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.5</td><td>28.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.266</td><td>0.261</td></tr>
<tr><td>Attention</td><td>NeuFA ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.6</td><td>54.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">27.4</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.473</td><td>0.398</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.6</td><td>46.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.460</td><td>0.399</td></tr>
<tr><td>Frame</td><td>FALCON ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">38.1</td><td>107.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.4</td><td>0.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.589</td><td>0.461</td><td style="border-left:2px solid rgba(128,128,128,.55)">40.6</td><td>99.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.7</td><td>0.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.585</td><td>0.464</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.7</td><td>59.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.6</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.427</td><td>0.349</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>50.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">31.7</td><td>34.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.424</td><td>0.359</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>113.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.8</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.449</td><td>0.311</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.9</td><td>104.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.9</td><td>34.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.445</td><td>0.313</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.3</td><td>27.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">25.4</td><td>30.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.522</td><td>0.457</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.3</td><td>26.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">26.1</td><td>29.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.518</td><td>0.463</td></tr>
<tr><td>API</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>26.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">26.9</td><td>27.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.533</td><td>0.486</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.7</td><td>24.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.2</td><td>28.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.522</td><td>0.483</td></tr>
</tbody>
</table>

[Details](Details.md) also has **MFA 2.0**.
⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **NeuFA**'s training recipe trains on 36 Buckeye speakers and holds out only 10, 20, 30 and 40, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. It does not train on TIMIT. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **FALCON** trains on its own 80/10/10 speaker split of Buckeye, so at least 8 of the 16 speakers in our Buckeye dev and test splits are in its training set, and it is handed the reference phones. See [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-buckeye -->

### Utterance completion

<!-- BEGIN GENERATED: completion-buckeye -->
Utterances each system returned **nothing** for, with no record or an empty one. Boundary F1, WER and PER count everything in them as missed. MAE is over the utterances that came back, so it leaves these out.

- **Charsiu**. Dev 0 of 4,456 clean, then 1, 128, 30, 0 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 112, 30, 0 under reverb, noise, music and babble.
- **MFA 2.0**. Dev 17 of 4,456 clean, then 21, 383, 164, 45 under reverb, noise, music and babble. Test 6 of 4,513 clean, then 5, 357, 125, 15 under reverb, noise, music and babble.
- **MFA 3.4**. Dev 10 of 4,456 clean, then 47, 430, 205, 46 under reverb, noise, music and babble. Test 8 of 4,513 clean, then 11, 354, 170, 30 under reverb, noise, music and babble.
- **Olign 1.0**. Dev 0 of 4,456 clean, then 1, 2, 0, 2 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 1, 2, 0 under reverb, noise, music and babble.
<!-- END GENERATED: completion-buckeye -->

**Read `OS`, `R-val` and the edit columns within a corpus rather than across
it.** The two corpora annotate at different granularities, so aligners tend to
under-segment against TIMIT's gold and over-segment against Buckeye's. That is a
gold-convention difference rather than a property of any aligner, and comparing
the columns across corpora measures the conventions instead.

---

