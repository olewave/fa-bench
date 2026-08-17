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

"""Fill the generated table blocks across the summary/ pages.

WHY ONLY THE BLOCKS. That file is 228 lines, of which ~165 are hand-written
analysis -- the two-metrics explanation, the Sub/Del/Ins section, aligner
provenance, reproduction steps. Only the ~63 table rows go stale. Generating
the whole file would put that prose inside Python strings and silently destroy
any hand edit on the next run, so this rewrites ONLY what sits between

    <!-- BEGIN GENERATED: <id> -->
    <!-- END GENERATED: <id> -->

and leaves every other line untouched.

Numbers come from the per-cell summary/en/<corpus>/<subset>/report.md, the same
source as evals/report_parse.py -- never recomputed here, so this cannot
become a second, disagreeing implementation of the metrics.

RUN rescore_all.sh FIRST. The sweep runs one fabench invocation per (cell,
tool), and each rewrites that cell's report.md with only its own row, so
straight after a sweep the reports show whichever tool ran last. rescore
reassembles them from the surviving hyp files. Skipping that step produces a
patchwork table that looks complete.

Usage:  update_public_tables.py [--root DIR] [--check]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.report_parse import _mae_or_inf, collect, subsets_of

BEGIN = "<!-- BEGIN GENERATED: {} -->"
END = "<!-- END GENERATED: {} -->"

#: Systems whose rows carry a caveat marker in the published table.
#:
#: MAPS only. Its models are `timbuck` = TIMIT + Buckeye with no split
#: discipline, so its evaluation data IS its training data and the row cannot be
#: read as a held-out result -- the one case here where the number does not mean
#: what the column header says.
#:
#: olign carried a marker while its row was described as trained on these
#: corpora's train splits. It is not overlap: the splits it is scored on are
#: speaker-disjoint from anything it saw, which is the same standard every other
#: row meets. Flagging it alongside MAPS put two different situations under one
#: symbol.
FLAGGED = {"maps": "⚠"}

#: What each flag means, appended under any generated table that carries it.
#: The marker used to be explained only on the methodology page, so a reader on
#: a corpus page met a bare warning glyph in thirteen cells with nothing to say
#: what it warned about. Emitted with the table rather than written into the
#: page, so the note cannot outlive -- or go missing from -- the flag itself.
FLAG_NOTE = {
    "⚠": "⚠ **MAPS** was trained on TIMIT and Buckeye, so it is scored on its "
         "own training data. Its row is not a held-out result — see "
         "[training data and overlap](../README.md#training-data-and-overlap).",
}

#: Systems published under a vendor's name, and the one variant that is.
#:
#: A closed system may be entered here as ONE row -- the shipped configuration --
#: and its internal variants are not published: their names encode the tunable
#: axes of a system whose design is not disclosed, and a leaderboard beside them
#: would say which setting won. The benchmark's public value is the cross-SYSTEM
#: comparison, not a vendor's parameter sweep.
#:
#: Expressed as a RULE rather than a list, so this file does not itself publish
#: the names it exists to withhold. Anything matching a prefix is suppressed
#: unless it is the declared shipped row.
SUPPRESS_PREFIX = {"olign"}
SUPPRESS_KEEP = {"olign_noisy"}


def _suppressed(name: str) -> bool:
    """Held back from the public tables? See SUPPRESS_PREFIX."""
    return any(name == p or name.startswith(p + "_") for p in SUPPRESS_PREFIX) \
        and name not in SUPPRESS_KEEP


class _SuppressSet:
    """Set-like, so `name in SUPPRESS_PUBLIC` still reads naturally."""

    def __contains__(self, name: object) -> bool:
        return _suppressed(str(name))

    def __iter__(self):                 # nothing to enumerate: it is a rule
        return iter(())

    def __rsub__(self, other):
        """`{names} - SUPPRESS_PUBLIC` -- two callers filter a set this way."""
        return {n for n in other if not _suppressed(str(n))}


SUPPRESS_PUBLIC = _SuppressSet()

#: Hidden from the CONCISE phone table only -- still in the detailed view, the
#: word table, and leaderboard.csv. MFA 2.0 and MFA 3.4 are two releases of one
#: system, and the concise table exists to compare SYSTEMS; carrying both puts a
#: version ablation in the row that should be answering "how do the approaches
#: differ". The comparison is worth keeping -- 3.4 beats 2.0 by 4.6 ms on TIMIT
#: dev -- it just belongs where ablations live.
SUPPRESS_CONCISE = {"mfa2"}

#: Systems whose PHONE tier is withheld while their word tier still publishes.
#:
#: torchaudio_fa aligns its phone tier against wav2vec2-lv-60-espeak-cv-ft,
#: whose vocabulary is eSpeak IPA, while FA-Bench hands it the reference
#: sequence in ARPABET. The worker keeps only labels present in the model
#: vocabulary, so every ARPABET vowel is filtered out before alignment and what
#: survives is the accidental spelling overlap -- 17 consonants. Measured on
#: TIMIT dev it aligns 15.0 phones per utterance against a 38.3 gold and 32-35
#: for every other phone-tier system: 39% of the reference against their 84-91%.
#:
#: That is not a coarser inventory, it is the reference with the vowels deleted,
#: and consonant boundaries are acoustically sharper -- so the number flatters
#: it and is not comparable. Withheld until the ARPABET -> eSpeak mapping
#: exists. gate#10 fails any cell that reaches this state again.
#: Systems whose PHONE tier is withheld while their word tier still publishes.
#:
#: torchaudio_fa is handed the GOLD PHONE SEQUENCE. runner.py passes
#: `phone_seq = [p.label for p in gold.phones]` to every adapter, and its mode-B
#: worker aligns exactly those labels -- the only aligner here that does.
#: Charsiu, MFA, MAPS, BFA and Olign derive their own phone sequence from the
#: transcript by lexicon or G2P, so they can and do get phones wrong.
#:
#: The consequence is visible in the edit columns: torchaudio scores S=0.0 and
#: I=0.0 on Buckeye against S=14-17 and I=9-17 for everyone else, because it
#: structurally cannot substitute or insert -- it emits the labels it was given,
#: exactly len(phone_seq) of them. Its D=1.3 is only the silence and closures
#: that have no acoustic target. A PER of 1.3% beside everyone else's 25-35%
#: reads as a decisive win and is nothing of the kind.
#:
#: Two different tasks: place boundaries given the true phone sequence, versus
#: predict the phones and place them. MAE is affected too, since knowing the
#: sequence removes an error source before timing is measured. Withheld until
#: the adapter derives its own phones. The word tier is a separate code path and
#: is unaffected.
#: Intentionally empty. TorchAudio sat here while it was aligning against the
#: reference phone sequence, which made its S and I columns 0.0 by construction.
#: It now derives its own sequence by eSpeak G2P from the transcript, so the tier
#: is comparable and published. The mechanism stays for the next system that
#: needs it.
SUPPRESS_PHONE_TIER: set[str] = set()

#: The fields a phone table reads. Blanking these at load is what withholds one
#: TIER without touching the row's word columns -- every phone builder already
#: skips a row whose MAE does not parse, so none of them needs to know.
_PHONE_FIELDS = ("mae", "median", "signed", "arr", "ins", "n_bnd",
                 "sub_pct", "del_pct", "ins_pct", "per", "err_gt100_pct",
                 "bnd_p", "bnd_r", "bnd_f1", "os", "r_value",
                 "ta_10", "ta_25", "ta_50", "ta_100")


def drop_phone_tier(collected: dict) -> dict:
    """Blank the phone columns of any system in SUPPRESS_PHONE_TIER."""
    for corpus in collected.values():
        for rows in corpus.values():
            for r in rows:
                if r.get("aligner") in SUPPRESS_PHONE_TIER:
                    for f in _PHONE_FIELDS:
                        if f in r:
                            r[f] = "—"
    return collected

#: How each tool is written by its own authors. The tables use these rather
#: than the internal directory slug -- `whisperx` is WhisperX, `mfa` is MFA.
#:
#: No "-FA" suffixes: every system here is a forced aligner, so the suffix
#: carries no information.
#:
#: CrisperWhisper was the exception while the ASR (decoding its own transcript)
#: and the aligner (given the reference) could land in one table. They cannot
#: any more: these pages read summary/aligners/ only, and the ASR lives in
#: summary/timestamp_asrs/, so no block can contain both and the suffix has
#: nothing left to disambiguate from.
DISPLAY = {
    "bfa": "BFA",
    "charsiu": "Charsiu",
    "crisperwhisper": "CrisperWhisper",
    "crisperwhisper_fa": "CrisperWhisper",
    "maps": "MAPS",
    "mfa": "MFA 3.4",
    "mfa2": "MFA 2.0",
    "neufa": "NeuFA",
    # Only the shipped configuration is named. The internal variants are
    # withheld by SUPPRESS_PREFIX, and describing them here would disclose the
    # axes of a system whose design is not published -- which is the thing the
    # suppression exists to prevent.
    "olign": "Olign 1.0",
    "olign_b": "Olign 1.0",
    "olign_noisy": "Olign 1.0",
    "olign_t": "Olign 1.0",
    "parakeet_tdt": "Parakeet-TDT",
    "qwen3_fa": "Qwen3",
    "stable_ts": "stable-ts",
    "torchaudio_fa": "TorchAudio",
    "whisperx": "WhisperX",
}


#: Alignment-mechanism family. Classified by how the tool DECIDES BOUNDARIES,
#: not by its encoder -- WhisperX is Whisper (attention) for recognition but
#: aligns with a wav2vec2 CTC model, and FA-Bench measures alignment.
FAMILY = {
    "charsiu": "frame",         # wav2vec2 frame classifier + DP, 10 ms grid
    "maps": "frame",            # neural phone segmentor + interpolation
    "parakeet_tdt": "transducer",   # Token-and-Duration Transducer
    "crisperwhisper": "attention",  # Whisper encoder-decoder cross-attention
    "crisperwhisper_fa": "attention",
    "qwen3_fa": "attention",    # Qwen3 transformer
    "stable_ts": "attention",  # Whisper cross-attention + DTW
    "neufa": "attention",       # bidirectional attention (not evaluated)
    "bfa": "ctc",               # CUPE + CTC
    "torchaudio_fa": "ctc",     # CTC forced alignment
    "whisperx": "ctc",          # wav2vec2 phoneme CTC for the ALIGNMENT stage
    "mfa": "hmm",               # Kaldi GMM-HMM + SAT/fMLLR/LDA
    "mfa2": "hmm",
    "olign": "proprietary",
    "olign_noisy": "proprietary",
    "olign_t": "proprietary",
    "olign_b": "proprietary",
}

#: Presentation order. Within each family the MOST ACCURATE row sits LAST, so
#: the eye travels from weaker to stronger both within and across families.
FAMILY_ORDER = ["transducer", "ctc", "attention", "frame", "hmm", "proprietary"]
#: Displayed family names. Capitalised across the board -- "Frame" beside a
#: lowercase "transducer" reads as a typo, not a distinction.
#:
#: "proprietary" becomes "Closed", not "Prpri.". This column names an
#: ARCHITECTURE -- CTC, Frame, HMM, Attention, Transducer -- so answering it
#: with a licence was a category error as well as an awkward contraction. The
#: architecture is simply not public, and "Closed" says that in the same
#: register as its neighbours, at a width the column already carries.
FAMILY_LABEL = {"frame": "Frame", "transducer": "Transducer",
                "attention": "Attention", "ctc": "CTC", "hmm": "HMM",
                "proprietary": "Closed"}


def disp(tool: str) -> str:
    return DISPLAY.get(tool, tool)


def fam(tool: str) -> str:
    return FAMILY.get(tool, "other")


def fam_rank(tool: str) -> int:
    f = fam(tool)
    return FAMILY_ORDER.index(f) if f in FAMILY_ORDER else len(FAMILY_ORDER)


def group_key(tool: str, score):
    """(family order, worst-first within family).

    `score` is the cell's headline metric; None sorts to the top of its family
    because a tool with no number is not evidence of accuracy. Higher accuracy
    -- LOWER MAE -- ends up at the BOTTOM of each group.
    """
    if score is None:
        return (fam_rank(tool), -float("inf"), disp(tool).lower())
    return (fam_rank(tool), -float(score), disp(tool).lower())


def sort_key(tool: str) -> tuple:
    """Alphabetical by DISPLAY name, case-insensitive.

    Deliberately NOT by score. Ordering rows by MAE builds a leaderboard
    whether or not it is called one, and invites tuning against a rank rather
    than reading the decomposition -- which is where this benchmark's findings
    actually live (MAPS collapsing 10x under noise; CrisperWhisper's median
    being competitive while its mean was a failure-rate artefact; olign leading
    on placement while carrying the highest PER of the non-BFA systems).
    """
    return (disp(tool).lower(), tool)


def _fmt(v: str) -> str:
    return v if v not in ("", None) else "—"


def _esc(v: str) -> str:
    """Minimal HTML escape for the raw-<table> concise view."""
    return (str(v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _hdr(label: str) -> str:
    """Header label stacked onto two lines at its last space.

    "MAE (ms)" -> "MAE<br>(ms)", "95% CI" -> "95%<br>CI", "S/D/I (%)" ->
    "S/D/I<br>(%)". A single-word label is left alone. Stacking lets each
    column shrink to the width of its widest LINE rather than its whole
    caption, which is what let the twenty-column detailed view stop
    overflowing -- the unit was setting the width of a column holding
    four-character numbers.
    """
    s = _esc(label)
    i = s.rfind(" ")
    if i >= 0:
        return s[:i] + "<br>" + s[i + 1:]
    # No space: split before a trailing number if what precedes it is long
    # enough to stand alone ("TA@10ms" -> "TA@" / "10ms"). The length guard
    # keeps "F1" from becoming "F" over "1".
    m = re.search(r"\d", s)
    if m and m.start() >= 3:
        return s[:m.start()] + "<br>" + s[m.start():]
    return s


def _best(rows: list[dict], key: str, lower_is_better: bool) -> str | None:
    vals = []
    for r in rows:
        try:
            vals.append((float(str(r.get(key, "")).split(" [")[0].rstrip("%")), r))
        except (ValueError, AttributeError):
            continue
    if not vals:
        return None
    # key= is required: vals holds (float, dict) and Python falls through to
    # comparing the dicts on a tie, raising TypeError. Ties are common here --
    # several systems report the same rounded TA or B-F1.
    pick = (min(vals, key=lambda x: x[0]) if lower_is_better
            else max(vals, key=lambda x: x[0]))
    return pick[1]["aligner"]


#: Concise view. MAE is placement on the matched path; PER% is the price paid
#: for it (a system can lower MAE for free by skipping hard phones, and PER%
#: is where that shows); P/R/F1 are time-paired, label-agnostic boundary
#: detection at a 20 ms tolerance -- the only metrics a word-only or
#: self-transcribing system can have at all.
#:
#: P and R replace ARR here because they say WHICH WAY a system fails, which
#: ARR cannot: precision falls when it emits boundaries that are not there
#: (over-segmentation), recall falls when it misses real ones. F1 alone hides
#: that trade, and the two failure modes have opposite fixes.
#: No "B-" prefix: this is the PHONE table, so the tier is already in the
#: heading, and the word table beside it says "word MAE"/"word F1" rather than
#: carrying a "W-" either. The prefix is kept only in the full internal table
#: (fabench/report/tables.py), where phone and word P/R/F1 share ONE row and
#: bare names would genuinely collide.
#: Grouped so a hairline can fall between them: placement | edit accounting |
#: boundary detection. The three answer different questions and pair phones
#: differently -- MAE and the edit columns pair by LABEL, P/R/F1 pair by TIME --
#: so a reader scanning left to right should see where one stops and the next
#: begins. Components before the total within the middle group, matching the
#: detailed view's Sub | Del | Ins | PER.
#: The headline table: ONE number per pairing, plus the anti-gaming counterpart.
#:
#: S/D/I, Pre and Rec moved to Details. They decompose numbers that are already
#: here -- S/D/I is what PER is made of, Pre and Rec are what F1 is made of --
#: so carrying them on the comparison page spent six columns restating three,
#: and pushed the split-to-split comparison off the side of the page. The
#: decompositions are what Details exists for; nothing was dropped, only moved.
#:
#: PER stays beside MAE because it is the anti-gaming pair: MAE is computed on
#: the matched path, so a system that skips hard phones flatters it, and PER is
#: what charges for the skipping. F1 stays because it pairs by TIME rather than
#: label and is the one column here that a label-blind failure shows up in.
CONCISE_GROUPS = [
    [("MAE (ms)", lambda r: r["mae"].split(" [")[0])],
    [("PER (%)", lambda r: r.get("per"))],
    [("F1", lambda r: r.get("bnd_f1"))],
]
CONCISE_METRICS = [m for g in CONCISE_GROUPS for m in g]

#: Column indices (within one split) that START a group -- where a light rule
#: goes. Derived, so adding a metric to a group cannot desynchronise the rules.
CONCISE_GROUP_STARTS = set()
_acc = 0
for _g in CONCISE_GROUPS:
    CONCISE_GROUP_STARTS.add(_acc)
    _acc += len(_g)


#: Splits are named by their directory; `core_test` is displayed as `test`
#: because it IS TIMIT's standard test set -- the corpus's own 24-speaker
#: recommendation -- and the qualifier only matters beside `full_test`, which
#: appears in the detailed view where both are present.
#: Splits as they are written in headings. `core_test` keeps its own name
#: rather than being flattened to "test": TIMIT ships a 24-speaker core test
#: set AND a 168-speaker extension, and calling the core set "test" invites
#: reading it as the whole thing.
SUBSET_LABEL = {"dev": "Dev", "core_test": "Core-test", "test": "Test"}

#: Corpora as their own projects write them. Used in table TITLES -- a heading
#: survives being linked to, quoted, or screenshotted on its own, where the
#: page title that would otherwise supply the corpus does not travel with it.
CORPUS_LABEL = {"timit": "TIMIT", "buckeye": "Buckeye"}


def corpus_disp(c: str) -> str:
    return CORPUS_LABEL.get(c, c)

def sub_disp(s: str, corpus: str = "") -> str:
    """Split label, qualified by corpus where the corpus is not its own column.

    The spanning headers pass it: a reader comparing the two corpus pages side
    by side, or looking at one table lifted out of its page, otherwise has a
    bare "Dev" and no way to tell which corpus produced it. The pipe tables
    that already carry a `corpus` column pass nothing, so it is not repeated.
    """
    label = SUBSET_LABEL.get(s, s)
    return f"{corpus_disp(corpus)} {label}" if corpus else label

#: Detailed view: EVERY phone-level field the scorer emits, GROUPED under
#: spanning headers the same way the concise view groups by split. The groups
#: are the distinction this whole page turns on -- label-paired metrics pair
#: phones by identity and are blind to a system that skips hard phones;
#: time-paired ones pair by clock and are blind to labels. Twenty-two columns
#: in one undifferentiated run invites reading MAE and F1 as commensurable.
#:
#: Word Pre/Rec/F1 are the only omission and they have their own table.
DETAILED_GROUPS = [
    # x̃ is the median absolute error, δ̄ the MEAN SIGNED error (bias): x̃ says
    # how far off a typical boundary is, δ̄ says which DIRECTION the system
    # leans, early or late. A system can have a small x̃ and a large δ̄, or the
    # reverse, so the symbols keep both visible without two word-wide columns.
    #
    # WBE micro/macro are gone from here: this is the PHONE table, and the word
    # tier has its own with its own splits. TA@100 replaces the separate
    # >100 ms column -- they were exact complements (TA@100 = 100 - >100ms%),
    # so carrying both printed one number twice.
    ("Boundary error — label-paired", [
        ("MAE (ms)", lambda r: r["mae"].split(" [")[0]),
        ("95% CI", lambda r: f"[{r['mae'].split('[')[1].rstrip(']')}]"
         if "[" in r.get("mae", "") else ""),
        ("x̃ (ms)", lambda r: r.get("median")),
        ("δ̄ (ms)", lambda r: r.get("signed")),
        ("TA@10ms", lambda r: r.get("ta_10")),
        ("TA@50ms", lambda r: r.get("ta_50")),
        ("TA@100ms", lambda r: r.get("ta_100")),
    ]),
    # ARR is NOT a column: ARR = 100 - Sub% - Del% exactly (verified across
    # every row, max deviation 0.1 from rounding), so it is Del% restated.
    # corr(ARR, Del%) = -0.997 on the current results. Carrying both invites
    # reading two independent pieces of evidence where there is one.
    ("Edit accounting — label-paired", [
        ("Sub (%)", lambda r: r.get("sub_pct")),
        ("Del (%)", lambda r: r.get("del_pct")),
        ("Ins (%)", lambda r: r.get("ins_pct")),
        ("PER (%)", lambda r: r.get("per")),
    ]),
    # P and R share a cell, as they do in the by-condition grid below and in
    # the word tables. Which way a system is unbalanced is read from the pair,
    # and one page showing them merged and another split made that a comparison
    # between tables rather than within a cell.
    ("Boundary detection @20 ms — time-paired", [
        ("P/R", lambda r: f"{r.get('bnd_p')}/{r.get('bnd_r')}"
         if r.get("bnd_p") not in (None, "", "\u2014") else None),
        ("F1", lambda r: r.get("bnd_f1")),
    ]),
    # Separate group so a rule falls at F1 | OS. P/R/F1 say how ACCURATE the
    # detected boundaries are; OS and R-val say whether the system emitted the
    # right NUMBER of them. F1 scores over- and under-segmentation identically,
    # which is exactly what these two separate.
    ("Segmentation balance", [
        ("OS", lambda r: r.get("os")),
        ("R-val", lambda r: r.get("r_value")),
    ]),
]

#: The detailed view as THREE tables, one metric family each. Twenty-two
#: columns in one grid could only be read by scrolling sideways, and the
#: families answer different questions: where boundaries land, what left the
#: matched path, and whether the right NUMBER of boundaries was emitted.
#: Detection and segmentation balance share a table because they are read
#: together -- F1 scores over- and under-segmentation identically, and OS /
#: R-val are what separate them.
#: Same order as every other table on these pages: MAE, then P/R and F1, then
#: the rest. Edit accounting reads last because it explains WHY a boundary was
#: missed, which only matters once the reader knows one was.
DETAILED_TABLES = [
    ("Phone-level boundary error", DETAILED_GROUPS[0:1]),
    ("Boundary detection @20 ms · Segmentation balance", DETAILED_GROUPS[2:4]),
    ("Phone editing errors", DETAILED_GROUPS[1:2]),
]

#: Two rule weights, shared by every spanned table. Heavy separates SPLITS,
#: light separates metric groups within a split.
#: Tables carry their own bottom margin. A blank line in markdown SOURCE never
#: renders as vertical space -- it only separates blocks -- so the gap after a
#: table is whatever CSS the viewer applies to a raw <table>, which in several
#: previewers is nothing. The caption of the next grid then sits flush against
#: the rows above it. Stating the margin here makes the spacing the same
#: everywhere instead of a property of the reader's renderer.
TABLE_TAG = '<table style="margin-bottom:1.5rem">'
SPLIT_RULE = ' style="border-left:2px solid rgba(128,128,128,.55)"'
GROUP_RULE = ' style="border-left:1px solid rgba(128,128,128,.25)"'

# RTF and n_bnd are deliberately NOT here. They are not alignment quality --
# RTF is a property of the machine the sweep happened to run on, and n_bnd is
# a corpus size. Both stay in leaderboard.csv; neither belongs in a column a
# reader scans for accuracy. (Cost that DOES matter is in the aligner docs:
# CrisperWhisper is the only system slower than realtime, RTF 2.35 against
# 0.22 for the next slowest.)

#: flat view of the above, for anything that just wants the columns in order
DETAILED_METRICS = [mg for _, g in DETAILED_GROUPS for mg in g]


def _rows_of(bysub: dict[str, list[dict]], sub: str) -> list[dict]:
    """Rows for a phone table.

    A system whose phone tier is WITHHELD keeps its row, with every phone cell
    an em dash. Dropping it silently would read as "has no phone tier", which is
    what WhisperX and Qwen3 genuinely are; torchaudio has one and we are choosing
    not to publish it, and those are different statements.
    """
    return [r for r in bysub.get(sub, [])
            if (_mae_or_inf(r) != float("inf")
                or r["aligner"] in SUPPRESS_PHONE_TIER)
            and r["aligner"] not in SUPPRESS_PUBLIC]


# NO per-column bolding, in either view. Marking the winner is a leaderboard
# rendered as typography: a reader sees who "won" before reading a number, and
# the mark implies a real difference where there may be none -- olign and olign
# (noise-trained) differ by 0.1 ms on clean, inside run-to-run variation, yet
# only one would carry it. The lowest number in a column is still visible to
# anyone reading the column.


#: One line per abbreviation actually used in the detailed table, in column
#: order. Generated rather than written so a renamed or dropped column cannot
#: leave a definition behind describing something no longer there -- which is
#: how "Charsiu emits no word tier" survived in this repo for months.
CAPTION = [
    ("MAE", "mean absolute boundary error, on the matched path only"),
    ("P/R, F1", ("boundary detection at 20 ms, paired by TIME and ignoring "
                "labels — a substitution at the right time is free here")),
    ("OS", ("over-segmentation, n_hyp/n_gold − 1: positive means more boundaries "
           "proposed than exist")),
    ("R-val", ("R-value (Räsänen et al. 2009), which separates the over- from "
              "under-segmentation that F1 scores identically")),
    ("x̃", ("median absolute error — the typical boundary, unmoved by a few "
          "catastrophic ones")),
    ("δ̄", ("mean *signed* error: negative is early, positive late. Direction, "
          "where MAE and x̃ give only magnitude")),
    ("t=N", "share of boundaries within N ms"),
    ("95% CI", "bootstrap confidence interval over utterances"),
    ("S / D / I", ("substitutions, deletions, insertions: why a unit left the "
                  "matched path — relabelled, never emitted, or invented. "
                  "Normalised by gold count. Phones in the phone tables, words "
                  "in the track-2 one")),
    ("PER", "phone error rate, S + D + I"),
]


def caption() -> str:
    """The abbreviation key, as bolded term-definition lines."""
    return "\n".join(f"**{k}**: {v}." for k, v in CAPTION)


def phone_table_concise(corpus: str, bysub: dict[str, list[dict]]) -> str:
    """One row per SYSTEM, every split side by side.

    The long form repeated each system once per split, which buries the
    question a reader actually has -- does this system hold up from dev to
    test? Pivoting puts dev and test on the same line so that comparison is
    horizontal instead of forty rows apart.

    EMITTED AS HTML, not a pipe table, to get a LaTeX-style \\multicolumn
    header: one spanning cell per split above its five metrics, so "dev" and
    "test" are read once each rather than repeated into every column name.
    GitHub-flavoured Markdown has no colspan, but both MkDocs and GitHub
    render a raw <table>, so this degrades nowhere it is actually read.
    """
    def _conc(bysub, s):
        return [r for r in _rows_of(bysub, s)
                if r["aligner"] not in SUPPRESS_CONCISE]

    present = [s for s in subsets_of(bysub) if _conc(bysub, s)]
    if not present:
        return "| family | system |\n|---|---|"

    # dev + ONE test split. TIMIT ships core_test (its own 24-spk standard) and
    # full_test (the 168-spk extension); carrying both here would make four
    # metrics into twelve columns and stop being a summary. The detailed view
    # below keeps every split, and anything skipped is named under the table
    # rather than silently dropped.
    tests = [s for s in present if "test" in s]
    keep = [s for s in present if s == "dev"] + tests[:1]
    subs = [s for s in present if s in keep] or present
    omitted = [s for s in present if s not in subs]

    # SPLIT-major, with a spanning header per split. Row 1 is the \multicolumn
    # line (family/system carry rowspan=2 so they occupy both header rows);
    # row 2 names the five metrics, repeated under each split.
    n = len(CONCISE_METRICS)
    # Two \cmidrule weights. The heavy rule separates SPLITS (dev from test);
    # the light one separates METRIC GROUPS inside a split -- placement, edit
    # accounting, boundary detection -- which pair phones differently and
    # should not read as one undifferentiated run. Inline styles because the
    # site has no custom stylesheet to hang a class on.

    def _sep(i, j=None):
        """i = split index, j = column index within the split.

        A split boundary gets the heavy rule -- including the FIRST one, which
        divides the label block (family | system) from the numbers. Without it
        the labels ran straight into MAE while every other boundary on the row
        was marked.
        """
        if j == 0 or j is None:
            return SPLIT_RULE
        return GROUP_RULE if j in CONCISE_GROUP_STARTS else ""

    L = [TABLE_TAG, '<thead>',
         '<tr><th rowspan="2">Family</th><th rowspan="2">System</th>'
         + "".join(f'<th colspan="{n}"{_sep(i)}>{_esc(sub_disp(s, corpus))}</th>'
                   for i, s in enumerate(subs)) + '</tr>',
         '<tr>' + "".join(f"<th{_sep(i, j)}>{_hdr(m)}</th>"
                          for i, _s in enumerate(subs)
                          for j, (m, _g) in enumerate(CONCISE_METRICS)) + '</tr>',
         '</thead>', '<tbody>']

    # index by system, and rank on the primary split (the first present)
    per_sys: dict[str, dict[str, dict]] = {}
    for s in subs:
        for r in _conc(bysub, s):
            per_sys.setdefault(r["aligner"], {})[s] = r

    def rank(name: str):
        for s in subs:
            r = per_sys[name].get(s)
            if r is not None and _mae_or_inf(r) != float("inf"):
                return group_key(name, _mae_or_inf(r))
        return group_key(name, None)

    for name in sorted(per_sys, key=rank):
        label = disp(name) + (f" {FLAGGED[name]}" if name in FLAGGED else "")
        cells = [(_fmt(get(per_sys[name][s])) if s in per_sys[name] else "—",
                  _sep(i, j))
                 for i, s in enumerate(subs)
                 for j, (_m, get) in enumerate(CONCISE_METRICS)]
        L.append(f"<tr><td>{FAMILY_LABEL.get(fam(name), fam(name))}</td>"
                 f"<td>{_esc(label)}</td>"
                 + "".join(f"<td{sep}>{_esc(c)}</td>" for c, sep in cells)
                 + "</tr>")
    L += ["</tbody>", "</table>"]
    extra = sorted(disp(a) for a in SUPPRESS_CONCISE
                   if any(a in {r["aligner"] for r in _rows_of(bysub, s)}
                          for s in present))
    also = omitted + extra
    if also:
        L += ["", ("Also evaluated, in the detailed view below: "
                  f"**{', '.join(also)}**.")]
    return "\n".join(L)


def phone_table(corpus: str, bysub: dict[str, list[dict]],
                detailed: bool = False) -> str:
    """Phone-level comparison.

    `detailed=False` delegates to the pivoted concise view. `detailed=True` is
    the full long form: one row per (split, system) with EVERY column, so
    nothing the scorer produces is hidden from the published page.
    """
    if not detailed:
        return phone_table_concise(corpus, bysub)

    # THREE tables, each one metric family, and every one SPLIT-SPANNED like the
    # concise view: a system occupies one row, with dev and test side by side.
    #
    # The long form put split in a column, so a system appeared twice, forty
    # rows apart, and "does this hold from dev to test" -- the question the
    # detailed view exists to answer -- meant scrolling between two rows and
    # holding twenty-two numbers in your head. Splitting by family also lets
    # each table be read on its own terms: placement accuracy, then what left
    # the matched path, then whether the right NUMBER of boundaries was emitted.
    subs = subsets_of(bysub)
    present = [s for s in subs if _rows_of(bysub, s)]
    if not present:
        return "| Family | System |\n|---|---|"

    out: list[str] = []
    for title, groups in DETAILED_TABLES:
        metrics = [m for _t, g in groups for m in g]
        n = len(metrics)
        # Heavy rule opens each split (and fences the labels from the numbers);
        # light rule marks a group boundary inside a split, where a table
        # carries more than one group.
        starts = set()
        acc = 0
        for _t, g in groups[:-1]:
            acc += len(g)
            starts.add(acc)

        def sep(i, j=None):
            if j == 0 or j is None:
                return SPLIT_RULE
            return GROUP_RULE if j in starts else ""

        out += [f"### {corpus_disp(corpus)} {title}", "",
                TABLE_TAG, '<thead>',
                '<tr><th rowspan="2">Family</th><th rowspan="2">System</th>'
                + "".join(f'<th colspan="{n}"{sep(i)}>{_esc(sub_disp(s, corpus))}</th>'
                          for i, s in enumerate(present)) + '</tr>',
                '<tr>' + "".join(f"<th{sep(i, j)}>{_hdr(m)}</th>"
                                 for i, _s in enumerate(present)
                                 for j, (m, _g) in enumerate(metrics)) + '</tr>',
                '</thead>', '<tbody>']

        per_sys: dict[str, dict[str, dict]] = {}
        for s in present:
            for r in _rows_of(bysub, s):
                per_sys.setdefault(r["aligner"], {})[s] = r

        def rank(name: str):
            for s in present:
                r = per_sys[name].get(s)
                if r is not None and _mae_or_inf(r) != float("inf"):
                    return group_key(name, _mae_or_inf(r))
            return group_key(name, None)

        for name in sorted(per_sys, key=rank):
            label = disp(name) + (f" {FLAGGED[name]}" if name in FLAGGED else "")
            cells = [(_fmt(get(per_sys[name][s])) if s in per_sys[name] else "—",
                      sep(i, j))
                     for i, s in enumerate(present)
                     for j, (_m, get) in enumerate(metrics)]
            out.append(f"<tr><td>{FAMILY_LABEL.get(fam(name), fam(name))}</td>"
                       f"<td>{_esc(label)}</td>"
                       + "".join(f"<td{s2}>{_esc(c)}</td>" for c, s2 in cells)
                       + "</tr>")
        out += ["</tbody>", "</table>", ""]
    return "\n".join(out).rstrip()


#: TRACK 2 -- timestamped ASRs. They decode their OWN transcript instead of
#: being handed the reference, so their numbers mix recognition error with
#: timing error and are not comparable head-to-head with a forced aligner.
#: Membership is inferred from where the recipe lives (evals/timestamp_asrs/<tool>)
#: rather than listed here, so a tool cannot be declared one thing and installed
#: as another -- the same rule fabench.paths.tool_kind() uses.
def _track2() -> set[str]:
    d = ROOT / "evals" / "timestamp_asrs"
    return {p.name for p in d.glob("*") if p.is_dir() and not p.name.startswith(".")}


TRACK2 = _track2()


#: Word-level concise: the same shape as CONCISE_METRICS, on the word tier.
#: There is no PER or S/D/I here -- the word edit accounting is not emitted per
#: cell -- so it is MAE plus the boundary-detection trio.
#: The word MAE (internal key `wbe`) is the micro average -- pooled over all
#: word boundaries. The macro
#: variant (mean of per-utterance means) is gone entirely, not just from this
#: table: it answered the same question with a different weighting and never
#: disagreed about a ranking -- under 1% apart on every published cell -- so it
#: cost a reader a decision and returned nothing. Utterance- and speaker-balanced
#: averaging is gone from the phone tier too, on the same evidence: it reordered
#: nothing but four olign ablations 0.04 ms apart.
WORD_CONCISE = [("MAE (ms)", lambda r: r.get("wbe")),
                ("Pre", lambda r: r.get("wbnd_p")),
                ("Rec", lambda r: r.get("wbnd_r")),
                ("F1", lambda r: r.get("wbnd_f1"))]

WORD_DETAILED = WORD_CONCISE


def _wsdi(r) -> str:
    """Word Sub/Del/Ins in one cell, mirroring the phone S/D/I."""
    v = [r.get(k) for k in ("w_sub_pct", "w_del_pct", "w_ins_pct")]
    if any(x in (None, "", "\u2014") for x in v):
        return ""
    return "/".join(str(x) for x in v)


#: TRACK 2 adds the recognition side. A timestamped ASR decodes its own words,
#: so WER is what separates "placed the boundary badly" from "never recognised
#: the word" -- without it a bad word MAE is unattributable, which is precisely what
#: fabench/timestamp_asrs/base.py has specified since the package was written.
#: S/D/I says which kind of recognition error: a substitution still puts a word
#: somewhere near the right place, a deletion puts none there at all.
def _wpr(r):
    """Word precision and recall in one cell, as everywhere else on these pages."""
    p, rc = r.get("wbnd_p"), r.get("wbnd_r")
    return f"{p}/{rc}" if p not in (None, "", "\u2014") else None


#: Column order is the same on every page: MAE first, then P/R and the F1 that
#: summarises them, then everything else. S/D/I and WER are recognition
#: accounting -- they explain a track-2 system's word errors but are not
#: timing, so they read last.
#: Track 2 decodes its own transcript, so WER comes first after MAE: a bad word
#: MAE is unattributable between recognition and timing until you know how much
#: of the transcript was even right. The S/D/I split behind that WER, and P/R
#: behind the F1, are in Details -- a comparison table carries the headline of
#: each, not its decomposition.
WORD_TRACK2 = [("MAE (ms)", lambda r: r.get("wbe")),
               ("WER (%)", lambda r: r.get("wer")),
               ("F1", lambda r: r.get("wbnd_f1"))]


def _has_word(r) -> bool:
    return (str(r.get("wbe", "—")) not in ("—", "", "None")
            and r["aligner"] not in SUPPRESS_PUBLIC)


def _word_mae(r):
    """Word MAE. NOT _mae_or_inf -- that is the PHONE MAE, absent for every
    word-only tool, which collapsed them into an alphabetical clump."""
    try:
        return float(r["wbe"])
    except (ValueError, KeyError, TypeError):
        return None


def word_table_corpus(corpus: str, bysub: dict, detailed: bool = False,
                      track: int = 1) -> str:
    """Word-level results for ONE corpus, mirroring the phone tables.

    Concise pivots dev against test, one row per system. Detailed is long form,
    one row per (split, system). The membership differs from the phone tables in
    both directions and that is by construction: Charsiu, MAPS and BFA emit no
    word tier, while WhisperX, Parakeet-TDT and Qwen3 have no phone tier -- for
    several of them this is the only table they can appear in at all.
    """
    metrics = WORD_TRACK2 if track == 2 else WORD_CONCISE

    def keep(r):
        in2 = r["aligner"] in TRACK2
        return _has_word(r) and (in2 if track == 2 else not in2)

    present = [s for s in subsets_of(bysub)
               if any(keep(r) for r in bysub.get(s, []))]
    if not present:
        return ("_No timestamped ASR produced a word tier for this corpus._"
                if track == 2 else
                "_No system emitted a word tier for this corpus._")

    # EVERY split, always. The word tier has four metrics, so even three splits
    # is fourteen columns -- the same width as the phone concise table. There is
    # therefore no second "detailed" word view to maintain: once micro/macro
    # collapsed to one WBE, a detailed table was byte-identical to this one on
    # Buckeye and differed only by full_test on TIMIT.
    subs, omitted = present, []
    n = len(metrics)
    RULE = ' style="border-left:1px solid rgba(128,128,128,.35)"'
    L = [TABLE_TAG, '<thead>',
         '<tr><th rowspan="2">Family</th><th rowspan="2">System</th>'
         + "".join(f'<th colspan="{n}"{RULE}>'
                   f'{_esc(sub_disp(s, corpus))}</th>'
                   for i, s in enumerate(subs)) + '</tr>',
         '<tr>' + "".join(f'<th{RULE if j == 0 else ""}>{_hdr(m)}</th>'
                          for i, _s in enumerate(subs)
                          for j, (m, _g) in enumerate(metrics)) + '</tr>',
         '</thead>', '<tbody>']

    per_sys: dict[str, dict] = {}
    for s in subs:
        for r in bysub.get(s, []):
            if keep(r):
                per_sys.setdefault(r["aligner"], {})[s] = r

    def rank(name):
        for s in subs:
            r = per_sys[name].get(s)
            if r is not None:
                return group_key(name, _word_mae(r))
        return group_key(name, None)

    for name in sorted(per_sys, key=rank):
        label = disp(name) + (f" {FLAGGED[name]}" if name in FLAGGED else "")
        cells = [(_fmt(get(per_sys[name][s])) if s in per_sys[name] else "—",
                  RULE if j == 0 else "")
                 for i, s in enumerate(subs)
                 for j, (_m, get) in enumerate(metrics)]
        L.append(f"<tr><td>{FAMILY_LABEL.get(fam(name), fam(name))}</td>"
                 f"<td>{_esc(label)}</td>"
                 + "".join(f"<td{sep}>{_esc(c)}</td>" for c, sep in cells)
                 + "</tr>")
    L += ["</tbody>", "</table>"]
    if omitted:
        L += ["", (f"Also evaluated, in the detailed view: "
                  f"**{', '.join(omitted)}**.")]
    return "\n".join(L)


def word_table(data: dict) -> str:
    L = ["| corpus | split | family | system | word MAE | word F1 |",
         "|---|---|---|---|---|---|"]
    for corpus in sorted(data):
        for sub in subsets_of(data[corpus]):
            rows = [r for r in data[corpus][sub]
                    if str(r.get("wbe", "—")) not in ("—", "")
                    and r["aligner"] not in SUPPRESS_PUBLIC]
            def key(r):
                try:
                    return float(r["wbe"])
                except (ValueError, KeyError):
                    return float("inf")
            def _wm(r):
                """Word MAE. NOT _mae_or_inf -- that is the PHONE MAE, which is
                absent for every word-only tool, so sorting on it collapsed
                them to an alphabetical clump inside their family."""
                try:
                    return float(r["wbe"])
                except (ValueError, KeyError, TypeError):
                    return None

            for r in sorted(rows, key=lambda x: group_key(x["aligner"], _wm(x))):
                name = r["aligner"]
                label = disp(name) + (f" {FLAGGED[name]}" if name in FLAGGED else "")
                # word F1, not the PHONE bnd_f1 this used to show -- that was
                # a phone metric under a word heading, and blank for every
                # word-only tool.
                L.append(f"| {corpus} | {sub_disp(sub)} | "
                         f"{FAMILY_LABEL.get(fam(name), fam(name))} | {label} | "
                         f"{_fmt(r.get('wbe'))} | {_fmt(r.get('wbnd_f1'))} |")
    return "\n".join(L)


def completion_note(corpus: str) -> str:
    """Which systems scored FEWER utterances than the cell contains.

    A tool that dies on some utterances and completes the rest still gets a
    row, and that row's MAE is computed over whatever survived -- an easier
    subset than its competitors were scored on. Nothing in the table said so.
    MFA drops 8 of 4,513 Buckeye test utterances and MFA 2.0 drops 17 of 4,456
    on dev; small, but it is exactly the survivorship the ARR/Del columns exist
    to expose at the phone level, one level up.

    Silent when every system is complete -- a note that always fires is
    ignored. Counts come from leaderboard.csv `n_utts`, the scorer's own
    accounting, not from line-counting hyp files.
    """
    import csv

    lines = []
    for lb in sorted((ROOT / "summary" / "en" / corpus).glob("*/leaderboard.csv")):
        sub = lb.parent.name
        if "__" in sub:                     # noise cells have their own table
            continue
        rows = [r for r in csv.DictReader(lb.open())
                if r.get("n_utts") and r.get("aligner") not in SUPPRESS_PUBLIC]
        if not rows:
            continue
        full = max(int(r["n_utts"]) for r in rows)
        short = sorted({(disp(r["aligner"]), int(r["n_utts"])) for r in rows
                        if int(r["n_utts"]) < full})
        if not short:
            continue
        # two decimals, because one rounds 4,512/4,513 to "100.0%" -- a system
        # listed as incomplete must not display as complete
        lines.append(f"- **{sub_disp(sub)}** ({full:,} utterances): "
                     + "; ".join(f"{a} {n:,} = {100 * n / full:.2f}%, "
                                 f"{full - n} missing"
                                 for a, n in short))
    if not lines:
        return "Every system scored every utterance in every split."
    return ("Systems that scored **fewer utterances than the split contains**. "
            "Their numbers are computed over the subset that survived, which is "
            "not the same subset as everyone else's:\n\n" + "\n".join(lines))


def coverage_table(data: dict) -> str:
    """Who was scored where.

    Collapses to a single sentence when every split has the same systems, which
    is the usual case and made four identical eleven-name rows. It expands back
    to the table the moment they diverge -- the whole point of this block is to
    show a gap, so the concise form may never be able to hide one.
    """
    per_split = {}
    for corpus in sorted(data):
        for sub in subsets_of(data[corpus]):
            names = tuple(disp(t) for t in
                          sorted({r["aligner"] for r in data[corpus][sub]}
                                 - SUPPRESS_PUBLIC, key=sort_key))
            per_split[(corpus, sub)] = names
    if not per_split:
        return "_No systems scored._"

    sets = set(per_split.values())
    if len(sets) == 1:
        names = next(iter(sets))
        splits = ", ".join(sub_disp(s, c) for c, s in per_split)
        return (f"All **{len(names)}** systems are scored on all "
                f"**{len(per_split)}** splits ({splits}):\n\n"
                f"{', '.join(names)}.")

    # Diverged: name the splits, and say what each is missing against the union.
    union = sorted({n for v in sets for n in v}, key=str.lower)
    L = ["| Split | Systems | Missing |", "|---|---|---|"]
    for (corpus, sub), names in per_split.items():
        gap = [n for n in union if n not in names]
        L.append(f"| {sub_disp(sub, corpus)} | {len(names)} | "
                 f"{', '.join(gap) if gap else '—'} |")
    return "\n".join(L)


def noise_table(clean: dict, noisy: dict, key: str = "mae",
                fmt: str = "{:.1f}", corpus_only: str | None = None,
                rank_key: str = "mae", summarize: bool = False) -> str:
    """Phone metric under clean and the four Kaldi conditions.

    Track-1 table shape (see phone_table_concise): HTML, one row per SYSTEM,
    a spanning header cell per split, so dev and test read horizontally on
    the same line instead of forty rows apart. Read the DELTA from clean, not
    across conditions: conditions differ in severity by construction (additive
    `noise` reaches 0 dB SNR, `babble` bottoms out at 13 dB), so
    cross-condition comparison measures the recipe, not the tool.

    `summarize` collapses the four conditions into one **Noisy** column, their
    mean. That is the comparison page's version: the question there is "how far
    does this system fall", and four columns per split answered it four times
    while doubling the width. The per-condition breakdown moves to Details.

    A summarised cell needs ALL FOUR conditions. A mean over two of them is not
    on the same scale as a mean over four, and printing them in one column
    would invite exactly the comparison the missing cells cannot support -- so
    a system still mid-sweep shows an em dash rather than a partial average.
    """
    CONDS = ("clean", "reverb", "noise", "music", "babble")
    HEADS = ("Clean", "Noisy") if summarize else tuple(c.capitalize() for c in CONDS)

    def _sep(j):
        # The heavy rule opens each split (and fences the label block, same
        # as track 1); the light rule separates the clean baseline from the
        # degradations that are read against it.
        return SPLIT_RULE if j == 0 else (GROUP_RULE if j == 1 else "")

    def _collapse(row: list) -> list:
        """[clean, reverb, noise, music, babble] -> [clean, mean-of-four]."""
        deg = row[1:]
        # A paired cell ("0.505/0.428") has no mean. No caller combines
        # summarize with a tuple key today; this makes that a clear refusal
        # rather than a TypeError from sum() if one ever does.
        if any(isinstance(v, str) for v in deg):
            raise ValueError("summarize= cannot average a paired metric; "
                             "give it a single field or drop summarize")
        if any(v is None for v in deg):
            return [row[0], None]
        return [row[0], sum(deg) / len(deg)]

    def val(d, c, sub, tool, _key=None):
        # A tool can have SEVERAL rows in one cell -- torchaudio_fa reports
        # mode A (words only, MAE "—") and mode B (phones, MAE 36.8). Taking
        # the first match returned the word-only row and silently dropped the
        # tool from this phone table even though its phone results existed.
        # Scan for a row that actually parses.
        #
        # A TUPLE key is a PAIR rendered in one cell, like "0.505/0.428".
        # Precision and recall are read together -- which way a system is
        # unbalanced is the whole point -- and two adjacent tables of the same
        # shape made that a comparison between pages rather than within a cell.
        k = _key or key
        for r in d.get(c, {}).get(sub, []):
            if r["aligner"] != tool:
                continue
            try:
                if isinstance(k, tuple):
                    parts = [float(str(r[f]).split(" [")[0]) for f in k]
                    return "/".join(fmt.format(x) for x in parts)
                return float(str(r[k]).split(" [")[0])
            except (ValueError, IndexError, KeyError):
                continue
        return None

    L: list[str] = []
    for corpus in sorted(clean):
        # A noise table lives with its corpus now, so it carries one corpus's
        # rows. The cross-corpus version put TIMIT and Buckeye in one grid on a
        # page that is meant to be methodology, not results.
        if corpus_only and corpus != corpus_only:
            continue
        # only subsets that actually have noisy counterparts
        subs = [s for s in subsets_of(clean[corpus])
                if any(f"{s}__{c}" in noisy.get(corpus, {})
                       for c in CONDS[1:])]
        if not subs:
            continue
        tools = sorted({r["aligner"] for s in subs for r in clean[corpus][s]}
                       - SUPPRESS_PUBLIC)
        per_sys: dict[str, dict[str, list]] = {}
        for t in tools:
            cells = {s: [val(clean, corpus, s, t)]
                     + [val(noisy, corpus, f"{s}__{c}", t)
                        for c in CONDS[1:]] for s in subs}
            if summarize:
                cells = {s: _collapse(row) for s, row in cells.items()}
            if any(v is not None for row in cells.values() for v in row):
                per_sys[t] = cells

        def rank(t):
            # order rows by the clean value of ONE key across the tables that
            # share a tier, so a reader comparing them is looking at the same
            # row in the same place: phone MAE orders both phone tables, word
            # MAE orders the word one. Ranking the word table by phone MAE
            # would drop WhisperX, Qwen3 and stable-ts to the bottom together
            # -- they have no phone tier at all, which is not a statement
            # about their word timing.
            for s in subs:
                r = val(clean, corpus, s, t, _key=rank_key)
                if r is not None:
                    return group_key(t, r)
            return group_key(t, None)

        L += [TABLE_TAG, '<thead>',
              '<tr><th rowspan="2">Family</th><th rowspan="2">System</th>'
              + "".join(f'<th colspan="{len(HEADS)}"{SPLIT_RULE}>'
                        f'{_esc(sub_disp(s, corpus))}</th>' for s in subs) + '</tr>',
              '<tr>' + "".join(f"<th{_sep(j)}>{c}</th>" for _s in subs
                               for j, c in enumerate(HEADS)) + '</tr>',
              '</thead>', '<tbody>']
        for t in sorted(per_sys, key=rank):
            label = disp(t) + (f" {FLAGGED[t]}" if t in FLAGGED else "")
            tds = "".join(
                f"<td{_sep(j)}>"
                f"{(v if isinstance(v, str) else fmt.format(v)) if v is not None else '—'}"
                "</td>"
                for s in subs for j, v in enumerate(per_sys[t][s]))
            L.append(f"<tr><td>{FAMILY_LABEL.get(fam(t), fam(t))}</td>"
                     f"<td>{_esc(label)}</td>" + tds + "</tr>")
        L += ["</tbody>", "</table>"]
    return "\n".join(L)


#: The comparison page's noise summary: several metrics, each Clean vs Noisy.
NOISE_SUMMARY_METRICS = [
    ("MAE (ms)", "mae", "{:.1f}"),
    # PER sits beside MAE because it is what MAE cannot see: MAE averages the
    # boundaries a system kept, so a system that copes with noise by dropping
    # phones improves its own MAE while PER records the phones it lost.
    ("PER (%)", "per", "{:.1f}"),
    ("F1 @20 ms", "bnd_f1", "{:.3f}"),
]
#: The same two questions on the word tier. Pre/Rec move to Details with their
#: phone counterparts; what a comparison page needs is placement and detection.
WORD_SUMMARY_METRICS = [
    ("MAE (ms)", "wbe", "{:.1f}"),
    ("F1 @20 ms", "wbnd_f1", "{:.3f}"),
]


def noise_summary_table(clean: dict, noisy: dict, corpus_only: str,
                        metrics=NOISE_SUMMARY_METRICS,
                        rank_key: str = "mae",
                        suppress: set | None = None) -> str:
    """Clean vs Noisy for SEVERAL metrics, in one table.

    MAE and F1 were two tables reading "the same conditions" -- the same rows
    in the same order, and a reader had to hold one while scrolling to the
    other, which is precisely the comparison the pair exists to invite: a
    system whose MAE holds while its F1 falls is aligning less, not degrading
    gracefully. Side by side, that shows up on one line.

    THREE header rows, because there are three nested things to name: the
    split, the metric, and the condition. Stacking them into two would have
    made a column called "MAE (ms) Clean" and lost the grouping that says MAE
    and F1 are different questions rather than four flavours of one.

    Noisy is the mean of the four conditions and needs all four; see
    noise_table, whose summarised mode this shares its arithmetic with.
    """
    CONDS = ("reverb", "noise", "music", "babble")

    def val(d, c, sub, tool, key):
        for r in d.get(c, {}).get(sub, []):
            if r["aligner"] != tool:
                continue
            try:
                return float(str(r[key]).split(" [")[0])
            except (ValueError, IndexError):
                continue
        return None

    corpus = corpus_only
    if corpus not in clean:
        return "| Family | System |\n|---|---|"
    subs = [s for s in subsets_of(clean[corpus])
            if any(f"{s}__{c}" in noisy.get(corpus, {}) for c in CONDS)]
    if not subs:
        return "| Family | System |\n|---|---|"

    hide = suppress or set()
    tools = sorted({r["aligner"] for s in subs for r in clean[corpus][s]}
                   - SUPPRESS_PUBLIC - hide)
    per_sys: dict[str, dict[str, list]] = {}
    for t in tools:
        cells = {}
        for s in subs:
            row = []
            for _label, key, _fmt in metrics:
                base = val(clean, corpus, s, t, key)
                deg = [val(noisy, corpus, f"{s}__{c}", t, key) for c in CONDS]
                row += [base, None if any(v is None for v in deg)
                        else sum(deg) / len(deg)]
            cells[s] = row
        # A withheld phone tier keeps its row, all cells em dash. Only the WORD
        # summary uses this builder too, where torchaudio has real numbers, so
        # gate on the metric set rather than the system alone.
        withheld = t in SUPPRESS_PHONE_TIER and metrics is NOISE_SUMMARY_METRICS
        if any(v is not None for row in cells.values() for v in row) or withheld:
            per_sys[t] = cells

    def rank(t):
        for s in subs:
            r = val(clean, corpus, s, t, rank_key)
            if r is not None:
                return group_key(t, r)
        return group_key(t, None)

    n = len(metrics) * 2

    def sep(j):
        """Heavy rule opens a split; light rule opens each metric within it."""
        return SPLIT_RULE if j == 0 else (GROUP_RULE if j % 2 == 0 else "")

    L = [TABLE_TAG, '<thead>',
         '<tr><th rowspan="3">Family</th><th rowspan="3">System</th>'
         + "".join(f'<th colspan="{n}"{SPLIT_RULE}>{_esc(sub_disp(s, corpus))}</th>'
                   for s in subs) + '</tr>',
         '<tr>' + "".join(f'<th colspan="2"{SPLIT_RULE if k == 0 else GROUP_RULE}>'
                          f'{_esc(label)}</th>'
                          for _s in subs
                          for k, (label, _key, _f) in enumerate(metrics)) + '</tr>',
         '<tr>' + "".join(f"<th{sep(j)}>{'Clean' if j % 2 == 0 else 'Noisy'}</th>"
                          for _s in subs for j in range(n)) + '</tr>',
         '</thead>', '<tbody>']
    for t in sorted(per_sys, key=rank):
        label = disp(t) + (f" {FLAGGED[t]}" if t in FLAGGED else "")
        tds = ""
        for s in subs:
            for j, v in enumerate(per_sys[t][s]):
                f = metrics[j // 2][2]
                tds += f"<td{sep(j)}>{f.format(v) if v is not None else '—'}</td>"
        L.append(f"<tr><td>{FAMILY_LABEL.get(fam(t), fam(t))}</td>"
                 f"<td>{_esc(label)}</td>" + tds + "</tr>")
    L += ["</tbody>", "</table>"]
    also = sorted(disp(a) for a in hide
                  if any(a in {r["aligner"] for r in clean[corpus].get(s, [])}
                         for s in subs))
    if also:
        L += ["", ("Also evaluated, in [Details](Details.md): "
                  f"**{', '.join(also)}**.")]
    return "\n".join(L)



#: P/R/F1 share one grid: they are three views of the SAME pairing, and the
#: question a reader brings is which way a system is unbalanced under a given
#: condition. Split across tables that is a comparison between pages; nested
#: under each condition it is three adjacent cells.
PRF_METRICS = [("P/R", ("bnd_p", "bnd_r")), ("F1", "bnd_f1")]
#: Segmentation balance, the same way. OS says whether too many or too few
#: boundaries were emitted, R-value how far that is from ideal -- they answer
#: one question together and are read as a pair.
OSR_METRICS = [("OS", "os"), ("R-val", "r_value")]
#: The word tier's detection pair, same shape and the same 20 ms tolerance --
#: aggregate.py scores word boundaries with tol_s=0.020, exactly as it does
#: phones.
WORD_PRF_METRICS = [("P/R", ("wbnd_p", "wbnd_r")), ("F1", "wbnd_f1")]
#: Word segmentation balance. These exist: score/aggregate.py has emitted
#: wbnd_os and w_r_value from the start. They were simply never written into a
#: report, so the pages read as though the tier had no balance to show.
WORD_OSR_METRICS = [("OS", "wbnd_os"), ("R-val", "w_r_value")]

#: The rest of the phone tier, each family condition-nested like the two above.
#: These used to be clean-only tables sitting beside the by-condition ones, so
#: a reader comparing a system's median under babble against its median clean
#: had to hold two tables in their head. Every phone number now reads across
#: clean and the four conditions on one row.
DIST_METRICS = [("x̃ (ms)", "median", "{:.1f}"),
                ("δ̄ (ms)", "signed", "{:.1f}")]
TA_METRICS = [("t=10", "ta_10", "{:.1f}"),
              ("t=50", "ta_50", "{:.1f}"),
              ("t=100", "ta_100", "{:.1f}")]
#: The interval is carried INSIDE the MAE string ("43.1 [41.1,45.1]"), not in a
#: column of its own, so it is pulled out with a callable rather than a key.
CI_METRICS = [("95% CI",
               lambda r: (f"[{r['mae'].split('[')[1].rstrip(']')}]"
                          if "[" in str(r.get("mae", "")) else None))]
#: Bare S / D / I: three words repeated under five conditions cost more width
#: than they carry, and the caption directly above defines them.
EDIT_METRICS = [("S", "sub_pct", "{:.1f}"),
                ("D", "del_pct", "{:.1f}"),
                ("I", "ins_pct", "{:.1f}")]
PER_METRIC = [("PER (%)", "per", "{:.1f}")]


def detection_grid(clean: dict, noisy: dict, corpus: str,
                   metrics=PRF_METRICS, rank_key: str = "mae") -> str:
    """Metrics nested under every condition, for each split.

    THREE header rows -- split, condition, metric -- because that is how deep
    the nesting actually goes. Thirty columns is a lot, but they are 2x5x3 and
    read as such; the alternative was three tables of ten with the row order
    repeated, which is what this replaces.
    """
    CONDS = ("clean", "reverb", "noise", "music", "babble")

    def val(d, c, sub, tool, key):
        """A TUPLE key renders both fields in one cell, as "0.505/0.428".

        A CALLABLE key returns the cell verbatim -- used for the 95% CI, which
        lives inside the MAE string rather than in a column of its own.
        """
        for r in d.get(c, {}).get(sub, []):
            if r["aligner"] != tool:
                continue
            try:
                if callable(key):
                    return key(r)
                if isinstance(key, tuple):
                    return "/".join(f"{float(str(r[f]).split(' [')[0]):.3f}"
                                    for f in key)
                return float(str(r[key]).split(" [")[0])
            except (ValueError, IndexError, KeyError, TypeError):
                continue
        return None

    # Metrics may carry their own format: probabilities want three decimals,
    # milliseconds and percentages want one. A single grid-wide format printed
    # "43.100 ms" the moment this builder took over the phone tables.
    fmts = [(mm[2] if len(mm) > 2 else "{:.3f}") for mm in metrics]

    if corpus not in clean:
        return ""
    subs = [s for s in subsets_of(clean[corpus])
            if any(f"{s}__{c}" in noisy.get(corpus, {}) for c in CONDS[1:])]
    if not subs:
        return ""

    tools = sorted({r["aligner"] for s in subs for r in clean[corpus][s]}
                   - SUPPRESS_PUBLIC)
    per_sys = {}
    for t in tools:
        cells = {}
        for s in subs:
            row = []
            for cond in CONDS:
                src, key_sub = ((clean, s) if cond == "clean"
                                else (noisy, f"{s}__{cond}"))
                row += [val(src, corpus, key_sub, t, mm[1]) for mm in metrics]
            cells[s] = row
        if any(v is not None for r in cells.values() for v in r) \
                or t in SUPPRESS_PHONE_TIER:
            per_sys[t] = cells

    def rank(t):
        # Rank by the TIER's own metric. Ranking the word grid by phone MAE
        # would sink WhisperX, Qwen3 and stable-ts as a block for having no
        # phone tier, which says nothing about their word timing.
        for s in subs:
            r = val(clean, corpus, s, t, rank_key)
            if r is not None:
                return group_key(t, r)
        return group_key(t, None)

    m = len(metrics)
    n = len(CONDS) * m

    def sep(j):
        """Heavy rule opens a split; light rule opens each condition in it."""
        return SPLIT_RULE if j == 0 else (GROUP_RULE if j % m == 0 else "")

    # A one-metric family needs no metric row: "95% CI" repeated under each of
    # Clean/Reverb/Noise/Music/Babble says nothing the caption has not.
    hrows = 3 if m > 1 else 2
    L = [TABLE_TAG, '<thead>',
         f'<tr><th rowspan="{hrows}">Family</th><th rowspan="{hrows}">System</th>'
         + "".join(f'<th colspan="{n}"{SPLIT_RULE}>{_esc(sub_disp(s, corpus))}</th>'
                   for s in subs) + '</tr>',
         '<tr>' + "".join(
             f'<th colspan="{m}"{SPLIT_RULE if k == 0 else GROUP_RULE}>'
             f'{c.capitalize()}</th>'
             for _s in subs for k, c in enumerate(CONDS)) + '</tr>']
    if m > 1:
        L.append('<tr>' + "".join(f"<th{sep(j)}>{metrics[j % m][0]}</th>"
                                  for _s in subs for j in range(n)) + '</tr>')
    L += ['</thead>', '<tbody>']
    for t in sorted(per_sys, key=rank):
        label = disp(t) + (f" {FLAGGED[t]}" if t in FLAGGED else "")
        tds = "".join(
            f"<td{sep(j)}>"
            f"{'—' if v is None else (v if isinstance(v, str) else fmts[j % m].format(v))}"
            "</td>"
            for s in subs for j, v in enumerate(per_sys[t][s]))
        L.append(f"<tr><td>{FAMILY_LABEL.get(fam(t), fam(t))}</td>"
                 f"<td>{_esc(label)}</td>" + tds + "</tr>")
    L += ["</tbody>", "</table>"]
    return "\n".join(L)


def _captioned_grids(clean, noisy, corpus, pairs, rank_key="mae") -> str:
    """Several condition-nested grids under one heading, each with a caption.

    Splitting a wide family this way keeps every table at ten or thirty columns
    instead of one seventy-column table nobody can read across.
    """
    out = []
    for label, metrics in pairs:
        grid = detection_grid(clean, noisy, corpus, metrics=metrics,
                              rank_key=rank_key)
        if grid:
            out += [f"**{label}**", "", grid, ""]
    return "\n".join(out).rstrip()


def detection_by_condition(clean: dict, noisy: dict, corpus: str,
                           tier: str = "phone") -> str:
    """Detection, then segmentation balance, each nested under the conditions.

    One builder for both tiers: the word tier is scored with the same matcher
    at the same 20 ms tolerance, so it gets the same two tables rather than a
    parallel implementation that could drift.
    """
    prf, osr, rank = ((PRF_METRICS, OSR_METRICS, "mae") if tier == "phone"
                      else (WORD_PRF_METRICS, WORD_OSR_METRICS, "wbe"))
    return _captioned_grids(clean, noisy, corpus, (
        ("Precision / Recall / F1 (0–1)", prf),
        ("Over-segmentation and R-value (ratio)", osr),
    ), rank_key=rank)


#: Track 2 in full. The comparison page carries MAE, WER and F1; the two
#: decompositions behind them -- which edits made that WER, and which way P/R
#: is unbalanced -- are here, on the same five conditions as every other table.
T2_MAE = [("MAE (ms)", "wbe", "{:.1f}")]
T2_WER = [("WER", "wer", "{:.1f}"), ("S", "w_sub_pct", "{:.1f}"),
          ("D", "w_del_pct", "{:.1f}"), ("I", "w_ins_pct", "{:.1f}")]


def track2_by_condition(clean: dict, noisy: dict, corpus: str) -> str:
    return _captioned_grids(clean, noisy, corpus, (
        ("Word MAE (ms)", T2_MAE),
        ("Recognition — WER, and the edits behind it (%)", T2_WER),
        ("Word detection @20 ms — precision / recall and F1 (0–1)",
         WORD_PRF_METRICS),
        ("Over-segmentation and R-value (ratio)", WORD_OSR_METRICS),
    ), rank_key="wbe")


def distribution_by_condition(clean: dict, noisy: dict, corpus: str) -> str:
    return _captioned_grids(clean, noisy, corpus, (
        ("Median x̃ and mean signed error δ̄ (ms)", DIST_METRICS),
        ("Tolerance accuracy — share of boundaries within t ms (%)",
         TA_METRICS),
        ("95% CI on the mean MAE (ms)", CI_METRICS),
    ))


def editing_by_condition(clean: dict, noisy: dict, corpus: str) -> str:
    return _captioned_grids(clean, noisy, corpus, (
        ("Substitutions, deletions, insertions (%)", EDIT_METRICS),
        ("Phone error rate (%)", PER_METRIC),
    ))


def _space_after_tables(body: str) -> str:
    """One blank line after every table.

    The gap has to be emitted HERE rather than left in the page template: a
    block can hold several tables (the captioned grids do), and only the
    generator knows where those internal boundaries fall.
    """
    body = re.sub(r"</table>[ \t]*\n+(?!\Z)", "</table>\n\n", body)
    body = body.rstrip("\n")
    if body.endswith("</table>") or body.rstrip().endswith("|"):
        body += "\n"
    return body


def _flag_notes(body: str) -> str:
    """Append the note for every flag the table actually uses."""
    notes = [n for glyph, n in FLAG_NOTE.items() if glyph in body]
    return body + ("\n" + "\n\n".join(notes) + "\n" if notes else "")


def replace_block(text: str, ident: str, body: str) -> tuple[str, bool]:
    body = _flag_notes(_space_after_tables(body))
    b, e = BEGIN.format(ident), END.format(ident)
    pat = re.compile(re.escape(b) + r".*?" + re.escape(e), re.DOTALL)
    if not pat.search(text):
        return text, False
    return pat.sub(f"{b}\n{body}\n{e}", text), True


#: Which page owns each generated block.
#:
#: Phone results live WITH THEIR CORPUS because the failure modes are
#: corpus-specific and the edit columns are not comparable across the two --
#: TIMIT is deletion-dominated, Buckeye insertion-dominated, and a reader
#: scrolling one long page compares rows that must not be compared. Everything
#: routed to the index is cross-corpus by construction: the coverage matrix, the
#: provenance table, and the word/noise tables, which exist precisely to put the
#: two corpora side by side.
BLOCK_DOC = {
    "coverage": "records/aligners/en/README.md",
    "provenance": "records/aligners/en/README.md",         # written by gen_provenance.py
    "word-timit-detailed": "records/aligners/en/timit/Details.md",
    "word-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "noise-timit-detailed": "records/aligners/en/timit/Details.md",
    "noise-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "noise-f1-timit-detailed": "records/aligners/en/timit/Details.md",
    "noise-f1-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "noise-word-timit-detailed": "records/aligners/en/timit/Details.md",
    "noise-word-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "phone-timit": "records/aligners/en/timit/README.md",
    "dist-timit-detailed": "records/aligners/en/timit/Details.md",
    "track2-timit-detailed": "records/aligners/en/timit/Details.md",
    "edit-timit-detailed": "records/aligners/en/timit/Details.md",
    "phone-buckeye": "records/aligners/en/buckeye/README.md",
    "caption-timit": "records/aligners/en/timit/Details.md",
    "caption-buckeye": "records/aligners/en/buckeye/Details.md",
    "completion-timit": "records/aligners/en/timit/README.md",
    "completion-buckeye": "records/aligners/en/buckeye/README.md",
    "word-timit": "records/aligners/en/timit/README.md",
    "word-buckeye": "records/aligners/en/buckeye/README.md",
    "word2-timit": "records/aligners/en/timit/README.md",
    "word2-buckeye": "records/aligners/en/buckeye/README.md",
    "dist-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "track2-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
    "edit-buckeye-detailed": "records/aligners/en/buckeye/Details.md",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", "--docs-root", dest="docs_root", default=str(ROOT),
                    help="directory the BLOCK_DOC paths are relative to")
    ap.add_argument("--records-dir", default=None,
                    help="write the record pages here instead of "
                         "records/aligners/en/ -- used by publish_records.py to "
                         "fill a dated snapshot")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any file would change (for CI)")
    a = ap.parse_args(argv)

    # Every record page can be redirected at a dated snapshot. summary/ holds no
    # published page any more -- it is script output, gitignored.
    def _doc(rel: str) -> str:
        if a.records_dir and rel.startswith("records/aligners/en/"):
            return str(pathlib.Path(a.records_dir)
                       / rel[len("records/aligners/en/"):])
        return rel

    data = drop_phone_tier(collect())
    noisy = drop_phone_tier(collect(include_noisy=True))
    # Track 2 is scored into its OWN tree and must be read from there.
    asr = collect(kind='timestamp_asrs')
    # Track 2's noisy cells live in the SIBLING tree. Reading `noisy` here --
    # the aligners one -- is what left the track-2 table empty before.
    asr_noisy = collect(include_noisy=True, kind='timestamp_asrs')
    if not data:
        print("no reports found; run evals/run_evals.sh then rescore_all.sh",
              file=sys.stderr)
        return 1

    blocks = {
        "coverage": coverage_table(data),
        # The phone tier's remaining families, each nested under the five
        # conditions like MAE and detection already are. Nothing on this page
        # is clean-only any more: every phone number reads across clean and the
        # four conditions on one row.
        "track2-timit-detailed": track2_by_condition(asr, asr_noisy, "timit"),
        "track2-buckeye-detailed": track2_by_condition(asr, asr_noisy,
                                                       "buckeye"),
        "dist-timit-detailed": distribution_by_condition(data, noisy, "timit"),
        "dist-buckeye-detailed": distribution_by_condition(data, noisy,
                                                           "buckeye"),
        "edit-timit-detailed": editing_by_condition(data, noisy, "timit"),
        "edit-buckeye-detailed": editing_by_condition(data, noisy, "buckeye"),
        # Comparison page: Clean + one Noisy column (the mean of the four).
        # Details carries the per-condition breakdown, same builder, summarize
        # off -- so the two can never disagree about a number.
        # The comparison table for each tier: MAE and F1, Clean and Noisy, in
        # ONE grid. The clean-only tables these replace were byte-identical to
        # the Clean columns here -- verified before removing them.
        "phone-timit": noise_summary_table(data, noisy, "timit",
                                           suppress=SUPPRESS_CONCISE),
        "phone-buckeye": noise_summary_table(data, noisy, "buckeye",
                                             suppress=SUPPRESS_CONCISE),
        "word-timit": noise_summary_table(data, noisy, "timit",
                                          metrics=WORD_SUMMARY_METRICS,
                                          rank_key="wbe"),
        "word-buckeye": noise_summary_table(data, noisy, "buckeye",
                                            metrics=WORD_SUMMARY_METRICS,
                                            rank_key="wbe"),
        # Word tier under the same conditions. Ranked by word MAE, not phone:
        # the word-only systems have no phone tier, and this is the one table
        # where they can be read at all.
        # Word tier in full. The comparison page shows MAE and F1 only, so
        # Pre and Rec exist here or nowhere -- the same split the phone tier
        # already makes between its comparison and detail views.
        "word-timit-detailed": detection_by_condition(data, noisy, "timit",
                                                      tier="word"),
        "word-buckeye-detailed": detection_by_condition(data, noisy, "buckeye",
                                                        tier="word"),
        # Details: every condition, its own column.
        "noise-timit-detailed": noise_table(data, noisy, corpus_only="timit"),
        "noise-buckeye-detailed": noise_table(data, noisy, corpus_only="buckeye"),
        "noise-f1-timit-detailed": detection_by_condition(data, noisy, "timit"),
        "noise-f1-buckeye-detailed": detection_by_condition(data, noisy,
                                                            "buckeye"),
        "noise-word-timit-detailed": noise_table(data, noisy, key="wbe",
                                                 rank_key="wbe",
                                                 corpus_only="timit"),
        "noise-word-buckeye-detailed": noise_table(data, noisy, key="wbe",
                                                   rank_key="wbe",
                                                   corpus_only="buckeye"),
        "caption-timit": caption(),
        "caption-buckeye": caption(),
        "completion-timit": completion_note("timit"),
        "completion-buckeye": completion_note("buckeye"),
        "word2-timit":
            word_table_corpus("timit", asr.get("timit", {}), track=2),
        "word2-buckeye":
            word_table_corpus("buckeye", asr.get("buckeye", {}), track=2),
    }

    docs_root = Path(a.docs_root)
    # group by target file so each page is read and written exactly once
    by_doc: dict[str, list[str]] = {}
    for ident in blocks:
        by_doc.setdefault(_doc(BLOCK_DOC.get(ident, "records/aligners/en/README.md")),
                          []).append(ident)

    missing, stale = [], []
    for rel, idents in sorted(by_doc.items()):
        doc = docs_root / rel
        if not doc.is_file():
            missing += [f"{i} (no {rel})" for i in idents]
            continue
        text = original = doc.read_text()
        for ident in idents:
            text, ok = replace_block(text, ident, blocks[ident])
            if ok:
                print(f"  filled {ident}: "
                      f"{blocks[ident].count(chr(10)) - 1} rows -> {rel}")
            else:
                missing.append(f"{ident} (no marker in {rel})")
        if text == original:
            continue
        stale.append(rel)
        if not a.check:
            doc.write_text(text)
            print(f"  wrote {rel}")

    if missing:
        print("  no target for: " + ", ".join(missing), file=sys.stderr)

    if a.check:
        if stale:
            print(f"  STALE: {', '.join(stale)} differ from the reports",
                  file=sys.stderr)
            return 1
        print("  up to date")
        return 0
    if not stale:
        print("  no change")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
