#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""Recompute the per-word claims in the Results section.

Most numbers in the paper come straight out of ``summary/``. Five do not. They
partition WORDS by what the recogniser did to them -- kept, substituted,
dropped, invented -- and nothing pooled per cell can answer that, so they were
computed once by hand and had no way to be rechecked. This script is that way.

It reads the same hypotheses the scorer reads, aligns each system's words to the
gold words with the scorer's own Needleman-Wunsch, and prints every quoted
figure beside the sentence it appears in.

    analyze_recognition_effects.py                       # buckeye dev clean
    analyze_recognition_effects.py --corpus timit --subset core_test

Definitions, so the numbers mean one thing:

* a hypothesis word is CORRECT when the alignment pairs it with a gold word of
  the same label, SUBSTITUTED when it is paired with a different label, and
  INSERTED when it is paired with nothing. A gold word paired with nothing is
  DELETED.
* "within 20 ms" for a paired word is measured against ITS OWN gold partner,
  both edges counted separately. An inserted word has no partner, so it is
  measured against the nearest gold boundary anywhere in the utterance, which
  is the most generous reading and still the one the paper quotes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fabench.config import load_config
from fabench.paths import hyp_path
from fabench.score.matched import nw_align

TOL = 0.020

#: The recognisers whose transcripts Track 2 rows are built on. Two-step rows
#: name theirs in the recipe; one-step rows are their own recogniser.
RECOGNIZERS = ["qwen3_asr", "parakeet_tdt", "whisper3", "crisperwhisper",
               "torchaudio_asr", "whisperx_asr"]


def load_words(path: Path) -> dict[str, list]:
    """utt_id -> [(label, start, end)], from a hyp.jsonl."""
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        uid = r.get("utt_id") or str(r.get("item_id", "")).split("__")[0]
        out[uid] = [(w["label"], float(w["start"]), float(w["end"]))
                    for w in (r.get("words") or [])]
    return out


def classify(gold: list, hyp: list):
    """(correct, substituted, inserted, deleted) index pairs for one utterance."""
    gl = [w[0] for w in gold]
    hl = [w[0] for w in hyp]
    cor, sub, ins, dele = [], [], [], []
    for gi, hj in nw_align(gl, hl).pairs:
        if gi is not None and hj is not None:
            (cor if gl[gi] == hl[hj] else sub).append((gi, hj))
        elif hj is not None:
            ins.append(hj)
        else:
            dele.append(gi)
    return cor, sub, ins, dele


def within(gold_w, hyp_w) -> list[bool]:
    return [abs(hyp_w[1] - gold_w[1]) <= TOL, abs(hyp_w[2] - gold_w[2]) <= TOL]


def near_any(bnds: np.ndarray, t: float) -> bool:
    return bool(bnds.size) and bool(np.min(np.abs(bnds - t)) <= TOL)


