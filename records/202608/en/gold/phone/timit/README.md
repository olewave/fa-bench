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
<tr><td>CTC</td><td>BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">43.1</td><td>60.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.3</td><td>34.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.463</td><td>0.447</td><td style="border-left:2px solid rgba(128,128,128,.55)">45.4</td><td>70.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">36.2</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.470</td><td>0.463</td></tr>
<tr><td>CTC</td><td>TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.0</td><td>32.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.9</td><td>33.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.488</td><td>0.487</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.3</td><td>32.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.9</td><td>35.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.502</td><td>0.500</td></tr>
<tr><td>Frame</td><td>Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.5</td><td>42.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.0</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.663</td><td>0.624</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>46.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.3</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.656</td><td>0.614</td></tr>
<tr><td>Frame</td><td>MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">16.9</td><td>143.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">28.4</td><td>28.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.773</td><td>0.530</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.0</td><td>156.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">30.7</td><td>30.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.763</td><td>0.519</td></tr>
<tr><td>HMM</td><td>MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.7</td><td>23.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">32.7</td><td>32.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.764</td><td>0.730</td><td style="border-left:2px solid rgba(128,128,128,.55)">15.9</td><td>25.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">34.8</td><td>34.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.762</td><td>0.730</td></tr>
<tr><td>Closed</td><td>Olign 1.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">11.9</td><td>19.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">33.1</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.824</td><td>0.795</td><td style="border-left:2px solid rgba(128,128,128,.55)">12.4</td><td>20.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">35.4</td><td>35.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.826</td><td>0.794</td></tr>
</tbody>
</table>

Also evaluated, in [Details](Details.md): **MFA 2.0**.
⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its own training data. Its row is not a held-out result — see [training data and overlap](../../../README.md#training-data-and-overlap).

<!-- END GENERATED: phone-timit -->

### Utterance completion

<!-- BEGIN GENERATED: completion-timit -->
Every system scored every utterance in every split.
<!-- END GENERATED: completion-timit -->

---

