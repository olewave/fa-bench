# TIMIT, phone-level, forced aligners

Only systems that emit phone labels appear here. The word tier, which every
system reaches, is at `../../word/timit/README.md`.

## Phone-level

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble), and each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows a dash rather than a partial
mean. What the four conditions are is on the
[methodology page](../../../README.md#noise-robustness). Why each is read against
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
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">41.7</td><td>45.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.3</td><td>34.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.198</td><td>0.191</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.1</td><td>48.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.183</td><td>0.178</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.3</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>33.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.215</td><td>0.214</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>33.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>35.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.208</td><td>0.206</td></tr>
<tr><td>Attention</td><td>NeuFA ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>52.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>37.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.356</td><td>0.295</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.5</td><td>56.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.0</td><td>39.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.326</td><td>0.277</td></tr>
<tr><td>Frame</td><td>FALCON ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>63.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.0</td><td>0.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.693</td><td>0.530</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.3</td><td>67.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.0</td><td>0.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.673</td><td>0.519</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>25.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>29.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.389</td><td>0.373</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.9</td><td>28.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>31.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.360</td><td>0.347</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.9</td><td>76.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.4</td><td>28.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.484</td><td>0.344</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.3</td><td>89.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.454</td><td>0.319</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.7</td><td>16.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>33.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.419</td><td>0.394</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.6</td><td>17.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>35.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.393</td><td>0.372</td></tr>
<tr><td>API</td><td>Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.2</td><td>12.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.1</td><td>33.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.418</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.4</td><td>13.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.410</td><td>0.393</td></tr>
</tbody>
</table>

[Details](Details.md) also has **MFA 2.0**.
⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **NeuFA**'s training recipe trains on 36 Buckeye speakers and holds out only 10, 20, 30 and 40, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. It does not train on TIMIT. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **FALCON** trains on its own 80/10/10 speaker split of Buckeye, so at least 8 of the 16 speakers in our Buckeye dev and test splits are in its training set, and it is handed the reference phones. See [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-timit -->

### Utterance completion

<!-- BEGIN GENERATED: completion-timit -->
Utterances each system returned **nothing** for, with no record or an empty one. Boundary F1, WER and PER count everything in them as missed. MAE is over the utterances that came back, so it leaves these out.

- **MFA 2.0**. Dev 0 of 400 clean, then 0, 7, 2, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 6, 0, 0 under reverb, noise, music and babble.
- **MFA 3.4**. Dev 0 of 400 clean, then 0, 4, 1, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 2, 0, 0 under reverb, noise, music and babble.
<!-- END GENERATED: completion-timit -->

---

