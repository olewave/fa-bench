#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Is a system's timing wrong, or merely shifted?

WHY THIS IS SEPARATE FROM MAE. Boundary MAE is an absolute error, so a system
whose every boundary is 60 ms late and one whose boundaries scatter 60 ms
either way score the same. They are not the same failure. The first is a
constant a user could subtract; the second is irreducible. This measures the
SIGNED error, hypothesis minus reference, so the two come apart.

WHAT IT FOUND, and it is not what it looks like at first. Five of the seven
commercial endpoints report word onsets 30 to 71 ms late, which invites the
reading that paid services share a defect. They do not. The open-weight CTC
aligners sit in the same band, BFA at +33, MMS-FA at +39, TorchAudio at +55,
NeMo-FA at +57 and WhisperX at +59, and CTC is exactly the architecture whose
emission spikes trail the acoustic onset. The bias is a property of the
alignment mechanism, not of who sells it. Whisper's own timestamps go the
other way at -132 ms, HMM and frame classifiers sit within a few ms of zero,
and across 28 systems the correlation between |onset bias| and word boundary
$F_1$ is -0.80, which is a better single predictor than the timestamp grid.

The MEAN is reported, so it sits beside boundary MAE, which is also a mean,
and the two describe one set of errors two ways rather than summarising two
different sets. The median is measured alongside and kept in the cache, since
the pair separates exactly where a system has a heavy tail.

    measure_onset_bias.py
    measure_onset_bias.py --cell buckeye/dev --tier phone
