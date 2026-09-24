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
"""Boundary scores by how many of a boundary's neighbours are mismatched,
word and phone tiers, for the paper's rows on the two clean test cells.

The groups are fixed by the word alignment of the transcript each system
was given, with the utterance edges in, and within a group the boundaries
are paired by time for F1. MAE is the paper's dual-edge error over the
aligned units, substitutions included so that every group has one, each
edge charged to the reference boundary it sits on."""
import importlib.util, json, glob, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fabench.schema import Interval
from fabench.score import segmentation as seg
from fabench.score.matched import nw_align
from fabench.score.core import _SILENCE_WORDS, _prep_phones
from fabench.normalize import make_canon
from fabench.aligners.relabel import relabel_to_input
spec = importlib.util.spec_from_file_location('g', 'evals/gen_paper_tables.py'); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
m = g.load_tables_module(); g._SHORT_NAMES = True
TOL = 0.020; T = 20
CELLS = (("timit", "core_test", "TIMIT test"), ("buckeye", "test", "Buckeye test"))
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("docs/paper")

def load_gold(corpus, subset):
    f = sorted(glob.glob(f"data/work/canonical/{corpus}__*{subset}*.jsonl"))[0]
    out = {}
    for line in open(f):
        r = json.loads(line)
        out[r["utt_id"]] = ([Interval(w["label"].lower(), w["start"], w["end"]) for w in r["words"]],
                            [Interval(p["label"], p["start"], p["end"]) for p in r.get("phones", [])])
    return out

def load_hyp(path):
    out = {}
    for line in open(path):
        r = json.loads(line)
        def ivs(key, lower):
            L = []
            for w in r.get(key) or []:
                lab, s, e = (w["label"], w["start"], w["end"]) if isinstance(w, dict) else (w[0], w[1], w[2])
                if s is None or e is None: continue
                L.append(Interval(str(lab).lower() if lower else str(lab), float(s), float(e)))
            return L
        # A recipe that runs mode A for words and mode B for phones writes two
        # records per utterance; keep the words of one and the phones of the
        # other rather than letting the second overwrite the first.
        w, ph = ivs("words", True), ivs("phones", False)
        prev = out.get(r["utt_id"])
        if prev is not None:
            w = w or prev[0]; ph = ph or prev[1]
            src = r.get("source", prev[2]) if ph is not prev[1] else prev[2]
        else:
            src = r.get("source", "arpabet")
        out[r["utt_id"]] = (w, ph, src)
    return out

def score(gold, hyp, tier, gold_canon, input_words=None):
    """Per-group precision, recall and F1 over one cell.

    The groups come from the WORD alignment on both tiers. `input_words` is
    the transcript the system was handed, per utterance: True for the
    reference words on Track 1, the recognizer's words for a cascade, None
    for a one-step system. The REFERENCE side is grouped by aligning that
    input to the reference, so every system on one transcript has identical
    reference groups by construction. The system's own words are relabelled
    onto the input, as the scorer does, and group its boundaries. An
    utterance the system returned nothing for keeps its reference groups and
    counts as all misses."""
    groups = ("both", "one", "none")
    cats = ("all", "pool") + groups
    agg = {c: {"n_gold": 0, "n_hyp": 0, "hits": 0, "mae_n": 0, "mae_sum": 0.0} for c in cats}
    for uid, (gw, gp) in gold.items():
        G = [w for w in gw if w.label not in _SILENCE_WORDS]
        if not G: continue
        gl = [w.label for w in G]
        rec = hyp.get(uid)
        hw, hp, src = rec if rec is not None else ([], [], "arpabet")
        toks = None
        if input_words is True:
            toks = gl
        elif isinstance(input_words, dict):
            toks = input_words.get(uid)
        if toks is not None and hw:
            hw = relabel_to_input(toks, hw)
        H = [w for w in hw if w.label not in _SILENCE_WORDS]
        hl = [w.label for w in H]
        # reference groups from the INPUT when there is one, else from the output
        if toks is not None:
            gold_matched = {gi for gi, _ in nw_align(gl, toks).matched(gl, toks)}
        else:
            gold_matched = None
        waln = nw_align(gl, hl) if hl else None
        matched = waln.matched(gl, hl) if waln else []
        mr = None
        if tier == "word":
            if H:
                r = seg.f1_by_word_context(G, H, matched, tols_s=(TOL,), gold_matched=gold_matched)
                mr = seg.mae_by_word_context(G, H, matched, waln.aligned(), gold_matched=gold_matched)
                gold_only = False
            else:
                r = seg.f1_by_word_context(G, [], [], tols_s=(TOL,), gold_matched=gold_matched)
                gold_only = True
        else:
            if not gp: continue
            GP, gpl = _prep_phones(gp, gold_canon)
            if not GP: continue
            HP, hpl = _prep_phones(hp, make_canon(src)) if hp else ([], [])
            if HP:
                # a phone-only system has no words; its phones are grouped by
                # the words it was given, which is what it timed
                Hg = H if H else [Interval(t, 0.0, 0.0) for t in (toks or [])]
                if not H and toks is not None:
                    # give the input words the reference times so phones can
                    # be placed inside them
                    Hg = [Interval(t, w.start, w.end) for t, w in zip(toks, G)] if len(toks) == len(G) else G
                    matched = [(i, i) for i in range(len(G))]
                r = seg.f1_by_word_context(G, Hg, matched, GP, HP, tols_s=(TOL,), gold_matched=gold_matched)
                mr = seg.mae_by_word_context(G, Hg, matched, nw_align(gpl, hpl).aligned(), GP, HP, gold_matched=gold_matched)
                gold_only = False
            else:
                r = seg.f1_by_word_context(G, [], [], GP, [], tols_s=(TOL,), gold_matched=gold_matched)
                gold_only = True
        for c in cats:
            agg[c]["n_gold"] += r[c]["n_gold"]
            if not gold_only:
                agg[c]["n_hyp"] += r[c]["n_hyp"]; agg[c]["hits"] += r[c]["hits"][T]
            if mr is None:
                continue
            # the pooled MAE is over the same edges as the three groups, so it
            # is their weighted mean and needs no pairing of its own
            src = mr[c] if c in mr else {"n": sum(mr[k]["n"] for k in groups),
                                         "sum_abs": sum(mr[k]["sum_abs"] for k in groups)}  # all and pool
            agg[c]["mae_n"] += src["n"]; agg[c]["mae_sum"] += src["sum_abs"]
    tot = sum(agg[c]["n_gold"] for c in groups)
    if tot == 0: return None
    out = {}
    for c in cats:
        a = agg[c]; d = a["n_gold"] + a["n_hyp"]
        out[c] = (2 * a["hits"] / d) if d else float("nan")
        out[c + "_p"] = (a["hits"] / a["n_hyp"]) if a["n_hyp"] else float("nan")
        out[c + "_r"] = (a["hits"] / a["n_gold"]) if a["n_gold"] else float("nan")
        out[c + "_pct"] = 100 * a["n_gold"] / tot
        out[c + "_n"] = a["n_gold"]; out[c + "_nh"] = a["n_hyp"]; out[c + "_hits"] = a["hits"]
        out[c + "_mae"] = (1000 * a["mae_sum"] / a["mae_n"]) if a["mae_n"] else float("nan")
        out[c + "_mae_n"] = a["mae_n"]
    return out


