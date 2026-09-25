# TIMIT — phone-level, forced aligners

Only systems that emit phone labels appear here; the word tier, which every
system reaches, is at `../../word/timit/README.md`.

## Phone-level

**Clean vs Noisy.** *Noisy* is the mean of the four Kaldi conditions (reverb,
noise, music, babble); each has its own column in
[Details](Details.md). A cell needs all four to
be averaged, so a system still mid-sweep shows an em dash rather than a partial
mean. What the four conditions actually are is on the
[methodology page](../../../README.md#noise-robustness); why each is read against
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
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">41.7</td><td>54.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.3</td><td>34.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.198</td><td>0.187</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.1</td><td>63.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.183</td><td>0.182</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.3</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>33.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.215</td><td>0.216</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>34.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>35.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.208</td><td>0.208</td></tr>
<tr><td>Attention</td><td>NeuFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>55.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>37.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.356</td><td>0.292</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.5</td><td>59.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.0</td><td>39.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.326</td><td>0.275</td></tr>
<tr><td>Frame</td><td>FALCON</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.1</td><td>74.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.0</td><td>0.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.693</td><td>0.514</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.3</td><td>79.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.0</td><td>0.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.673</td><td>0.502</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.3</td><td>46.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.389</td><td>0.354</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.9</td><td>52.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.360</td><td>0.329</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">13.9</td><td>145.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.4</td><td>28.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.484</td><td>0.308</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.3</td><td>159.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.454</td><td>0.282</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.7</td><td>18.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>32.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.419</td><td>0.394</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.6</td><td>19.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>34.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.393</td><td>0.372</td></tr>
<tr><td>API</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.2</td><td>13.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.1</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.435</td><td>0.418</td><td style="border-left:2px solid rgba(128,128,128,.55)">8.4</td><td>13.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.410</td><td>0.393</td></tr>
</tbody>
</table>

Also evaluated, in [Details](Details.md): **MFA 2.0**.
⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are: both our TIMIT splits come from TIMIT `TEST/`, which it did not train on — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-timit -->

### Utterance completion

<!-- BEGIN GENERATED: completion-timit -->
Every system scored every utterance in every split.
<!-- END GENERATED: completion-timit -->

---

