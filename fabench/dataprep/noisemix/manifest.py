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

"""Record exactly what was mixed into every generated noisy file.

FA-Bench is a TEST set, so a noisy condition is only useful if it is
reproducible and auditable: which noise recording, at which SNR, starting
where, and for reverb which impulse response.

That provenance already exists — Kaldi encodes it in the `wav.scp` command it
generates, e.g.

    wav-reverberate --shift-output=true \\
      --additive-signals='<musan>/speech-librivox-0137.wav,...' \\
      --start-times='0,0,0' --snrs='20,13,20' ...

so this does not re-derive anything; it parses what was actually run into a
per-utterance record. If the mixing ever disagrees with this manifest, the
manifest is wrong — the command is the ground truth.

Writes one JSONL per (corpus, condition):

    /scratch/data/speech/english/<corpus>/noisy/<cond>/manifest.jsonl
      {"utt_id":..., "condition":"babble",
       "snrs":[20.0,13.0,20.0],
       "noises":["<musan>/speech-librivox-0137.wav", ...],
       "start_times":[0.0,0.0,0.0],
       "rir": null}

usage: manifest.py <work-dir> <out-root>
"""
import json
import re
import sys
from pathlib import Path

CONDITIONS = ("reverb", "noise", "music", "babble")


def parse(cmd: str) -> dict:
    """Pull the mixing parameters out of one wav-reverberate command."""
    def lst(pat, cast=str):
        m = re.search(pat, cmd)
        if not m:
            return []
        return [cast(x) for x in m.group(1).split(",") if x.strip()]

    # additive signals may themselves be nested `wav-reverberate ... "<path>" - |`
    raw = re.search(r"--additive-signals='([^']*)'", cmd)
    noises = []
    if raw:
        for part in raw.group(1).split(","):
            inner = re.search(r'"([^"]+\.wav)"', part) or re.search(r"(\S+\.wav)", part)
            if inner:
                noises.append(inner.group(1))

    rir = None
    m = re.search(r'--impulse-response="[^"]*?(\S+\.wav)', cmd)
    if m:
        rir = m.group(1)

    return {
        "snrs": lst(r"--snrs='([^']*)'", float),
        "noises": noises,
        "start_times": lst(r"--start-times='([^']*)'", float),
        "rir": rir,
    }


def main() -> int:
    work, out_root = Path(sys.argv[1]), Path(sys.argv[2])
    written = 0
    for cond in CONDITIONS:
        by_corpus: dict[str, list] = {}
        for scp in sorted(work.glob(f"*_{cond}/wav.scp")):
            split = scp.parent.name[: -len(f"_{cond}")]
            corpus = "TIMIT" if split.startswith("timit") else "Buckeye"
            with open(scp) as _scp:
              for line in _scp:
                  line = line.rstrip("\n")
                  if not line.strip():
                      continue
                  utt, cmd = re.split(r"[ \t]", line, maxsplit=1)
                  rec = {"utt_id": utt, "split": split, "condition": cond}
                  rec.update(parse(cmd))
                  by_corpus.setdefault(corpus, []).append(rec)
        for corpus, recs in by_corpus.items():
            d = out_root / corpus / "noisy" / cond
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "manifest.jsonl", "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in recs)
            print(f"  {corpus}/{cond}: {len(recs)} records")
            written += len(recs)
    print(f"  {written} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
