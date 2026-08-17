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

"""Realise a kaldi wav.scp of pipe commands into actual .wav files.

Why not awk+xargs+eval: the augmented commands embed NESTED shell commands
inside single quotes, e.g.

    wav-reverberate ... --additive-signals='wav-reverberate --duration=... "sox ..." - |'

Passing those through `xargs -I{} bash -c '... eval "$cmd"'` mangles the
quoting and every utterance dies silently. Python hands the command to one
shell verbatim, which is the only thing that survives it.

cwd matters: reverb commands reference `RIRS_NOISES/...` RELATIVELY, so they
must run from a directory where that resolves.

usage: materialise.py <wav.scp> <out-dir> <cwd> [n_jobs]
"""
import concurrent.futures as cf
import os
import re
import subprocess
import sys
from pathlib import Path


def one(job):
    utt, cmd, out_dir, cwd = job
    dest = Path(out_dir) / f"{utt}.wav"
    if dest.exists() and dest.stat().st_size > 44:      # 44 = wav header
        return True, utt, "cached"
    cmd = cmd.strip().rstrip("|").strip()
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=300, check=False)
    except subprocess.TimeoutExpired:
        return False, utt, "timeout"
    if p.returncode != 0 or len(p.stdout) <= 44:
        return False, utt, (p.stderr[-160:].decode("utf8", "replace") or "empty output")
    dest.write_bytes(p.stdout)
    return True, utt, "ok"


def main() -> int:
    scp, out_dir, cwd = sys.argv[1], sys.argv[2], sys.argv[3]
    nj = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    os.makedirs(out_dir, exist_ok=True)
    jobs = []
    with open(scp) as _scp:
      for line in _scp:
          line = line.rstrip("\n")
          if not line.strip():
              continue
          utt, cmd = re.split(r"[ \t]", line, maxsplit=1)
          jobs.append((utt, cmd, out_dir, cwd))

    ok = bad = 0
    first_err = ""
    with cf.ThreadPoolExecutor(max_workers=nj) as ex:
        for good, utt, msg in ex.map(one, jobs):
            if good:
                ok += 1
            else:
                bad += 1
                if not first_err:
                    first_err = f"{utt}: {msg}"
    print(f"   {ok} ok, {bad} failed" + (f" | first error -- {first_err}" if bad else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
