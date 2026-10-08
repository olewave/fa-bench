# TIMIT, timestamped ASR results

**September 2026.** Systems that **decode their own words** and emit their own
word timestamps, scored on TIMIT (read US English) under clean audio and four
degradations.

These are **track 2**. They are not comparable head to head with the forced
aligners in
[the gold-transcript results](../../../gold/word/timit/README.md), which are
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
[their own page](../../phone/timit/README.md), kept separate because a phone
derived from a decoded word is not the same measurement as one derived from the
reference.

<!-- BEGIN GENERATED: word2-timit -->
<table style="margin-bottom:1.5rem">
<thead>
<tr><th rowspan="3">Family</th><th rowspan="3">Pipeline</th><th rowspan="3">System</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Dev</th><th colspan="4" style="border-left:2px solid rgba(128,128,128,.55)">TIMIT Core-test</th></tr>
<tr><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th><th colspan="2" style="border-left:2px solid rgba(128,128,128,.55)">MAE (ms)</th><th colspan="2" style="border-left:1px solid rgba(128,128,128,.25)">F1 @20 ms</th></tr>
<tr><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th><th style="border-left:2px solid rgba(128,128,128,.55)">Clean</th><th>Noisy</th><th style="border-left:1px solid rgba(128,128,128,.25)">Clean</th><th>Noisy</th></tr>
</thead>
<tbody>
<tr><td>Transducer</td><td>one-step</td><td>Parakeet-TDT</td><td style="border-left:2px solid rgba(128,128,128,.55)">79.8</td><td>78.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.194</td><td>0.181</td><td style="border-left:2px solid rgba(128,128,128,.55)">79.3</td><td>77.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.180</td><td>0.180</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → NeMo-FA 80 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">76.2</td><td>77.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.187</td><td>0.184</td><td style="border-left:2px solid rgba(128,128,128,.55)">79.3</td><td>79.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.179</td><td>0.175</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → BFA</td><td style="border-left:2px solid rgba(128,128,128,.55)">48.0</td><td>53.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.252</td><td>0.222</td><td style="border-left:2px solid rgba(128,128,128,.55)">51.0</td><td>56.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.265</td><td>0.237</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → NeMo-FA 40 ms</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.5</td><td>45.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.150</td><td>0.168</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.3</td><td>47.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.170</td><td>0.177</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → TorchAudio</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.4</td><td>42.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.186</td><td>0.175</td><td style="border-left:2px solid rgba(128,128,128,.55)">39.9</td><td>42.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.205</td><td>0.187</td></tr>
<tr><td>CTC</td><td>one-step</td><td>TorchAudio (ASR)</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.2</td><td>37.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.158</td><td>0.124</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.8</td><td>38.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.166</td><td>0.124</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">34.7</td><td>37.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.172</td><td>0.161</td><td style="border-left:2px solid rgba(128,128,128,.55)">37.3</td><td>39.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.175</td><td>0.164</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Whisper → WhisperX</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.9</td><td>36.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.175</td><td>0.161</td><td style="border-left:2px solid rgba(128,128,128,.55)">35.1</td><td>38.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.178</td><td>0.163</td></tr>
<tr><td>Open → CTC</td><td>two-step</td><td>Qwen3 → MMS-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">30.6</td><td>30.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.259</td><td>0.250</td><td style="border-left:2px solid rgba(128,128,128,.55)">31.1</td><td>31.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.271</td><td>0.258</td></tr>
<tr><td>Attention</td><td>one-step</td><td>Whisper-timestamped</td><td style="border-left:2px solid rgba(128,128,128,.55)">165.9</td><td>167.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.107</td><td>0.106</td><td style="border-left:2px solid rgba(128,128,128,.55)">161.6</td><td>163.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.113</td><td>0.108</td></tr>
<tr><td>Attention</td><td>one-step</td><td>Whisper large-v3</td><td style="border-left:2px solid rgba(128,128,128,.55)">155.3</td><td>157.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.101</td><td>0.092</td><td style="border-left:2px solid rgba(128,128,128,.55)">148.0</td><td>151.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.104</td><td>0.098</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → stable-ts</td><td style="border-left:2px solid rgba(128,128,128,.55)">99.7</td><td>96.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.167</td><td>0.176</td><td style="border-left:2px solid rgba(128,128,128,.55)">97.8</td><td>95.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.172</td><td>0.189</td></tr>
<tr><td>Attention</td><td>one-step</td><td>CrisperWhisper ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.4</td><td>36.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.439</td><td>0.418</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.5</td><td>36.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.425</td><td>0.413</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → CrisperWhisper ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.3</td><td>36.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.445</td><td>0.423</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.8</td><td>36.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.427</td><td>0.417</td></tr>
<tr><td>Open → Attention</td><td>two-step</td><td>Qwen3 → Qwen3-FA</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.4</td><td>38.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.388</td><td>0.366</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.6</td><td>38.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.385</td><td>0.367</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → UnitY2</td><td style="border-left:2px solid rgba(128,128,128,.55)">53.9</td><td>56.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.327</td><td>0.313</td><td style="border-left:2px solid rgba(128,128,128,.55)">52.4</td><td>54.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.336</td><td>0.335</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → Charsiu</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.3</td><td>38.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.510</td><td>0.463</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.2</td><td>39.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.524</td><td>0.472</td></tr>
<tr><td>Open → Frame</td><td>two-step</td><td>Qwen3 → MAPS ⚠</td><td style="border-left:2px solid rgba(128,128,128,.55)">25.4</td><td>95.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.693</td><td>0.393</td><td style="border-left:2px solid rgba(128,128,128,.55)">25.5</td><td>107.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.698</td><td>0.394</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 2.0</td><td style="border-left:2px solid rgba(128,128,128,.55)">29.3</td><td>34.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.562</td><td>0.542</td><td style="border-left:2px solid rgba(128,128,128,.55)">28.0</td><td>32.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.567</td><td>0.554</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Parakeet-TDT → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>29.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.629</td><td>0.599</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.8</td><td>29.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.622</td><td>0.600</td></tr>
<tr><td>Open → HMM</td><td>two-step</td><td>Qwen3 → MFA 3.4</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.9</td><td>30.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.631</td><td>0.601</td><td style="border-left:2px solid rgba(128,128,128,.55)">21.8</td><td>29.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.628</td><td>0.608</td></tr>
<tr><td>API</td><td>one-step</td><td>Speechmatics enhanced</td><td style="border-left:2px solid rgba(128,128,128,.55)">76.7</td><td>81.0</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.141</td><td>0.139</td><td style="border-left:2px solid rgba(128,128,128,.55)">77.1</td><td>81.5</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.155</td><td>0.143</td></tr>
<tr><td>API</td><td>one-step</td><td>IBM Watson Large</td><td style="border-left:2px solid rgba(128,128,128,.55)">73.8</td><td>75.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.154</td><td>0.149</td><td style="border-left:2px solid rgba(128,128,128,.55)">72.4</td><td>75.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.147</td><td>0.141</td></tr>
<tr><td>API</td><td>one-step</td><td>Deepgram Nova-3 ‡</td><td style="border-left:2px solid rgba(128,128,128,.55)">68.7</td><td>70.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.208</td><td>0.203</td><td style="border-left:2px solid rgba(128,128,128,.55)">67.6</td><td>70.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.208</td><td>0.198</td></tr>
<tr><td>API</td><td>one-step</td><td>Azure AI Speech</td><td style="border-left:2px solid rgba(128,128,128,.55)">64.9</td><td>69.1</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.129</td><td>0.128</td><td style="border-left:2px solid rgba(128,128,128,.55)">64.4</td><td>67.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.139</td><td>0.138</td></tr>
<tr><td>API</td><td>one-step</td><td>Amazon Transcribe</td><td style="border-left:2px solid rgba(128,128,128,.55)">56.9</td><td>57.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.256</td><td>0.257</td><td style="border-left:2px solid rgba(128,128,128,.55)">55.7</td><td>56.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.253</td><td>0.262</td></tr>
<tr><td>API</td><td>one-step</td><td>AssemblyAI Universal 3.5</td><td style="border-left:2px solid rgba(128,128,128,.55)">46.9</td><td>53.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.225</td><td>0.207</td><td style="border-left:2px solid rgba(128,128,128,.55)">47.9</td><td>53.9</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.236</td><td>0.217</td></tr>
<tr><td>API</td><td>one-step</td><td>Google Chirp 2</td><td style="border-left:2px solid rgba(128,128,128,.55)">33.2</td><td>33.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.439</td><td>0.437</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.7</td><td>32.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.443</td><td>0.446</td></tr>
<tr><td>API</td><td>one-step</td><td>ElevenLabs Scribe v2</td><td style="border-left:2px solid rgba(128,128,128,.55)">30.3</td><td>—</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.158</td><td>—</td><td style="border-left:2px solid rgba(128,128,128,.55)">32.1</td><td>32.6</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.166</td><td>0.163</td></tr>
<tr><td>API → API</td><td>two-step</td><td>Google Chirp 2 → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.7</td><td>33.3</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.716</td><td>0.572</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.1</td><td>33.7</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.734</td><td>0.574</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Parakeet-TDT → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.7</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.739</td><td>0.596</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.2</td><td>33.8</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.753</td><td>0.600</td></tr>
<tr><td>Open → API</td><td>two-step</td><td>Qwen3 → Olign 0.9</td><td style="border-left:2px solid rgba(128,128,128,.55)">19.7</td><td>33.4</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.740</td><td>0.598</td><td style="border-left:2px solid rgba(128,128,128,.55)">18.1</td><td>34.2</td><td style="border-left:1px solid rgba(128,128,128,.25)">0.759</td><td>0.607</td></tr>
</tbody>
</table>