def input_words_for(tool, track, corpus, subset):
    """The transcript the row was handed, per utterance, or None for a
    one-step recognizer. Track 1 rows are given the reference, which the
    caller signals with True."""
    if track == "Track 1":
        return True
    parts = m.cascade_parts(tool)
    if not parts:
        return None
    rec = parts[1]
    d = g.recipe_dirs().get(rec)
    if d is None:
        return None
    hp = d / "en" / corpus / subset / "origin" / "hyp.jsonl"
    if not hp.is_file():
        return None
    return {uid: [w.label for w in ws] for uid, (ws, _, _) in load_hyp(hp).items()}


def rows_for(tier):
    if tier == "word":
        a, t = g.collect("aligners", "wbe_ms"), g.collect("timestamp_asrs", "wbe_ms")
    else:
        a, t = g.collect("aligners", "mae_ms"), g.collect("timestamp_asrs", "mae_ms")
    r1 = g.order(m, sorted(set(a) - m.SUPPRESS_PUBLIC - g.PAPER_SUPPRESS), a)
    r2 = g.order(m, sorted(set(t) - m.SUPPRESS_PUBLIC - g.PAPER_SUPPRESS), t)
    return [("Track 1", r1), ("Track 2", r2)]

golds = {(c, s): load_gold(c, s) for c, s, _ in CELLS}
tex_all = []
fmt = lambda v: "   --" if v != v else f"{v:5.2f}"
fmt_t = lambda v: "--" if v != v else f"{v:.2f}"
fmt_m = lambda v: "    --" if v != v else f"{v:6.1f}"
fmt_mt = lambda v: "--" if v != v else f"{v:.1f}"
F1CAT = ("all", "pool", "both", "one", "none")
CAT = ("all", "both", "one", "none")
NC = len(F1CAT) + 2 * len(CAT)  # F1, then MAE and reference n without the pool
for tier in ("word", "phone"):
    print(f"\n=== {tier} tier at 20 ms.  Groups fixed by the word alignment: both / one / none of a boundary's two sides is a matched word, edges included, silence matching silence.  F1 per group, MAE in ms per group over the edges of the aligned units, then the number of reference boundaries in each group")
    print(f"{'system':22s}" + "".join(f" | {lab:>6s} F1   all  pool  both   one  none |  MAE    all   both    one   none |  gold    all   both   one  none" for _, _, lab in CELLS))
    L = [r"\begin{table}[htbp]\centering\scriptsize\setlength{\tabcolsep}{2.5pt}",
         r"\caption{Boundary $F_1$ at 20\,ms on the " + tier + r" tier in three groups fixed by the word alignment. The recognized words are aligned "
         r"to the reference words, a word is matched when it is label-matched to an aligned word on the other side, and every boundary takes the group of "
         r"its two neighbouring words, both matched, one or none. The utterance edges are boundaries against silence, which matches silence, so an edge is "
         r"classed by its one word. On the phone tier a phone boundary takes the group of the word that contains it. Reference boundaries are grouped by "
         r"the reference words and recognized boundaries by the recognized words, so systems on the same transcript share the reference groups. Every group "
         r"reports the plain boundary $F_1$, its reference and recognized times paired one-to-one within the tolerance, closest first. The labels are spent "
         r"on the grouping, every boundary in a group standing on the same two kinds of neighbour, so the hit rule has none left to check. The \emph{all} "
         r"column is the bottom line over the whole utterance. Every boundary is in its denominator, the edges included, and only a boundary with a matched "
         r"word on each side can score, an edge counting as matched when its one word is, so a boundary missed for misreading the words costs the same as one "
         r"put in the wrong place. The \emph{pool} column drops the label condition rather than the grouping and pairs any boundary against any other within "
         r"the tolerance, which is the ceiling the three groups sit under and is not their average. "
         r"MAE is in ms over the onset and the offset of every aligned unit, matched or substituted, "
         r"each edge charged to the reference boundary it sits on, so a unit the system named wrongly is still measured where it was put, and a deleted unit "
         r"contributes nothing, as in the paper's MAE. The right-hand columns are the number of reference boundaries in each group.}",
         r"\begin{tabular}{@{}l" + "r" * NC * len(CELLS) + "@{}}", r"\toprule",
         " & " + " & ".join(r"\multicolumn{" + str(NC) + "}{c}{" + lab + "}" for _, _, lab in CELLS) + r"\\",
         "".join(r"\cmidrule(lr){" + f"{2+NC*i}-{1+NC*(i+1)}" + "}" for i in range(len(CELLS))),
         " & " + " & ".join(r"\multicolumn{5}{c}{$F_1$ by matched sides} & \multicolumn{4}{c}{MAE (ms)} & \multicolumn{4}{c}{reference boundaries}" for _ in CELLS) + r"\\",
         "".join(r"\cmidrule(lr){" + f"{2+NC*i}-{6+NC*i}" + r"}\cmidrule(lr){" + f"{7+NC*i}-{10+NC*i}" + r"}\cmidrule(lr){" + f"{11+NC*i}-{14+NC*i}" + "}" for i in range(len(CELLS))),
         "System & " + " & ".join(" & ".join(F1CAT + CAT + CAT) for _ in CELLS) + r"\\", r"\midrule"]
    for track, rows in rows_for(tier):
        print(f"--- {track}")
        L.append(r"\multicolumn{" + str(1 + NC * len(CELLS)) + r"}{l}{\emph{" + track + r"}}\\")
        for r in rows:
            t = r[3]; d = g.recipe_dirs().get(t)
            if d is None: continue
            name = g.disp_paper(m, t).replace(" → ", "→"); cells = []
            for c, sub, _ in CELLS:
                hp = d / "en" / c / sub / "origin" / "hyp.jsonl"
                iw = input_words_for(t, track, c, sub)
                cells.append(score(golds[(c, sub)], load_hyp(hp), tier, make_canon(c), input_words=iw) if hp.is_file() else None)
            if all(x is None for x in cells): continue
            line = f"{name:22s}"; tex = name.replace("→", r"$\to$")
            for x in cells:
                if x is None:
                    line += " | " + " " * 9 + "   --    --    --    --    -- |     --     --     --     -- |        --    --    --    --"
                    tex += " & --" * NC; continue
                line += (f" | {'':9s}" + " ".join(fmt(x[c]) for c in F1CAT)
                         + " |" + " ".join(fmt_m(x[c + '_mae']) for c in CAT)
                         + f" | {x['all_n']:9d} {x['both_n']:5d} {x['one_n']:5d} {x['none_n']:5d}")
                tex += ("".join(f" & {fmt_t(x[c])}" for c in F1CAT)
                        + "".join(f" & {fmt_mt(x[c + '_mae'])}" for c in CAT)
                        + "".join(f" & {x[c + '_n']:,}" for c in CAT))
            print(line); L.append(tex + r"\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\label{tab:class-" + tier + "}", r"\end{table}"]
    (OUT / f"{tier}_class_table.tex").write_text("\n".join(L) + "\n"); tex_all.append("\n".join(L))
(OUT / "class_tables.tex").write_text(r"""\documentclass[10pt]{article}\usepackage[margin=1cm,landscape]{geometry}\usepackage{booktabs,times}
\begin{document}
""" + "\n\n".join(tex_all) + "\n\\end{document}\n")
print("\nwrote", OUT / "class_tables.tex")
