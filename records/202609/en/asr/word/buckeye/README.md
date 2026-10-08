# Buckeye, timestamped ASR results

**September 2026.** Systems that **decode their own words** and emit their own
word timestamps, scored on Buckeye (spontaneous conversational English) under clean audio and four
degradations.

These are **track 2**. They are not comparable head to head with the forced
aligners in
[the gold-transcript results](../../../gold/word/buckeye/README.md), which are
handed the reference transcript and measured on timing alone. A system here has
to recognise the word before it can place it, so its error mixes recognition
with alignment, which is why `WER (%)` sits beside the timing columns rather
than in a footnote. Without it a poor MAE cannot be attributed between the two.

Read WER first, then the timing. A system can post a flattering MAE by
recognising few words and placing those well, and a system can recognise almost
perfectly while placing every boundary early.

## Word-level

Not every system here reaches the phone tier. A one-step timestamped ASR emits
words and their times and nothing below. A two-step cascade inherits its
aligner's phones. The phone-level results for the systems that have them are on
[their own page](../../phone/buckeye/README.md), kept separate because a phone
derived from a decoded word is not the same measurement as one derived from the
reference.

<!-- BEGIN GENERATED: word2-buckeye -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">Pipeline</th><th rowspan="3">System</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Dev</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">Buckeye Test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>Transducer</td><td>one-step</td><td>Parakeet-TDT</td><td style="border-left:2px solid rgba(128,128,128,.55)">79.6</td><td>80.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.199</td><td>0.187</td><td style="border-left:2px solid rgba(128,128,128,.55)">80.7</td><td>80.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.192</td><td>0.185</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → NeMo-FA 80 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">88.4</td><td>89.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.186</td><td>0.176</td><td style="border-left:2px solid rgba(128,128,128,.55)">88.8</td><td>88.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.181</td><td>0.176</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → NeMo-FA 40 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">60.0</td><td>60.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.175</td><td>0.167</td><td style="border-left:2px solid rgba(128,128,128,.55)">60.8</td><td>61.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.179</td><td>0.174</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">49.9</td><td>63.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.274</td><td>0.239</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.6</td><td>61.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.275</td><td>0.242</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Whisper → WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">44.6</td><td>53.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.121</td><td>0.111</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.2</td><td>55.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.125</td><td>0.116</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">38.4</td><td>46.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.135</td><td>0.127</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.7</td><td>48.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.138</td><td>0.130</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.8</td><td>45.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.152</td><td>0.139</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.8</td><td>46.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.154</td><td>0.141</td></tr>
<tr><td>CTC</td><td>one-step</td><td>TorchAudio (ASR)</td><td style="border-left:2px solid rgba(128,128,128,.55)">36.8</td><td>39.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.078</td><td>0.046</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.8</td><td>39.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.083</td><td>0.053</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → MMS-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.6</td><td>35.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.195</td><td>0.179</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.3</td><td>36.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.196</td><td>0.184</td></tr>
<tr><td>Attention</td><td>one-step</td><td>Whisper-timestamped</td><td style="border-left:2px solid rgba(128,128,128,.55)">127.9</td><td>130.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.180</td><td>0.167</td><td style="border-left:2px solid rgba(128,128,128,.55)">133.3</td><td>136.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.175</td><td>0.164</td></tr>
<tr><td>Attention</td><td>one-step</td><td>Whisper large-v3</td><td style="border-left:2px solid rgba(128,128,128,.55)">116.6</td><td>118.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.144</td><td>0.136</td><td style="border-left:2px solid rgba(128,128,128,.55)">122.7</td><td>123.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.138</td><td>0.132</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">69.2</td><td>71.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.254</td><td>0.243</td><td style="border-left:2px solid rgba(128,128,128,.55)">70.8</td><td>73.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.257</td><td>0.251</td></tr>
<tr><td>Attention</td><td>one-step</td><td>CrisperWhisper ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.4</td><td>33.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.330</td><td>0.416</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.6</td><td>41.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.430</td><td>0.371</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → Qwen3-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.4</td><td>42.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.394</td><td>0.338</td><td style="border-left:2px solid rgba(128,128,128,.55)">30.6</td><td>41.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.386</td><td>0.341</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → CrisperWhisper ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">30.9</td><td>38.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.501</td><td>0.398</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.2</td><td>44.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.434</td><td>0.377</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → UnitY2</td><td style="border-left:2px solid rgba(128,128,128,.55)">35.1</td><td>39.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.440</td><td>0.415</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.8</td><td>44.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.422</td><td>0.407</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.6</td><td>109.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.553</td><td>0.372</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.8</td><td>109.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.551</td><td>0.383</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.1</td><td>55.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.542</td><td>0.410</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.1</td><td>50.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.543</td><td>0.433</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">23.4</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.580</td><td>0.484</td><td style="border-left:2px solid rgba(128,128,128,.55)">23.7</td><td>32.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.573</td><td>0.499</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.8</td><td>35.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.594</td><td>0.478</td><td style="border-left:2px solid rgba(128,128,128,.55)">22.7</td><td>33.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.599</td><td>0.504</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.2</td><td>33.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.602</td><td>0.480</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.3</td><td>32.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.602</td><td>0.500</td></tr>
<tr><td>API</td><td>one-step</td><td>Deepgram Nova-3 ‡</td><td style="border-left:2px solid rgba(128,128,128,.55)">90.9</td><td>86.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.204</td><td>0.187</td><td style="border-left:2px solid rgba(128,128,128,.55)">97.8</td><td>93.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.197</td><td>0.184</td></tr>
<tr><td>API</td><td>one-step</td><td>Azure AI Speech</td><td style="border-left:2px solid rgba(128,128,128,.55)">87.3</td><td>94.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.137</td><td>0.125</td><td style="border-left:2px solid rgba(128,128,128,.55)">84.7</td><td>92.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.142</td><td>0.133</td></tr>
<tr><td>API</td><td>one-step</td><td>Speechmatics enhanced</td><td style="border-left:2px solid rgba(128,128,128,.55)">76.3</td><td>84.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.137</td><td>0.121</td><td style="border-left:2px solid rgba(128,128,128,.55)">74.2</td><td>81.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.144</td><td>0.130</td></tr>
<tr><td>API</td><td>one-step</td><td>IBM Watson Large</td><td style="border-left:2px solid rgba(128,128,128,.55)">59.9</td><td>61.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.179</td><td>0.155</td><td style="border-left:2px solid rgba(128,128,128,.55)">62.0</td><td>65.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.181</td><td>0.159</td></tr>
<tr><td>API</td><td>one-step</td><td>AssemblyAI Universal 3.5</td><td style="border-left:2px solid rgba(128,128,128,.55)">55.1</td><td>66.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.202</td><td>0.180</td><td style="border-left:2px solid rgba(128,128,128,.55)">56.4</td><td>66.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.204</td><td>0.184</td></tr>
<tr><td>API</td><td>one-step</td><td>Amazon Transcribe</td><td style="border-left:2px solid rgba(128,128,128,.55)">53.5</td><td>54.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.290</td><td>0.276</td><td style="border-left:2px solid rgba(128,128,128,.55)">52.8</td><td>53.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.285</td><td>0.275</td></tr>
<tr><td>API</td><td>one-step</td><td>ElevenLabs Scribe v2</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.4</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.106</td><td>—</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.8</td><td>35.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.109</td><td>0.108</td></tr>
<tr><td>API</td><td>one-step</td><td>Google Chirp 2</td><td style="border-left:2px solid rgba(128,128,128,.55)">24.6</td><td>36.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.458</td><td>0.415</td><td style="border-left:2px solid rgba(128,128,128,.55)">26.9</td><td>28.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.442</td><td>0.414</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.4</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.668</td><td>0.539</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.6</td><td>30.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.665</td><td>0.551</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.0</td><td>28.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.636</td><td>0.498</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.2</td><td>29.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.633</td><td>0.514</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">17.7</td><td>29.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.675</td><td>0.537</td><td style="border-left:2px solid rgba(128,128,128,.55)">20.1</td><td>29.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.666</td><td>0.545</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **CrisperWhisper** names TIMIT among the datasets with word timestamps it used, and chose its alignment heads on TIMIT, without saying which part. Both our TIMIT splits come from TIMIT `TEST/`, so its TIMIT rows are held out only if it used the training part. It names no Buckeye data. See [training data and overlap](../../../README.md#training-data-and-overlap).