⚠ **MAPS** trained on Buckeye, holding out only speakers 4, 27, 38, 39 and 40. FA-Bench splits Buckeye differently, so 7 of the 8 speakers in each of our Buckeye splits are in its training set and those rows are not held-out results. Its TIMIT rows are held out, because both our TIMIT splits come from TIMIT `TEST/`, which it did not train on. See [training data and overlap](../../../README.md#training-data-and-overlap).

⚠ **CrisperWhisper** names TIMIT among the datasets with word timestamps it used, and chose its alignment heads on TIMIT, without saying which part. Both our TIMIT splits come from TIMIT `TEST/`, so its TIMIT rows are held out only if it used the training part. It names no Buckeye data. See [training data and overlap](../../../README.md#training-data-and-overlap).

‡ **Deepgram Nova-3** times the last word of 24% of Buckeye test utterances (1,088 of 4,505, clean) to end more than 0.3 s after the audio does, by up to 4.1 s. Those times are scored as returned, which raises its word MAE.

<!-- END GENERATED: word2-timit -->

Per-condition breakdowns, including the decompositions behind these columns, are
in [Details.md](Details.md).

### Utterance completion

<!-- BEGIN GENERATED: completion-word2-timit -->
Utterances each system returned **nothing** for, with no record or an empty one. Boundary F1, WER and PER count everything in them as missed. MAE is over the utterances that came back, so it leaves these out.

- **Deepgram Nova-3**. Dev 0 of 400 clean, then 0, 0, 0, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 1, 0, 0 under reverb, noise, music and babble.
- **Parakeet-TDT**. Dev 0 of 400 clean, then 0, 0, 0, 4 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 0, 1, 1 under reverb, noise, music and babble.
- **Parakeet-TDT → MFA 3.4**. Dev 0 of 400 clean, then 0, 4, 1, 4 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 3, 1, 1 under reverb, noise, music and babble.
- **Parakeet-TDT → Olign 0.9**. Dev 0 of 400 clean, then 0, 0, 0, 4 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 0, 1, 1 under reverb, noise, music and babble.
- **Qwen3 → MFA 2.0**. Dev 0 of 400 clean, then 0, 7, 2, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 7, 0, 0 under reverb, noise, music and babble.
- **Qwen3 → MFA 3.4**. Dev 0 of 400 clean, then 0, 4, 1, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 0, 3, 0, 0 under reverb, noise, music and babble.
- **Whisper → WhisperX**. Dev 0 of 400 clean, then 39, 0, 0, 0 under reverb, noise, music and babble. Core-test 0 of 192 clean, then 21, 0, 0, 0 under reverb, noise, music and babble.
<!-- END GENERATED: completion-word2-timit -->
