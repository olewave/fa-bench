# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""Compare a `fabench prepare` build with the published degraded audio.

usage: python datasets/prep/compare_reference.py <out>/manifest.json

reference_audio_202610.sha256 holds the sha256 of every degraded file behind
the published cells. This prints, per corpus, subset and condition, how many
of your files are byte-identical to them and how many your build did not make.
"""
import json
import sys
from collections import Counter
from pathlib import Path

REFERENCE = Path(__file__).with_name("reference_audio_202610.sha256")
CORPUS_DIR = {"timit": "TIMIT", "buckeye": "Buckeye"}


def main(manifest: str) -> int:
    outputs = json.loads(Path(manifest).read_text())["outputs"]
    same, differ, missing = Counter(), Counter(), Counter()
    for line in REFERENCE.read_text().splitlines():
        ref, rel = line.split("  ", 1)
        corpus, subset, cond, name = rel.split("/")
        key = (corpus, subset, cond)
        mine = outputs.get(f"noisy/{CORPUS_DIR[corpus]}/noisy/{cond}/{name}")
        (missing if mine is None else same if mine == ref else differ)[key] += 1
    for key in sorted(same.keys() | differ.keys() | missing.keys()):
        built = same[key] + differ[key]
        print(f"{'/'.join(key):28s} {same[key]:5d} of {built:5d} identical, {missing[key]:5d} not built")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
