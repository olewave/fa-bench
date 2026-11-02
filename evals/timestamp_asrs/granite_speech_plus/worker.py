#!/usr/bin/env python
# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Granite Speech 4.1 2B-plus in its OWN interpreter.

    in : {"item_id":..., "audio_path":...}
    out: {"item_id":..., "words": [[label, start_s, end_s], ...]}

Run with the model card's timestamp prompt, the model writes an END-time tag
after every word, `hello [T:45] world [T:82]`, and a `_` with its own tag for
each silence. The tag holds only the last three digits of the time in
centiseconds, so it wraps every 10 s and _parse() unwraps it the way the card
does. It never gives a START time. A word starts where the token before it
ended, word or silence, and the first one starts at 0. So a pause the model
does not mark with `_` is counted inside the next word.

Decoding follows the card: beam search (`num_beams`, 4 by default
as in IBM's reported numbers), repetition_penalty 2.0, and an output cap of
48 tokens per second of audio, at least 256.
"""
from __future__ import annotations

import json
import re
import sys

SYSTEM_PROMPT = ("Knowledge Cutoff Date: April 2024.\nToday's Date: December 19, 2024.\n"
                 "You are Granite, developed by IBM. You are a helpful AI assistant")
TS_PROMPT = ("<|audio|> Timestamps: Transcribe the speech. After each word, add a "
             "timestamp tag showing the end time in centiseconds, e.g. hello [T:45] world [T:82]")
SAMPLE_RATE = 16000
TAG = re.compile(r"\[T:(\d+)\]")
SILENCE = "_"


def _parse(text: str) -> list[list]:
    """`w [T:n] w [T:n] ...` -> [[w, start_s, end_s], ...], silences dropped.

    A tag smaller than the one before it is a 10 s rollover. Text after the
    last tag has no time and is dropped.
    """
    parts = TAG.split(text)
    words, prev_end, offset = [], 0.0, 0.0
    for lab, tag in zip(parts[::2], parts[1::2]):
        t = int(tag) / 100
        while t + offset < prev_end:
            offset += 10.0
        end = round(t + offset, 2)
        for w in lab.split():
            if w != SILENCE:
                words.append([w, prev_end, end])
        prev_end = end
    return words


def main(argv: list[str]) -> int:
    jobs_path = argv[0]
    name = argv[1] if len(argv) > 1 else "ibm-granite/granite-speech-4.1-2b-plus"
    num_beams = int(argv[2]) if len(argv) > 2 else 4
    with open(jobs_path) as f:
        jobs = [json.loads(line) for line in f if line.strip()]

    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    processor = AutoProcessor.from_pretrained(name)
    tok = processor.tokenizer
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        name, device_map=dev,
        dtype=torch.bfloat16 if dev == "cuda" else torch.float32).eval()
    chat = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": TS_PROMPT}]
    prompt = tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)

    out = sys.stdout
    for j in jobs:
        try:
            x, sr = sf.read(j["audio_path"], dtype="float32", always_2d=True)
            wav = torch.from_numpy(x.mean(axis=1)).unsqueeze(0)
            if sr != SAMPLE_RATE:
                wav = AF.resample(wav, sr, SAMPLE_RATE)
            inputs = processor(prompt, wav, device=dev, return_tensors="pt").to(dev)
            with torch.inference_mode():
                ids = model.generate(
                    **inputs,
                    max_new_tokens=max(256, int(48 * wav.shape[-1] / SAMPLE_RATE)),
                    do_sample=False, num_beams=num_beams, repetition_penalty=2.0)
            text = tok.decode(ids[0, inputs["input_ids"].shape[-1]:],
                              add_special_tokens=False, skip_special_tokens=True)
            rec = {"item_id": j["item_id"], "words": _parse(text)}
            if not rec["words"] and TAG.search(text) is None and text.strip():
                rec["error"] = "no timestamp tags in " + repr(text)[:200]
            out.write(json.dumps(rec) + "\n")
        except Exception as e:
            out.write(json.dumps({"item_id": j["item_id"],
                                  "error": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
