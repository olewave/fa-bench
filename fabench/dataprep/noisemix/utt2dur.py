#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC

# See LICENSE at the repository root for the full terms
#
# Licensed under the PolyForm Noncommercial License 1.0.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Noncommercial use is permitted -- research, teaching, personal study, and work
# by charitable, educational, public-safety, environmental and government
# organisations. Any commercial use requires a separate licence from Olewave, LLC.
#
# AS FAR AS THE LAW ALLOWS, THE SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR
# CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING
# OUT OF THESE TERMS OR THE USE OR NATURE OF THE SOFTWARE, UNDER ANY KIND OF
# LEGAL CLAIM.

"""Compute utt2dur from a kaldi wav.scp of ffmpeg pipes, WITHOUT running them.

Why not `utils/data/get_utt2dur.sh`: it shells out to `wav-to-duration`, which
reads the wav header and closes the pipe — ffmpeg then dies with a nonzero
status and kaldi treats the whole thing as fatal. (The staged
`split_data.sh --per-utt` is also version-mismatched in this checkout.)

The gold-prep recipe's wav.scp encodes exactly what it does to the source:

    ffmpeg ... -i <src>.WAV -ar 16000 -ac 1 -af "adelay=475,apad=pad_dur=0.475" -f wav -

so duration = source duration + adelay(ms)/1000 + pad_dur(s). Reading the
source header with soundfile is exact and costs no subprocess.

usage: utt2dur.py <wav.scp> <out-utt2dur>
"""
import re
import sys

import soundfile as sf


def main() -> int:
    n_ok = n_bad = 0
    with open(sys.argv[1]) as f, open(sys.argv[2], "w") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            utt, cmd = re.split(r"[ \t]", line, maxsplit=1)
            # Two shapes: an ffmpeg pipe (the corpora) or a bare path (MUSAN).
            m = re.search(r"-i\s+(\S+)", cmd)
            path = m.group(1) if m else cmd.strip().rstrip("|").strip()
            if not path:
                n_bad += 1
                continue
            try:
                info = sf.info(path)
                dur = info.frames / info.samplerate
            except Exception:
                n_bad += 1
                continue
            d = re.search(r"adelay=(\d+)", cmd)
            p = re.search(r"pad_dur=([\d.]+)", cmd)
            if d:
                dur += int(d.group(1)) / 1000.0
            if p:
                dur += float(p.group(1))
            out.write(f"{utt} {dur:.3f}\n")
            n_ok += 1
    print(f"  utt2dur: {n_ok} ok, {n_bad} failed", file=sys.stderr)
    return 0 if n_ok and not n_bad else (0 if n_ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