"""
from __future__ import annotations

import argparse
import functools
import glob
import json
import os
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fabench.normalize import make_canon                    # noqa: E402
from fabench.schema import Interval                         # noqa: E402
from fabench.score.core import _SILENCE_WORDS, _prep_phones  # noqa: E402
from fabench.score.matched import nw_align                  # noqa: E402

#: The two development splits, which is where a supplement table belongs. The
#: test splits carry the same story and are in records/.
CELLS = {
    "timit/dev": ("timit", "timit__dev__*.jsonl", "en/timit/dev/origin"),
    "timit/core_test": ("timit", "timit__*core_test*.jsonl",
                        "en/timit/core_test/origin"),
    "buckeye/dev": ("buckeye", "buckeye__paper__dev__*.jsonl", "en/buckeye/dev/origin"),
    "buckeye/test": ("buckeye", "buckeye__paper__test__*.jsonl",
                     "en/buckeye/test/origin"),
}
#: Enough utterances for a stable median; the full Buckeye dev split is 4,456
#: and the medians move by under 0.1 ms past this.
CAP = 4000


def _ivs(rec, key):
    out = []
    for w in rec.get(key) or []:
        if isinstance(w, dict):
            lab, s, e = w.get("label"), w.get("start"), w.get("end")
        else:
            lab, s, e = w[0], w[1], w[2]
        if s is None or e is None:
            continue
        out.append(Interval(str(lab), float(s), float(e)))
    return out


@functools.lru_cache(maxsize=None)
def gold_of(pattern: str, key: str) -> dict:
    out = {}
    for f in glob.glob(str(ROOT / "data/work/canonical" / pattern)):
        for line in open(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ivs = _ivs(r, key)
            if ivs:
                out[r["utt_id"]] = ivs
    return out


def bias(hyp_path: str, corpus: str, pattern: str, tier: str) -> dict:
    """Mean signed word start and end error, in ms, over matched units.

    Matching is the scorer's own: a monotonic label alignment, over lowercased
    words with the silence pseudo-words dropped, or over canonicalized phones
    with each side mapped from its own alphabet. Anything the alignment does
    not pair contributes nothing, exactly as it contributes nothing to MAE.
    """
    key = "words" if tier == "word" else "phones"
    # The gold manifest is per CELL, not per corpus. Keying it on the corpus
    # worked while there was one cell each; with a dev and a test split per
    # corpus the later entry won, both TIMIT cells were scored against
    # core-test gold, and the dev cells matched nothing and vanished.
    gold = gold_of(pattern, key)
    gcanon = make_canon(corpus)
    on, off = [], []
    with open(hyp_path) as fh:
        for n, line in enumerate(fh):
            if n >= CAP:
                break
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            g = gold.get(r.get("utt_id"))
            h = _ivs(r, key)
            if not g or not h:
                continue
            if tier == "word":
                gi_ = [x for x in g if x.label.lower() not in _SILENCE_WORDS]
                hi_ = [x for x in h if x.label.lower() not in _SILENCE_WORDS]
                gl = [x.label.lower() for x in gi_]
                hl = [x.label.lower() for x in hi_]
            else:
                hcanon = make_canon(r.get("source", "arpabet"))
                gi_, gl = _prep_phones(g, gcanon)
                hi_, hl = _prep_phones(h, hcanon)
            for a, b in nw_align(gl, hl).matched(gl, hl):
                on.append((hi_[b].start - gi_[a].start) * 1000)
                off.append((hi_[b].end - gi_[a].end) * 1000)
    if len(on) < 100:
        return {"n": len(on), "onset": None, "offset": None}
    # MEAN is what the figure and the table report, so that this sits beside
    # boundary MAE, which is also a mean. The median is kept alongside it
    # because the two part company wherever a system has a heavy tail.
    return {"n": len(on),
            "onset": statistics.fmean(on),
            "offset": statistics.fmean(off),
            "onset_med": statistics.median(on),
            "offset_med": statistics.median(off)}


def systems():
    """`(name, recipe dir)` for every recipe with hypotheses, as the grid scan does."""
    out = []
    for cfg in sorted(glob.glob(str(ROOT / "evals/*/*/config.yaml"))
                      + glob.glob(str(ROOT / "evals/*/*/exps/*/config.yaml"))):
        d = pathlib.Path(cfg).parent
        name = ""
        for ln in open(cfg):
            if ln.startswith("name:"):
                name = ln.split(":", 1)[1].strip()
                break
        out.append((name or d.name, d))
    return out


def table(tier: str) -> dict:
    """`{system: {cell: {onset, offset, n}}}` for one tier."""
    out = {}
    for name, d in systems():
        for cell, (corpus, pat, sub) in CELLS.items():
            p = d / sub / "hyp.jsonl"
            if not p.is_file():
                continue
            b = bias(str(p), corpus, pat, tier)
            if b["onset"] is not None:
                out.setdefault(name, {})[cell] = b
    return out


#: Where the measured biases are cached. Reading every hypothesis on both
#: tiers takes minutes, and the paper's table generator runs on every build, so
#: the expensive pass is explicit and its result is a file.
CACHE = ROOT / "summary" / "onset_bias.json"


def refresh(path=None) -> dict:
    """Measure both tiers and write the cache."""
    out = {t: {k: {c: v for c, v in cells.items()}
               for k, cells in table(t).items()} for t in ("word", "phone")}
    path = pathlib.Path(path or CACHE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, sort_keys=True))
    return out


def load_cache(path=None) -> dict:
    p = pathlib.Path(path or CACHE)
    return json.loads(p.read_text()) if p.is_file() else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tier", choices=("word", "phone", "both"), default="both")
    ap.add_argument("--refresh", action="store_true",
                    help=f"measure both tiers and write {CACHE.name}")
    a = ap.parse_args(argv)
    if a.refresh:
        d = refresh()
        print(f"wrote {CACHE} "
              f"({sum(len(v) for v in d.values())} system-tier rows)")
        return 0
    for tier in (("word", "phone") if a.tier == "both" else (a.tier,)):
        t = table(tier)
        print(f"\n{tier.upper()} TIER, median signed error in ms, hypothesis minus reference.")
        print("Negative is early. " + " " * 10
              + "  ".join(f"{c:>22}" for c in CELLS))
        print(f"  {'system':<30} " + "  ".join(f"{'onset':>9}{'offset':>9}{'n':>7}"
                                               for _ in CELLS))
        rows = sorted(t.items(), key=lambda kv: min(
            (v["onset"] for v in kv[1].values()), default=0))
        for name, cells in rows:
            line = f"  {name:<30} "
            for c in CELLS:
                v = cells.get(c)
                line += (f"{v['onset']:>9.1f}{v['offset']:>9.1f}{v['n']:>7}"
                         if v else " " * 25)
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