‡ **Deepgram Nova-3** times the last word of 24% of Buckeye test utterances (1,088 of 4,505, clean) to end more than 0.3 s after the audio does, by up to 4.1 s. Those times are scored as returned, which raises its word MAE.

<!-- END GENERATED: word2-buckeye -->

Per-condition breakdowns, including the decompositions behind these columns, are
in [Details.md](Details.md).

### Utterance completion

<!-- BEGIN GENERATED: completion-word2-buckeye -->
Utterances each system returned **nothing** for, with no record or an empty one. Boundary F1, WER and PER count everything in them as missed. MAE is over the utterances that came back, so it leaves these out.

- **Amazon Transcribe**. Dev 3 of 4,456 clean, then 3, 40, 18, 34 under reverb, noise, music and babble. Test 6 of 4,513 clean, then 6, 31, 17, 55 under reverb, noise, music and babble.
- **AssemblyAI Universal 3.5**. Dev 1 of 4,456 clean, then 2, 94, 52, 118 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 4, 71, 36, 77 under reverb, noise, music and babble.
- **Azure AI Speech**. Dev 11 of 4,456 clean, then 22, 124, 120, 236 under reverb, noise, music and babble. Test 9 of 4,513 clean, then 16, 118, 63, 172 under reverb, noise, music and babble.
- **CrisperWhisper**. Dev 35 of 4,456 clean, then 20, 12, 14, 9 under reverb, noise, music and babble. Test 8 of 4,513 clean, then 20, 21, 21, 19 under reverb, noise, music and babble.
- **Deepgram Nova-3**. Dev 14 of 4,456 clean, then 89, 176, 188, 421 under reverb, noise, music and babble. Test 8 of 4,513 clean, then 48, 135, 112, 294 under reverb, noise, music and babble.
- **ElevenLabs Scribe v2**. Dev 0 of 4,456 clean. Test 0 of 4,513 clean, then 0, 34, 12, 8 under reverb, noise, music and babble.
- **Google Chirp 2**. Dev 0 of 4,456 clean, then 0, 8, 0, 0 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 3, 0, 0 under reverb, noise, music and babble.
- **Google Chirp 2 → Olign 0.9**. Dev 0 of 4,456 clean, then 0, 8, 0, 1 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 3, 0, 0 under reverb, noise, music and babble.
- **IBM Watson Large**. Dev 4 of 4,456 clean, then 52, 120, 145, 194 under reverb, noise, music and babble. Test 7 of 4,513 clean, then 20, 92, 81, 143 under reverb, noise, music and babble.
- **Parakeet-TDT**. Dev 71 of 4,456 clean, then 32, 88, 76, 207 under reverb, noise, music and babble. Test 67 of 4,513 clean, then 37, 72, 71, 258 under reverb, noise, music and babble.
- **Parakeet-TDT → MFA 3.4**. Dev 90 of 4,456 clean, then 79, 425, 226, 217 under reverb, noise, music and babble. Test 87 of 4,513 clean, then 50, 378, 216, 291 under reverb, noise, music and babble.
- **Parakeet-TDT → Olign 0.9**. Dev 72 of 4,456 clean, then 33, 91, 79, 214 under reverb, noise, music and babble. Test 68 of 4,513 clean, then 38, 74, 73, 259 under reverb, noise, music and babble.
- **Qwen3 → Charsiu**. Dev 0 of 4,456 clean, then 1, 106, 22, 1 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 98, 25, 0 under reverb, noise, music and babble.
- **Qwen3 → CrisperWhisper**. Dev 2 of 4,456 clean, then 15, 9, 10, 11 under reverb, noise, music and babble. Test 7 of 4,513 clean, then 10, 6, 8, 21 under reverb, noise, music and babble.
- **Qwen3 → MFA 2.0**. Dev 14 of 4,456 clean, then 13, 301, 111, 12 under reverb, noise, music and babble. Test 4 of 4,513 clean, then 5, 289, 99, 11 under reverb, noise, music and babble.
- **Qwen3 → MFA 3.4**. Dev 8 of 4,456 clean, then 40, 321, 142, 8 under reverb, noise, music and babble. Test 6 of 4,513 clean, then 10, 274, 135, 12 under reverb, noise, music and babble.
- **Qwen3 → MMS-FA**. Dev 0 of 4,456 clean, then 0, 0, 0, 2 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 1, 0, 0 under reverb, noise, music and babble.
- **Qwen3 → NeMo-FA 80 ms**. Dev 10 of 4,456 clean, then 9, 9, 8, 6 under reverb, noise, music and babble. Test 10 of 4,513 clean, then 7, 8, 9, 8 under reverb, noise, music and babble.
- **Qwen3 → Olign 0.9**. Dev 0 of 4,456 clean, then 0, 0, 0, 1 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 2, 0, 0 under reverb, noise, music and babble.
- **Qwen3 → TorchAudio**. Dev 0 of 4,456 clean, then 0, 0, 0, 2 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 1, 0, 0 under reverb, noise, music and babble.
- **Speechmatics enhanced**. Dev 16 of 4,456 clean, then 19, 80, 33, 64 under reverb, noise, music and babble. Test 7 of 4,513 clean, then 7, 48, 17, 43 under reverb, noise, music and babble.
- **TorchAudio (ASR)**. Dev 2 of 4,456 clean, then 8, 147, 38, 17 under reverb, noise, music and babble. Test 3 of 4,513 clean, then 8, 165, 46, 7 under reverb, noise, music and babble.
- **Whisper large-v3**. Dev 0 of 4,456 clean, then 0, 1, 0, 2 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 0, 0, 0, 0 under reverb, noise, music and babble.
- **Whisper → WhisperX**. Dev 4 of 4,456 clean, then 141, 43, 10, 1 under reverb, noise, music and babble. Test 3 of 4,513 clean, then 195, 27, 9, 7 under reverb, noise, music and babble.
- **Whisper-timestamped**. Dev 0 of 4,456 clean, then 3, 26, 31, 77 under reverb, noise, music and babble. Test 0 of 4,513 clean, then 2, 28, 11, 50 under reverb, noise, music and babble.
<!-- END GENERATED: completion-word2-buckeye -->