def pct(hits: list[bool]) -> float:
    return 100.0 * sum(hits) / len(hits) if hits else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default="buckeye")
    ap.add_argument("--subset", default="dev")
    ap.add_argument("--condition", default="origin")
    ap.add_argument("--aligner", default="olign",
                    help="the Track 1 aligner whose timing is analysed")
    ap.add_argument("--cascade", default="olign_on_qwen3asr")
    ap.add_argument("--asr", default="qwen3_asr")
    a = ap.parse_args(argv)

    cell = ROOT / f"evals/aligners/{a.aligner}/en/{a.corpus}/{a.subset}/{a.condition}/config.yaml"
    if not cell.is_file():
        print(f"no cell config at {cell}", file=sys.stderr)
        return 2
    cfg = load_config(str(cell))

    from fabench.dataprep.datasets import ingest_corpus
    gold = {u.utt_id: [(w.label, w.start, w.end) for w in u.words]
            for u in ingest_corpus(a.corpus, cfg)}

    def hyp_of(tool: str) -> dict[str, list]:
        p = hyp_path(ROOT, tool, a.corpus, a.subset, condition=a.condition)
        return load_words(p) if p.exists() else {}

    t1 = hyp_of(a.aligner)
    casc = hyp_of(a.cascade)
    cell_name = f"{a.corpus}/{a.subset}/{a.condition}"
    print(f"cell {cell_name}   gold utts {len(gold)}   "
          f"{a.aligner} {len(t1)}   {a.cascade} {len(casc)}\n")

    # ---- claim 1 and 2: how the cascade times each class of word ----
    cw, sw, iw = [], [], []
    for uid, g in gold.items():
        h = casc.get(uid)
        if not h or not g:
            continue
        cor, sub, ins, _ = classify(g, h)
        gb = np.array([x for w in g for x in (w[1], w[2])])
        for gi, hj in cor:
            cw += within(g[gi], h[hj])
        for gi, hj in sub:
            sw += within(g[gi], h[hj])
        for hj in ins:
            iw += [near_any(gb, h[hj][1]), near_any(gb, h[hj][2])]
    print(f"[1] {a.cascade}, share of word boundaries inside {TOL*1000:.0f} ms")
    print(f"      correctly recognised  {pct(cw):5.1f}%   (n={len(cw)})")
    print(f"      substituted           {pct(sw):5.1f}%   (n={len(sw)})")
    print(f"[2]   inserted, vs nearest  {pct(iw):5.1f}%   (n={len(iw)})\n")

    # ---- claim 3 and 4: Track 1 error on words the recogniser lost ----
    # Two readings of "a word the recogniser missed", because the paper does
    # not say which one it used. `not-correct` counts a substituted word as
    # missed, since the reference word is indeed not in the transcript;
    # `deleted` counts only the words that produced nothing at all.
    print(f"[3,4] {a.aligner} on the reference transcript, MAE by whether the "
          f"recogniser got the word")
    for lost_is in ("not-correct", "deleted"):
        print(f"      lost = {lost_is}")
        print(f"      {'recogniser':<18}{'kept':>9}{'lost':>9}{'ratio':>8}"
              f"{'lost%':>8}{'understate':>12}")
        for asr in RECOGNIZERS:
            ah = hyp_of(asr)
            if not ah:
                continue
            kept, lost = [], []
            for uid, g in gold.items():
                h1, ha = t1.get(uid), ah.get(uid)
                if not h1 or ha is None or not g:
                    continue
                cor, sub, _, dele = classify(g, ha)
                if lost_is == "deleted":
                    missed = set(dele)
                else:
                    missed = set(dele) | {gi for gi, _ in sub}
                c1, _, _, _ = classify(g, h1)
                for gi, hj in c1:
                    e = [abs(h1[hj][1] - g[gi][1]), abs(h1[hj][2] - g[gi][2])]
                    (lost if gi in missed else kept).extend(e)
            if not kept or not lost:
                continue
            mk, ml = np.mean(kept) * 1000, np.mean(lost) * 1000
            allm = np.mean(kept + lost) * 1000
            print(f"      {asr:<18}{mk:8.1f} {ml:8.1f} {ml/mk:8.2f}"
                  f"{100*len(lost)/(len(kept)+len(lost)):7.1f}%"
                  f"{100*(allm/mk - 1):11.1f}%")

    # ---- claim 5: how many reference boundaries each track can even see ----
    print(f"\n[5] reference boundaries {a.aligner} accounts for")
    n_gold = sum(2 * len(g) for g in gold.values())
    for tool, src in ((a.aligner, "reference transcript"),
                      (a.cascade, f"{a.asr} transcript")):
        h = hyp_of(tool)
        n = 0
        for uid, g in gold.items():
            hh = h.get(uid)
            if not hh or not g:
                continue
            cor, _, _, _ = classify(g, hh)
            n += 2 * len(cor)
        print(f"      {src:<24}{100.0 * n / n_gold:5.1f}%  ({n}/{n_gold})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
