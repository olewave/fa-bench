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
# organizations. Any commercial use requires a separate licence from Olewave, LLC.
#
# AS FAR AS THE LAW ALLOWS, THE SOFTWARE COMES AS IS, WITHOUT ANY WARRANTY OR
# CONDITION, AND THE LICENSOR WILL NOT BE LIABLE TO YOU FOR ANY DAMAGES ARISING
# OUT OF THESE TERMS OR THE USE OR NATURE OF THE SOFTWARE, UNDER ANY KIND OF
# LEGAL CLAIM.
"""Generate docs/paper/tables.tex from summary/, the same source as the records.

WHY. The paper's two result tables were transcribed by hand from a records
snapshot, with a comment at the top naming the month they came from. That makes
the paper and the site two independent copies of one scoring run, and they drift
the moment either is rescored -- silently, because nothing checks. This reads
summary/ through the same parser the published pages use, so the paper cannot
disagree with them.

Numbers are never computed here. "Noisy" is the mean of the four degradations,
exactly as the records pages define it.

    evals/gen_paper_tables.py            # write docs/paper/tables.tex
    evals/gen_paper_tables.py --check    # exit 1 if it would change (for CI)
"""
from __future__ import annotations

import argparse
import csv
import functools
import glob
import importlib.util
import pathlib
import re as _re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONDS = ("reverb", "noise", "music", "babble")
#: (corpus, subset) per column group, in table order.
#: Both splits of both corpora. Dev is reported beside test rather than held
#: back: it is the larger TIMIT split and the one a system is tuned against, so
#: a gap between the two is itself a result.
CELLS = (("timit", "dev"), ("timit", "core_test"),
         ("buckeye", "dev"), ("buckeye", "test"))
#: The corpus spans its splits in the header, so the name is not repeated. The
#: register of each is given in the text and the caption.
CORPUS_LABEL = {"timit": "TIMIT", "buckeye": "Buckeye"}
SPLIT_LABEL = {("timit", "dev"): "dev", ("timit", "core_test"): "test",
               ("buckeye", "dev"): "dev", ("buckeye", "test"): "test"}
#: Kept for callers that want one flat name for a cell.
CELL_LABEL = {c: f"{CORPUS_LABEL[c[0]]} {SPLIT_LABEL[c]}" for c in CELLS}

#: WHAT TABLE 1 SHOWS, which is now less than what is scored. The table went to
#: one column, and one column holds four numeric columns, not sixteen. The two
#: TEST splits at the CLEAN condition are what it keeps. Everything else is
#: still scored, still in records/, and still in the supplement's tables, which
#: read CELLS rather than these.
#:
#: The prose follows the table: a figure quoted without naming a split is the
#: mean over these two cells, so a reader can check it against what is printed.
#: Robustness needs the degraded numbers and they are no longer here, so that
#: paragraph points at records/.
PAPER_CELLS = (("timit", "core_test"), ("buckeye", "test"))
#: Conditions Table 1 shows, as indices into the (clean, noisy) pair.
PAPER_CONDS = (0, 1)
#: How many conditions $F_1$ carries. MAE carries both, so degradation stays in
#: the table; the noisy $F_1$ pair is what a single column cannot hold once
#: both corpora are in, and it stays in the records. header, colspec and body
#: all read column_plan, so this is the one place the choice is made.
PAPER_F1_CONDS = 2
#: Whether Table 1 spends a column on the family tag. Off, the groups are
#: still there, split by rules in a fixed order the caption states, and the
#: width goes to the noisy $F_1$ pair instead.
PAPER_FAMILY_COL = True
#: Decimals on $F_1$. Two: the third never separated two systems that the
#: first two did not, and it cost a digit in eight columns.
PAPER_F1_DIGITS = 2
#: WER under each split and condition rather than one mean column in front.
#: The word table switches it on for its own plan and the phone table off, so
#: (b), which is Track 1 only, does not carry four columns of dashes.
_WER_IN_PLAN = False
#: What the rate column is called, WER on the word tier and PER on the phone
#: tier, where it is the phone error rate against the gold phones.
_RATE_LABEL = "WER"
#: Horizontal scale of the rate label, so it sets no column. "WER" is three
#: wide capitals, 14.7pt at the table size over two-digit rates 11.6pt wide;
#: "PER" is 12.1pt over the same numbers.
_RATE_SCALE = {"WER": "0.78", "PER": "0.80"}
#: Vertical rules between the numeric columns, at a quarter point so that
#: thirteen of them cost three points rather than five.
PAPER_RULES = True


#: The cell each system's grid is measured in. Clean TIMIT test, because
#: every system has it and the grid is a property of the decoder rather than
#: of the audio. measure_grid.py reports the same figures for every cell.
GRID_CELL = "en/timit/core_test/origin"


def load_measure_grid():
    spec = importlib.util.spec_from_file_location(
        "measure_grid", ROOT / "evals" / "measure_grid.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@functools.cache
def recipe_dirs() -> dict:
    """Tool name to recipe directory, walked the way measure_grid.systems() does.

    The leaderboard's `aligner` key is the recipe's `name:` field, and variants
    such as nemo_fa_conformer live under exps/, so the map is read from the
    configs rather than assumed to be evals/<kind>/<tool>.
    """
    out = {}
    for cfg in sorted(glob.glob(str(ROOT / "evals/*/*/config.yaml"))
                      + glob.glob(str(ROOT / "evals/*/*/exps/*/config.yaml"))):
        d = pathlib.Path(cfg).parent
        name = ""
        for ln in open(cfg):
            if ln.startswith("name:"):
                name = ln.split(":", 1)[1].strip()
                break
        out[name or d.name] = d
    return out


@functools.cache
def grid_label(tool: str, tier: str = "words") -> str:
    """The Grid cell: the step in ms that every boundary of `tool` sits on.

    MEASURED from the system's own hypotheses, never copied from a vendor's
    page, because two vendors have changed it between releases without saying
    so. A per-utterance frame, the torchaudio ratio trick, is shown as the
    stride it rescales, see below. A system written at 1 ms with no coarser lattice shows 1,
    and a dash means no lattice was found at all. Blank if the hypotheses are
    not on disk, which is a row the caption must not explain.
    """
    d = recipe_dirs().get(tool)
    if d is None:
        return ""
    hyp = d / GRID_CELL / "hyp.jsonl"
    if not hyp.is_file():
        return ""
    g = load_measure_grid().grid_of(str(hyp), cap=4000, key=tier)
    if not g["n"]:
        return ""
    if g["step"]:
        return str(g["step"])
    if g["frame"] is not None and g["frame_share"] >= 0.5:
        # Rounded to the millisecond, and that IS the stride rather than an
        # approximation of it, so no tilde. The per-file reading runs over
        # the stride because the ratio divides the whole file by the frames
        # the model kept after its receptive field ate the edges. TorchAudio
        # and MMS-FA emit floor((N-400)/320)+1 frames, checked on 190 of 190
        # clean TIMIT test files, so the stride is 320 samples and 20 ms while
        # the ratio reads 20.02 to 20.25 ms. BFA's CUPE stack is 256 samples,
        # 16 ms, losing 4.9 frames a file to its 120 ms windows, read 16.1 to
        # 17.4. FALCON multiplies its frame index by a constant 161.34 samples
        # in next_frame_classifier.py, a 10 ms frame read 10.08. None of the
        # readings is within a millisecond of a neighboring integer.
        return f"{g['frame']:.0f}"
    return "1" if g["written_at"] == "1 ms" else "--"


def load_tables_module():
    """update_public_tables owns display names, families and suppression.

    Imported rather than duplicated: a system renamed there must not keep its
    old name in the paper, and the rule that hides internal variants has to
    apply to both or the paper leaks what the site withholds.
    """
    spec = importlib.util.spec_from_file_location(
        "upt", ROOT / "evals" / "update_public_tables.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


#: THE $F_1$ THE PAPER REPORTS, and it is the label-checked one, not the
#: time-only score the segmentation literature uses. A time-only hit says a
#: hypothesis boundary landed within the tolerance of SOME reference boundary,
#: not that the system found the one it was meant to, and the share that
#: credits a neighbor runs from under 1% for the sharpest aligners to 70% for
#: Whisper. Reporting it would rank systems partly on an accident.
#:
#: STRICT at both tiers, so a boundary counts only when the units on both
#: sides are the aligned, same-labeled units. At the word tier that charges a
#: recognizer for timing a word it got wrong, which is what Track 2 is for. At
#: the phone tier it also charges a substitution, so on Buckeye, where 58.7% of
#: tokens are realized off their canonical form, part of the drop is
#: pronunciation rather than timing. The positional variant, which asks only
#: that the units correspond, is in records/ beside it: bnd_f1_pos.
#: Read at an EXPLICIT 20 ms rather than through the summary alias, which
#: was keyed to tolerance accuracy's 25 ms primary and printed a 25 ms
#: score under a 20 ms caption.
# THE TWO UTTERANCE EDGES ARE NOW IN. The label-checked columns beside these
# in the leaderboard, wbnd_f1_lbl_*, already put every INTERIOR boundary in
# the denominator, so a word the system misread already cost it the two
# boundaries beside that word. What they leave out is the first boundary and
# the last, which are a fifth of the word boundaries on TIMIT and the ones an
# aligner given the reference words can still get wrong. Counting them drops
# MFA on TIMIT from .73 to .64 and is the whole of the difference on Track 1.
F1_WORD = "wbnd_f1_all_20ms"
F1_PHONE = "bnd_f1_all_20ms"


def collect(kind: str, metric: str) -> dict:
    """``{tool: {cell: (clean, noisy_mean)}}`` for one metric, from summary/."""
    out: dict[str, dict] = {}
    for cell in CELLS:
        base = ROOT / "summary" / kind / "en" / cell[0] / cell[1]
        clean_p = base / "origin" / "leaderboard.csv"
        if not clean_p.is_file():
            continue
        clean, degraded = {}, {}
        for r in csv.DictReader(clean_p.open()):
            v = (r.get(metric) or "").strip()
            if v:
                clean[r["aligner"]] = float(v)
        for cond in CONDS:
            p = base / cond / "leaderboard.csv"
            if not p.is_file():
                continue
            for r in csv.DictReader(p.open()):
                v = (r.get(metric) or "").strip()
                if v:
                    degraded.setdefault(r["aligner"], []).append(float(v))
        for tool, c in clean.items():
            deg = degraded.get(tool, [])
            # All four conditions or none: a mean over three understates the
            # degradation and is not comparable across rows.
            out.setdefault(tool, {})[cell] = (
                c, sum(deg) / len(deg) if len(deg) == len(CONDS) else None)
    return out


def fmt(v, bold=False, digits=1, pad=0, lead_zero=True) -> str:
    """One cell. `pad` prepends invisible zeros so every entry in a column has
    the same width: 16.9 under 143.2 becomes \\phantom{0}16.9, which puts the
    decimal points in line without right-aligning the column away from its
    header. \\phantom reserves the width of a real digit, so it stays correct
    whatever the font does."""
    if v is None:
        return "--"
    s = f"{v:.{digits}f}"
    if not lead_zero and s.startswith("0."):
        s = s[1:]
    if bold:
        s = f"\\textbf{{{s}}}"
    return ("\\phantom{" + "0" * pad + "}" + s) if pad else s


def _extreme(rows, data, cell, idx, want_max=False):
    vals = [(data.get(t, {}).get(cell) or (None, None))[idx] for *_, t, _ in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return max(vals) if want_max else min(vals)


#: Family order for the paper's tables, weakest mechanism to strongest, ending
#: with the closed system. Deliberately NOT accuracy order: the results section
#: argues about families, and a table that reorders itself whenever a number
#: moves cannot be referred to by position in prose.
PAPER_FAMILY_ORDER = ["transducer", "ctc", "attention", "frame", "hmm", "proprietary"]

#: THE PAPER GROUPS BY WHAT A READER CAN GET, NOT BY ARCHITECTURE. The records
#: pages keep CTC, Frame, Attention, HMM and Transducer, which answer "how does
#: it place a boundary"; Table 1 answers "can I run this, and on what terms",
#: which is the question that decides whether a row is usable at all.
#:
#: OpenS is reproducible: source, weights and a published recipe over described
#: data, so the system can be rebuilt rather than only run. OpenW is a released
#: checkpoint behind published inference code whose training data is not
#: published -- the Whisper and Qwen3 families and Parakeet. API is a service.
#:
#: A ONE-STEP row is labeled by everything it runs, so WhisperX-as-ASR is
#: OpenW: wav2vec2 places its boundaries but Whisper has to decode first. A
#: TWO-STEP row is labeled by its ALIGNER, which is the part the row exists to
#: test and the same convention fam() already uses for the architecture column.
PAPER_AVAIL = {
    # Reproducible end to end.
    "mfa": "opens", "mfa2": "opens", "charsiu": "opens", "maps": "opens",
    "bfa": "opens", "falcon": "opens", "nemo_fa": "opens",
    "nemo_fa_conformer": "opens", "torchaudio_fa": "opens",
    "torchaudio_asr": "opens", "mms_fa": "opens", "whisperx": "opens",
    "unity2": "opens", "neufa": "opens",
    # A checkpoint you can download and nothing more.
    "whisper3": "openw", "whisper_ts": "openw", "stable_ts": "openw",
    "crisperwhisper": "openw", "crisperwhisper_fa": "openw",
    "qwen3_asr": "openw", "qwen3_fa": "openw", "parakeet_tdt": "openw",
    # Whisper decodes and wav2vec2 times it, so the row needs both.
    "whisperx_asr": "openw",
}
PAPER_AVAIL_ORDER = ["opens", "openw", "api"]
#: What the column prints. ONE Open group: the split into OpenS and OpenW
#: cost a rule and a label in every block for a distinction the caption makes
#: in a sentence, naming the open-source members and calling the rest open
#: weights. _fam_rank merges the two the same way, so a block sorts worst to
#: best across all of Open.
PAPER_AVAIL_LABEL = {"opens": "Open", "openw": "Open", "api": "API"}

#: Shorter family labels for the paper only. "Attention" and "Transducer" set
#: the width of the family column on their own, and that column is pure
#: overhead in a table already fighting for a single column; the records pages
#: keep the full words, where width is free.
PAPER_FAMILY_LABEL = {"transducer": "Transducer"}

#: The ALIGNER half of a two-step family, paper only. A composite such as
#: "Open -> Attention" is the widest entry in the column and therefore sets
#: its width, and the column is pure overhead in a table already fighting for
#: a single page. Abbreviating here shortens the composites without touching
#: the Track 1 rows, which still read "Attention" in full.
PAPER_FAMILY_RIGHT = {"attention": "Attn."}

#: Names for the ROTATED family column, where the label's length is a row
#: height rather than a column width. A run of one row is only as tall as one
#: row, so "Transducer" standing alone would set that row four times taller
#: than its neighbors.
FAM_ROT = {"Transducer": "Trans.", "Attention": "Attn."}

#: Whether the family tag is turned on its side. Measured, because the
#: obvious way of doing it fails: a row is 6.32pt at arraystretch 0.79 over an
#: 8pt baseline, while rotated "Frame" at \scriptsize is 17.88pt and even
#: "API" at \tiny is 8.06pt, so no tag fits in one row. Nine of the seventeen
#: runs here ARE one row, since HMM is only MFA and so on, and smashing them
#: to fit printed three tags on top of each other.
#:
#: So a run is smashed only when it is tall enough to hold its tag, and a
#: short run keeps the rotated box at its natural height, which grows that row
#: to fit. The table pays a few points of height and every tag stays legible.
FAM_ROTATE = True
#: Rows a run needs before its tag is turned on its side. Measured: a run of
#: three is 18.96pt against the 17.88pt of the longest tag, "Frame", so three
#: always fits and nothing shorter does. A shorter run keeps its tag upright.
#: Two runs of one, side by side, is the case that decides this. Their tags
#: are 6.32pt apart and each wants 11.28pt even shrunk to \tiny, so rotating
#: both prints "API" through "HMM"; letting the rows grow instead adds 23pt to
#: the table, which pushes it off its column by 17.89pt and past the
#: references. Upright is the only one of the three that is legible AND fits.
FAM_ROTATE_MIN = 3


def fam_runs(rows, m):
    """`[(family, first row index, length)]` over consecutive equal families.

    A family is printed once per run and the rest of the run is blank, which
    is what the rule below it already implies. Runs are computed per call, so
    a block heading always breaks one.
    """
    out = []
    for i, r in enumerate(rows):
        f = _fam_short(m, r[3])
        if out and out[-1][0] == f:
            out[-1][2] += 1
        else:
            out.append([f, i, 1])
    return out


def _fam_short(m, tool: str) -> str:
    """The family as the rotated column prints it.

    A two-step row is given its ALIGNER's family alone. The composite that
    used to sit here, "Open $\\to$ API", says what the System column already
    spells out with the arrow, and as a rotated singleton it was the tallest
    thing in the table.
    """
    lab = unshrink(_fam_label(m, tool))
    if "$\\to$" in lab:
        lab = lab.split("$\\to$")[-1].strip()
    return FAM_ROT.get(lab, lab)


def _avail(m, tool: str) -> str:
    """OpenS, OpenW or API for `tool`. See PAPER_AVAIL."""
    if m.fam(tool) == "proprietary":
        return "api"
    parts = m.cascade_parts(tool)
    base = parts[0] if parts else tool
    return PAPER_AVAIL.get(base, PAPER_AVAIL.get(tool, "openw"))


def _arch_label(m, tool: str) -> str:
    """The ARCHITECTURE label, which the supplement keeps and Table~1 does not.

    The bias table exists to argue that the word-start lag belongs to CTC
    rather than to who sells the system, and a reader cannot check that
    against a column that says OpenS. Table~1 answers a different question and
    groups by availability; see PAPER_AVAIL.
    """
    return m.fam_label(tool, arrow=r"$\to$", label=PAPER_FAMILY_LABEL,
                       right=PAPER_FAMILY_RIGHT)


def _fam_label(m, tool: str) -> str:
    """The availability label, set a size down.

    It is a taxonomy label repeated down a group, not a measurement, so it is
    the cheapest column to take width from -- and taking it here means the
    numbers keep the table's size. Both tables use it, so they stay a matched
    pair.
    """
    return PAPER_AVAIL_LABEL[_avail(m, tool)]


def _fam_rank(m, tool: str) -> int:
    # Open before API, and the two kinds of open are one group; see
    # PAPER_AVAIL_LABEL.
    return 0 if _avail(m, tool) != "api" else 1


def _base_name(label: str) -> str:
    """The system without its version: "MFA 3.4" and "MFA 2.0" share one base."""
    parts = label.replace("$^\\dagger$", "").replace("\\smash{$^\\dagger$}", "").split()
    while parts and parts[-1].replace(".", "").isdigit():
        parts.pop()
    return " ".join(parts) or label


def _recognizer(m, tool: str, label: str) -> str:
    """Which ASR produced this row's words, for grouping track 2.

    A two-step row is named "<recognizer> -> <aligner>", so the left half is the
    recognizer; a one-step row is its own. Grouping on it puts every system that
    read the same words together, which is the comparison track 2 exists to make
    -- and it keeps Whisper's own timings beside the same words re-aligned.
    """
    left = label.split(" \u2192 ")[0].strip()
    # First token only: "Whisper large-v3" and "Whisper -> WhisperX" are the
    # same recognizer and must sit together -- that pair is the whole point of
    # scoring WhisperX end to end, since it says what re-aligning Whisper's own
    # words is worth. Keying on the full name would split them.
    return left.split()[0] if left.split() else left



#: The recognizer every two-step row shares. Named once in the block header
#: instead of on each row -- it is the constant, and repeating it cost more
#: width than the family column.
DEFAULT_ASR = "Qwen3"


def aligner_only(label: str) -> str:
    """A two-step row reduced to its aligner.

    Every cascade reads the same Qwen3-ASR transcript except one, which reads
    Whisper's; that exception is starred and explained in the caption rather
    than given a prefix of its own. The block header carries the recognizer, so
    the rows carry only what distinguishes them.
    """
    if " \u2192 " not in label:
        return shrink_long(label)
    left, right = label.split(" \u2192 ", 1)
    if left == DEFAULT_ASR:
        return shrink_long(right)
    # A row reading a DIFFERENT transcript names its recogniser inline. A single
    # "*" worked while WhisperX was the only exception; with a second one it
    # stops identifying anything, and a footnote key the reader has to hold is
    # worse than four characters in the cell.
    return "{\\tiny " + left + "}$\\!\\to\\!$\\," + shrink_long(right)


def cascade_label(label: str) -> str:
    """A two-step row as "<recognizer> $\\to$ <aligner>", both halves always named.

    Naming only the exceptions left the block a mix: a bare "MFA", meaning the
    Qwen3 cascade, sat directly above "Parakeet-TDT -> MFA", so a reader had to
    carry the rule that an unprefixed row reads Qwen3. Spelling the recognizer on
    every row costs a few characters and removes the rule. `aligner_only` still
    strips it for SORTING, which is what keeps the two cascades of one aligner
    adjacent.
    """
    if " \u2192 " not in label:
        return shrink_long(label)
    left, right = label.split(" \u2192 ", 1)
    return left + " $\\to$ " + shrink_long(right)


#: Paper-only short names. The records keep the long forms -- there a reader is
#: scanning one track and needs "TorchAudio (ASR)" to tell it from the aligner.
#: In Table 2 the track heading already says it, so the qualifier is width spent
#: on something the surrounding row states. The caption carries what is lost.
PAPER_SHORT = {
    "torchaudio_asr": "TorchAudio",
    # The one-step ROW names the exact model; the cascade PREFIX stays "Whisper",
    # since PAPER_RECOGNIZER rewrites the left half of an arrow separately and
    # "Whisper large-v3 -> WhisperX" would not fit the System column.
    "whisper3": "Whisper",
    # Named by CHECKPOINT now that only one of the two is shown. The frame
    # step it used to be named for is in the Grid column, and a row called
    # "NeMo-FA 40 ms" beside a Grid cell reading 40 says it twice. The full
    # tag is stt_en_conformer_ctc_large; the supplement spells it out.
    "nemo_fa_conformer": "NeMo-FA",
    # SHORT NAMES, now that the table carries clean and noisy for two corpora
    # and the System column is the only one that can give width back. The
    # vendor alone names an endpoint; the model behind each is spelled out
    # once in the caption, where it costs a line instead of a column.
    "whisper_ts": "Whisper-ts",
    # Shortened for the table, where the System column sets the width every
    # other column then has to live inside. Figure 1 puts the full name back
    # through BIAS_SHORT, having room for it.
    "crisperwhisper": "CrisperW",
    "crisperwhisper_fa": "CrisperW",
    "parakeet_tdt": "Parakeet",
    "google_stt_chirp2": "Google",
    "elevenlabs": "ElevenLabs",
    "aws": "Amazon",
    "assemblyai": "AssemblyAI",
    "ibm": "IBM",
    "azure": "Azure",
    "deepgram": "Deepgram",
    "speechmatics": "Speechmatics",
}

#: Bibliography key per system, appended to its row label in the tables. Olign is
#: uncited on purpose: it is described in this paper and has no prior publication.
PAPER_CITE = {
    # The commercial endpoints. Each cites the vendor's documentation for the
    # model that answered, with the served build in the entry's note where the
    # vendor reports one. A row that names a service and cites nothing reads
    # as hearsay beside the open rows, all of which carry a paper.
    "deepgram": "deepgram2026nova3",
    "assemblyai": "assemblyai2026universal",
    "elevenlabs": "elevenlabs2026scribe",
    "google_stt_chirp2": "google2026chirp2",
    "speechmatics": "speechmatics2026batch",
    "ibm": "ibm2026watson",
    "azure": "microsoft2026azure",
    "aws": "amazon2026transcribe",
    "bfa": "rehman2025bfa",
    "charsiu": "zhu2022charsiu",
    "maps": "kelley2024maps",
    "mfa": "mcauliffe2017mfa",
    "crisperwhisper": "zusag2024crisperwhisper",
    "crisperwhisper_fa": "zusag2024crisperwhisper",
    "whisperx": "bain2023whisperx",
    "whisperx_asr": "bain2023whisperx",
    "whisper3": "radford2023whisper",
    "torchaudio_fa": "yang2022torchaudio",
    "torchaudio_asr": "yang2022torchaudio",
    "parakeet_tdt": "xu2023tdt",
    # The aligner checkpoint is the model of Mu et al., whose abstract gives
    # QwenLM/Qwen3-ASR as where the checkpoint lives. The method paper is
    # what a reader of this row wants; the ASR row keeps the release note.
    # The report that released the aligner and the paper behind it, both on
    # the Track 1 row, so the Q -> Qwen3-FA row below cites nothing new.
    "qwen3_fa": "qwen2026asr,mu2026llmfa",
    "qwen3_asr": "qwen2026asr",
    "stable_ts": "jianfch2023stablets",
    "neufa": "li2022neufa",
    # The UnitY2 alignment extractor ships with SeamlessM4T v2 and is
    # described in that paper, so the system cites the model it came from.
    "unity2": "seamless2023",
    "falcon": "rousso2026falcon",
    # torchaudio ships the bundle; the checkpoint and its training are the
    # MMS paper, and that is what a reader needs to look up.
    "mms_fa": "pratap2024mms",
    "nemo_fa": "rastorgueva2023nfa",
    "nemo_fa_conformer": "rastorgueva2023nfa",
    "whisper_ts": "louradour2023whisperts",
    # Olign is a closed commercial service; the vendor page is the only
    # citable description. "olign" covers the cascades, which cite_for()
    # reaches by splitting on "_on_"; the Track 1 row is named olign_noisy.
    "olign": "olewave2024olign",
    "olign_noisy": "olewave2024olign",
}


#: Rows the PAPER omits. The records keep them -- MFA 2.0 is a real published
#: result and someone comparing against it needs the number -- but in the paper
#: it earns less than the line it costs: it is strictly worse than 3.4 on every
#: cell, and the 2.0-vs-3.4 progression is not a finding this paper makes.
PAPER_SUPPRESS = {"mfa2", "mfa2_on_qwen3asr",
                  # NeMo-FA over TWO checkpoints was two rows of one aligner,
                  # and the pair earned its width only while the grid was
                  # being argued from prose. The Grid column now carries that,
                  # so the paper keeps the conformer checkpoint and the 80 ms
                  # FastConformer stays in records/ -- where the 32 dropped
                  # short Buckeye utterances are documented too.
                  "nemo_fa",
                  # Parakeet-TDT -> MFA only. Results asserts that the
                  # transcript effect replicates through MFA but quotes no
                  # number from it, so the row costs a line and the evidence
                  # stays in records/. Parakeet-TDT -> Olign is kept: it is
                  # the best cascade in the table, so dropping it would hide
                  # the configuration the benchmark's own numbers pick out.
                  "mfa3_on_parakeettdt",
                  # The commercial endpoints are IN the table. Only the
                  # variants stay out: deepgram_nova2 is an ablation of
                  # deepgram (80 ms against 10 ms, kept in records/), and
                  # google_stt is the v1 recipe that google_stt_chirp2
                  # supersedes.
                  "deepgram_nova2", "google_stt",
                  # NeuFA is held out while its checkpoint is in question. The
                  # cells are swept and stay in records/, so restoring the row
                  # is deleting this line and regenerating.
                  "neufa",
                  # TWO-STEP CASCADES, all but five. Sixteen of them mostly
                  # restate their own Track 1 row -- the transcript swap moves
                  # a median 0.5 ms, which the Results section already reports
                  # as an aggregate over fourteen aligners rather than from any
                  # single line. What survives is one cascade per boundary
                  # family, so a reader can still read the families against
                  # each other: Whisper -> WhisperX (CTC), Qwen3-ASR ->
                  # Qwen3-FA (attention), Qwen3-ASR -> MFA (HMM), and the two
                  # Olign cascades, which differ in their RECOGNIZER rather
                  # than their aligner and are the pair the transcript
                  # argument rests on.
                  #
                  # Every suppressed row is in records/, and no number quoted
                  # in the Results section comes from one.
                  "nemo_fa_on_qwen3asr", "nemo_fa_conformer_on_qwen3asr",
                  "whisperx_on_qwen3asr", "bfa_on_qwen3asr",
                  "torchaudio_fa_on_qwen3asr", "mms_fa_on_qwen3asr",
                  "stable_ts_on_qwen3asr", "crisperwhisper_fa_on_qwen3asr",
                  "unity2_on_qwen3asr", "charsiu_on_qwen3asr",
                  "maps_on_qwen3asr"}

#: Tools that are handed the GOLD phone sequence and only place its boundaries.
#: Every other phone row derives its own phones from the words, so such a row
#: is answering an easier question and is marked in the table rather than
#: ranked silently beside them.
#: TorchAudio is NOT in this set although its phone tier runs under mode B.
#: That is plumbing: the worker ignores the supplied sequence and aligns the
#: one eSpeak G2P derives from the transcript (evals/aligners/torchaudio_fa/
#: worker.py, phones()), which is why its PER is 34%, not 0. It carried the
#: dagger from the revision before that change and was wrongly described as
#: given the gold sequence in the 2026-09 draft.
#: FALCON is mode B and nothing else. Its English path resolves only for
#: lang=english, mode=phoneme, annotation=phn, and everything else falls
#: through to a Dutch panphon G2P that turns "wage" into y aa g ae, so the
#: phone sequence has to be supplied. Its adapter docstring already claimed
#: it was marked here. It was not, so it sat unmarked at 21.0 ms beside
#: Charsiu at 21.5 and MAPS at 16.9, both of which derive their own phones.
PHONE_MODE_B = {"falcon"}

#: Recogniser names as they should read in a cascade label. The tool key is not
#: a display name: `olign_on_parakeettdt` was rendering as "parakeettdt".
#: The key is whatever the left half of the arrow ALREADY reads as, which for
#: qwen3asr is the prettified "Qwen3" rather than the tool id -- so the entry
#: that fires is "Qwen3", and the raw key is kept only as a safety net.
#: "Qwen3" alone names Alibaba's text LLM series; the paper's prose says
#: Qwen3-ASR everywhere, and so should the table.
#: The left half of a two-step row's name. An initial where the recognizer is
#: named elsewhere on the row's own page, the full name where it is not. The
#: right half names the aligner, which is what a two-step row is being read
#: for, and the caption names every recognizer once.
PAPER_RECOGNIZER = {"qwen3asr": "Q", "Qwen3": "Q",
                    "Google Chirp 2": "G", "Google": "G",
                    "Whisper": "W",
                    "parakeettdt": "P", "Parakeet-TDT": "P"}

#: Trailing "3.4" / "1.0" / "2.0" on a system name. Stripped for the paper: with
#: one MFA and one Olign in the table the version distinguishes nothing, and the
#: exact builds are named once in Table 1's caption where they belong.
_VERSION_RE = _re.compile(r"\s+v?\d+\.\d+$")

#: ...but ONLY for those two. The rule was written for local tools whose build
#: the caption pins, and applied blindly it also ate the model out of a
#: commercial row: "AssemblyAI Universal 3.5" came out as "AssemblyAI
#: Universal", which names a family rather than the thing that answered. For an
#: endpoint the model version IS the identity -- it is the only claim such a row
#: can honestly make, since the service behind the name can change -- so it
#: stays.
_VERSION_IN_CAPTION = ("MFA", "Olign")


def _drop_version(name: str) -> str:
    if not name.startswith(_VERSION_IN_CAPTION):
        return name
    return _VERSION_RE.sub("", name)

#: No system name is shrunk any more. The shrink bought width when both tables
#: had to fit one column; spanning the page they do not need it, and a name at
#: full size beside full-size numbers is what the rows deserve. Kept as a dial
#: rather than deleted, so a future column-width table can turn it back on.
#: Back on at 20 since the Grid column arrived: with it the word tier ran
#: 14.7pt past the text block, and the width sat in the versioned API names.
_SHRINK_AT = 20


def cite_for(tool: str) -> str:
    """``~\\cite{...}`` for a system, or "" if it has none.

    A cascade is credited to its ALIGNER: `mfa3_on_qwen3asr` is MFA doing the
    aligning, so it carries MFA's citation. The recogniser that supplied the
    words is named in the row itself.
    """
    key = PAPER_CITE.get(tool)
    if key is None and "_on_" in tool:
        key = PAPER_CITE.get(tool.split("_on_")[0])
    if key is None:
        base = tool.split("_on_")[0].rstrip("0123456789")
        key = PAPER_CITE.get(base)
    # A size down: the reference is provenance, not part of the system's name,
    # and at 16 numeric columns the width it costs comes off the numbers.
    return ("\\,{\\tiny\\cite{" + key + "}}") if key else ""


#: The initials a two-step row is written with, spelled out under the heading
#: that introduces them, at the same size as the system names it explains.
#: \textbf on the letter so the eye lands on what it has to match. Two lines,
#: because at this size the four entries run 37pt past a single column.
_CASCADE_KEY = (r"{\fontsize{8pt}{8.8pt}\selectfont\textup{"
                r"\begin{tabular}{@{}l@{}}"
                r"\textbf{W} Whisper, as in Crisper\textbf{W}\quad"
                r"\textbf{Q} Qwen3-ASR\\"
                r"\textbf{G} Google Chirp~2\quad\textbf{P} Parakeet-TDT"
                r"\end{tabular}}}")

#: Whether disp_paper applies the paper's short names. On for Table 1 and
#: Figure 1, whose caption spells the short names out, and off for the
#: supplement, which stands on its own and has no such legend.
_SHORT_NAMES = False


def disp_paper(m, tool: str) -> str:
    """The display name, with the paper's shortenings applied when
    _SHORT_NAMES is on and the version dropped either way."""
    name = (PAPER_SHORT.get(tool, m.disp(tool)) if _SHORT_NAMES else m.disp(tool))
    left, sep, right = name.partition(" \u2192 ")
    if sep:
        left = PAPER_RECOGNIZER.get(left, left) if _SHORT_NAMES else left
        return left + sep + _drop_version(right)
    return _drop_version(left)


def unshrink(label: str) -> str:
    """`label` with any size wrapper removed, for sorting and for prose.

    Sorting on the wrapped form compares a leading "{", which sorts after every
    letter in ASCII, so a shrunk name dropped silently to the end of its family.
    """
    return _re.sub(r"\{\\(?:scriptsize|tiny) ([^}]*)\}", r"\1", label)


def shrink_long(name: str, measure: str | None = None) -> str:
    """Set an over-long system name one size down, so it stops setting the
    column width for every other row.

    `measure` is the text whose length is judged when `name` carries markup,
    so a cascade's arrow counts as one character and not five.
    """
    n = len(measure if measure is not None else name)
    return "{\\scriptsize " + name + "}" if n >= _SHRINK_AT else name


def tex_name(label: str) -> str:
    """A cascade name, typeset compactly.

    "Qwen3 -> MFA 3.4" is the widest kind of entry in the word table, and the
    two spaces around the arrow plus a full-size arrow cost more room than the
    aligner name itself. The recognizer is set smaller and the arrow tightened
    with \\!: the recognizer is the same for nearly every two-step row, so it is
    the half a reader skims, while the aligner is what distinguishes them.
    """
    if " \u2192 " not in label:
        return shrink_long(label)
    left, right = label.split(" \u2192 ", 1)
    # Tight on the left, a thin space on the right: the arrow belongs to the
    # recognizer it points away from, and the aligner name needs air or it reads
    # as one word with the arrow.
    return "{\\tiny " + left + "}$\\!\\to\\!$\\," + shrink_long(right)


#: Paper-only ordering nudges inside a family. Rows otherwise sort alphabetically
#: by displayed name, which put CrisperWhisper above Whisper. Whisper leads the
#: pair instead: CrisperWhisper is a Whisper derivative, so reading the base
#: model first shows what its retraining bought. Keys are tool names, so the
#: one-step entries here do not touch `crisperwhisper_fa` in Track 1.
#:


_CITE_RE = _re.compile(r"\\,\{\\tiny\\cite\{([^}]*)\}\}")


def drop_repeat_cite(label: str, seen: set | None) -> str:
    """`label` with its citation removed if that key has already been cited.

    A system is referenced once per table, on its first row. Table 1 lists most
    of them twice, once given the reference transcript and again reading an
    ASR's words, and a second [n] on the same work is width spent saying nothing
    -- the more so once the two-step rows also carry a recognizer name.
    """
    if seen is None:
        return label
    mm = _CITE_RE.search(label)
    if mm is None:
        return label
    keys = mm.group(1).split(",")
    unseen = [k for k in keys if k not in seen]
    seen.update(keys)
    if not unseen:
        return _CITE_RE.sub("", label)
    if len(unseen) < len(keys):
        return _CITE_RE.sub(lambda _m: "\\,{\\tiny\\cite{" + ",".join(unseen) + "}}", label)
    return label


def order(m, tools, mae, by_recognizer=False, f1=None):
    """Rows grouped, most accurate first inside each group.

    Two orderings, for two questions. Track 1 groups by how a system decides
    boundaries, because that is what the results section compares. Track 2
    groups by whose words it was working from, because a timing difference
    between two rows only means something when the transcript is the same.
    Within either grouping, systems that differ only by version stay in version
    order rather than accuracy order -- MFA 2.0 above MFA 3.4 reads as a
    progression, and reversing it to put the better number first hides that.
    """
    rows = []
    for t in tools:
        if not any(mae.get(t, {}).get(c) for c in PAPER_CELLS):
            continue
        # No held-out marker on the row. One system carries the caveat and a
        # symbol on every table asks the reader to look up a footnote to learn
        # that; the text says it once instead.
        label = tex_name(disp_paper(m, t)) + cite_for(t)
        rows.append((_fam_rank(m, t), _fam_label(m, t), label, t, disp_paper(m, t)))

    def acc(t):
        return (mae.get(t, {}).get(PAPER_CELLS[0]) or (9e9,))[0]

    # rank each group by its best member, so groups stay accuracy-ordered even
    # though members within a group are not
    def group_of(r):
        return _recognizer(m, r[3], r[2]) if by_recognizer else r[0]

    if by_recognizer:
        # Groups ordered by their best member, so the strongest transcript
        # source leads; rows within a group by accuracy, then version.
        best_in = {}
        for r in rows:
            g = group_of(r)
            best_in[g] = min(best_in.get(g, 9e9), acc(r[3]))
        rows.sort(key=lambda r: (best_in[group_of(r)], str(group_of(r)),
                                 _base_name(r[2]), r[2]))
    else:
        # A starred variant leads its base name: WhisperX* reads a different
        # transcript from WhisperX, and putting the exception first makes the
        # pair read as "this one differs, and here is the baseline".
        # Sort on the name AS DISPLAYED. "Qwen3 -> WhisperX" and "Whisper ->
        # WhisperX" have different full labels but both show as WhisperX, so
        # sorting the full label separated the pair and the star tiebreak never
        # applied. The starred variant leads: it is the exception, and the
        # unstarred row beneath it is the baseline to read it against.
        def shown(r):
            return _base_name(
                unshrink(aligner_only(m.disp(r[3]))).replace("$^{*}$", ""))

        # EVERY group now sorts by accuracy, worst at the top and best at the
        # bottom, so a block is read downwards and the row to beat is the last
        # one in it. The measure is the mean clean MAE over the cells the table
        # prints, which is the paper's own definition of "the mean" everywhere
        # else. This replaced a hand-placed order that kept the NeMo and
        # WhisperX pairs adjacent; the pairing is worth less than a block a
        # reader can scan in one direction, and both rows are still in it.
        def acc_mean(t):
            vals = [(mae.get(t, {}).get(c) or (None,))[0] for c in PAPER_CELLS]
            vals = [v for v in vals if v is not None]
            # No number sorts to the top, with the worst: it is not evidence
            # of accuracy and must not be read as the best row in its group.
            return sum(vals) / len(vals) if vals else 9e9

        def rank(t):
            """Where a row sits inside its family. MAE descending by default,
            worst first. With `f1` given it is $F_1$ on the FIRST printed cell,
            clean TIMIT, ASCENDING, which is the same direction: worst at the
            top and the row to beat at the bottom of its block. A mean over
            both corpora was used first and put rows out of order against the
            column beside them, which reads as a mistake even when the mean is
            right."""
            if f1 is None:
                return -acc_mean(t)
            v = (f1.get(t, {}).get(PAPER_CELLS[0]) or (None,))[0]
            # No number sorts to the top, with the worst, exactly as it does
            # for MAE: an absent $F_1$ is not evidence of accuracy and must
            # not be read as the best row in its group.
            return v if v is not None else -9e9

        rows.sort(key=lambda r: (_fam_rank(m, r[3]),
                                 rank(r[3]),
                                 shown(r),
                                 0 if "*" in aligner_only(m.disp(r[3])) else 1,
                                 r[2]))
    return rows


def best_values(rows, mae, f1, w=None) -> dict:
    """The winning value per column, for bolding.

    Split out so a track that prints in several blocks can bold against the
    WHOLE track. Track 2 is drawn as one-step and two-step separately, and
    letting each block bold its own best put two bold numbers in every column,
    which reads as two winners.
    """
    bestv = {}
    for c in PAPER_CELLS:
        for cond in PAPER_CONDS:
            bestv[("m", c, cond)] = _extreme(rows, mae, c, cond)
            bestv[("f", c, cond)] = _extreme(rows, f1, c, cond, want_max=True)
            # A rate is not bolded; an F1 in the rate slot is, as a max.
            bestv[("w", c, cond)] = (_extreme(rows, w, c, cond, want_max=True)
                                     if w is not None else None)
    return bestv


def col_pads(rows, mae, f1, wer=None) -> dict:
    """Integer digits of the widest entry in each column.

    Computed over ALL the table's rows, not one block, so a column stays a
    single width down the whole table -- Track 1 and Track 2 are drawn by
    separate calls but share columns.
    """
    widest = {}
    for cell, metric, cond in column_plan():
        src = {"m": mae, "f": f1, "w": wer or {}}[metric]
        n = 1
        for r in rows:
            v = (src.get(r[3], {}).get(cell) or (None, None))[cond]
            if v is not None:
                n = max(n, len(f"{v:.0f}"))
        widest[(metric, cell, cond)] = n
    return widest


def col_slack(pads: dict) -> dict:
    """Digits a column is NARROWER than its partner, for symmetric padding.

    Clean and noisy must end up the same width or their split header cannot
    centre over the pair -- but that width must be added as column padding, half
    on each side. Adding it as \\phantom inside the cells (which is what dot
    alignment uses) is not equivalent: the phantom sits on the left, so every
    number in the narrower column is pushed right by half a digit, measured at
    +2.24pt and visible as the MAE columns leaning right.
    """
    slack = {}
    for cell, metric, cond in column_plan():
        # Over the conditions actually shown: with the noisy half gone there is
        # no partner to match, and reaching for cond 1 raised a KeyError.
        pair = max(pads[k] for k in ((metric, cell, c) for c in PAPER_CONDS) if k in pads)
        slack[(metric, cell, cond)] = pair - pads[(metric, cell, cond)]
    return slack


def n_lead(grid: str | None, wer: dict | None = None) -> int:
    """Columns before the numbers: Family, System, and Grid and WER if shown."""
    return ((2 if PAPER_FAMILY_COL else 1) + (1 if grid else 0)
            + (1 if wer is not None and not _WER_IN_PLAN else 0))


def body(rows, mae, f1, m=None, with_pipeline=False, family_col=True,
         f1_digits=None, f1_conds: int = 2, aligner_names: bool = False,
         bestv: dict | None = None, pads: dict | None = None,
         seen_cites: set | None = None, grid: str | None = None,
         wer: dict | None = None, wfmt: tuple | None = None) -> list[str]:
    """One \\\\-terminated line per system: MAE(clean,noisy) F1(clean,noisy) per cell.

    `grid` names the tier whose timestamp grid fills the Grid column, "words"
    or "phones", or None for no such column.

    `wfmt` is (digits, lead_zero) when the rate slot carries an F1 instead.

    `wer` fills the WER column, the plain mean over the two test splits, which
    is the paper's convention wherever a number is not given per split. It is
    a Track 2 number by construction: a Track 1 row is handed the reference
    words, so it has no recognition error to report and its cell is a dash
    rather than a zero, which would read as a perfect recogniser.
    """
    if bestv is None:
        bestv = best_values(rows, mae, f1)
    if pads is None:
        pads = col_pads(rows, mae, f1)
    _runs = fam_runs(rows, m) if m else []
    runs = {r[1]: (r[0], r[2]) for r in _runs} if family_col else {}
    # Last row of each run, so a rule can close the group. The final run needs
    # none: a block heading or the table's own rule already closes it.
    ends = {r[1] + r[2] - 1 for r in _runs[:-1]}
    out = []
    for _i, (_, family, label, t, _) in enumerate(rows):
        if aligner_names:
            # The same length rule as the one-step names. Without it the
            # widest cell in the tier was "Qwen3-ASR -> Qwen3-FA" plus its
            # citation, 15pt past the next, and it set the column alone.
            name = cascade_label(disp_paper(m, t))
            left, _, right = name.partition(" $\\to$ ")
            measure = name.replace(" $\\to$ ", "\u2192")
            if right:
                # Both halves in full, the arrow carrying only its own math
                # space. A letter for the recognizer was tried and read as a
                # code, and the column has the room now that the Qwen3-FA
                # citation sits on its Track 1 row.
                name = left + "$\\to$" + right
            label = shrink_long(name, measure) + cite_for(t)
        label = drop_repeat_cite(label, seen_cites)
        # Emitted straight off column_plan, so the body cannot drift out of
        # step with the header spans above it.
        cells = []
        for cell, metric, cond in column_plan():
            if metric == "f" and f1_conds == 1 and cond == 1:
                continue
            src = {"m": mae, "f": f1, "w": wer or {}}[metric]
            v = (src.get(t, {}).get(cell) or (None, None))[cond]
            digits = (f1_digits or PAPER_F1_DIGITS) if metric == "f" else 1
            pad = pads[(metric, cell, cond)] - (len(f"{v:.0f}") if v is not None else 1)
            lz = metric != "f"
            if metric == "w" and wfmt is not None:
                # An F1 riding in the rate slot, its own digits and no leading
                # zero, but padded to the width the rates set so the column has
                # ONE right edge. Left to itself the F1 is a digit narrower
                # than a rate, ".40" against "10.8", and a centred cell puts
                # the two blocks half a digit apart, which is what reads as the
                # column not lining up. A phantom digit is exactly the
                # difference, since a period is half the width of a digit.
                digits, lz = wfmt[0], wfmt[1]
                width = pads[(metric, cell, cond)] + 1 + 1     # ints, dot, one decimal
                pad = width - ((len(f"{v:.0f}") if lz and v is not None else 0) + 1 + digits)
            cells.append(fmt(v, v is not None and v == bestv[(metric, cell, cond)],
                             digits, max(0, pad), lead_zero=lz))
        if with_pipeline:
            lead = f"{family:<10} & {m.pipe(t) or '---':<9} & {label:<24}"
        elif family_col:
            lead = f"{family:<10} & {label:<24}"  # replaced below by the run
        elif family_col is None:
            # Column present but EMPTY. Track 2 is grouped by recognizer, not by
            # family, so a family label there would name a grouping the rows do
            # not follow -- worse than no label. The cell is kept so the two
            # halves of the table stay in the same columns.
            lead = f"{'':<10} & {label:<24}"
        else:
            lead = f"{label:<24}"
        if runs:
            # One rotated tag per run of equal families, on the run's first
            # row, blank on the rest.
            if _i in runs:
                f, n = runs[_i]
                if FAM_ROTATE and n >= FAM_ROTATE_MIN:
                    # Smashed because the run is known to be taller than the
                    # tag, so the zero height costs nothing and keeps the row
                    # spacing exactly as the unrotated rows have it.
                    inner = (r"\smash{\rotatebox[origin=c]{90}{" + f + r"}}")
                else:
                    # A run too short for a rotated tag keeps it upright, a
                    # size down so "API" is 8pt and not the column's 11.
                    inner = r"{\tiny " + f + "}"
                # A run of one needs no \multirow, and asking for one cost a
                # 1.68pt overfull vbox apiece: multirow sets its content at
                # natural height, which is taller than a row compressed to
                # arraystretch 0.79.
                cell = (inner if n == 1 else
                        r"\multirow{" + str(n) + r"}{*}{" + inner + r"}")
            else:
                cell = ""
            lead = f"{cell:<34} & {lead.split('&', 1)[1].strip():<24}"
        if grid:
            lead += f" & {grid_label(t, grid):>9}"
        if wer is not None and not _WER_IN_PLAN:
            vs = [(wer.get(t, {}).get(cell) or (None, None))[0] for cell in PAPER_CELLS]
            vs = [v for v in vs if v is not None]
            # The same dash the Grid column sets for a system with no
            # lattice. An em-dash is the one thing this document does not set.
            lead += f" & {(f'{sum(vs) / len(vs):.1f}' if vs else '--'):>5}"
        out.append(lead + " & " + " & ".join(cells) + r"\\")
        if _i in ends:
            out.append(r"\cmidrule(lr){1-"
                       + str(n_lead(grid, wer) + len(column_plan())) + r"}")
    return out



#: Gaps that carry the header's grouping down into the body. Uniform padding
#: cannot do this: it separates the two columns INSIDE a metric pair exactly as
#: much as it separates MAE from $F_1$, so at sixteen columns a reader has no
#: cue for which pair a number belongs to. These put the space only where a
#: boundary is, which is why the pairs read as pairs.
#: Gaps that carry the header's grouping down into the body. Uniform padding
#: cannot do this -- it separates columns inside a pair exactly as much as it
#: separates one group from the next -- so the space goes only where a boundary
#: is, sized by how big that boundary is.
_GAP_METRIC = "0.4pt"      # $F_1$ | the rate slot, the innermost pair
_GAP_MAE = "0.6pt"        # MAE | $F_1$, which are read against each other
#: The phone table cannot pay for that. Its rate column holds three-digit PERs
#: where the word table holds two-digit WERs, so the same air across four
#: conditions runs it 3pt past the column. phone_table lowers this and restores
#: it on the way out.
_GAP_MAE_PHONE = "0.6pt"
_GAP_SPLIT = "1pt"      # dev pair | test pair, inside one condition
_GAP_COND = "1.4pt"         # the clean half | the noisy half, inside one corpus
_GAP_CORPUS = "1.4pt"   # TIMIT | Buckeye
#: Sized with TABLE_SIZE to fill the column rather than sit inside it. At
#: 6.6pt and gaps of 0.25, 1.5 and 2pt the word table measured 234.4pt in a
#: 244.7pt column, ten points of white margin; at 7pt with these gaps it is
#: 244.2pt. The tabular* below spreads what is still left over the numeric
#: columns, so the last of it goes between numbers and not beside them.

#: How far the MAE digits sit left of centre in their own column, pulling them
#: off the rule they share with $F_1$. Applied as -x before and +x after, so it
#: costs no width. Zero since the rules came: a three-digit MAE shifted 1.5pt
#: left overprinted the rule on its LEFT, the one it shares with the previous
#: condition's WER or with Grid, and the MAE header did the same. Centred, a
#: three-digit MAE clears both rules by the column separation and a two-digit
#: one by 1.7pt more.
_MAE_SHIFT = "0pt"


def corpus_order(cells=None) -> list:
    """Corpora in table order, each once."""
    out = []
    for cell in (PAPER_CELLS if cells is None else cells):
        if cell[0] not in out:
            out.append(cell[0])
    return out


def splits_of(corpus: str, cells=None) -> list:
    """That corpus's cells, in table order."""
    return [c for c in (PAPER_CELLS if cells is None else cells) if c[0] == corpus]


def column_plan() -> list:
    """Every numeric column, in order, as (cell, metric, condition).

    corpus > condition > split > metric. Each split shows its metrics side by
    side, MAE, then F1, then the rate slot, which on Track 1 is F1 at 50 ms
    and so sits beside the 20 ms F1, and a reader judges one system on one
    split of one corpus without crossing the table; the clean and noisy halves
    are then read against each other as blocks. The nesting lives here alone:
    header spans, column spec and body rows all derive from this list.
    """
    plan = []
    for corpus in corpus_order():
        for cond in PAPER_CONDS:
            for cell in splits_of(corpus):
                for metric in (("m", "f", "w") if _WER_IN_PLAN else ("m", "f")):
                    if metric == "f" and cond == 1 and PAPER_F1_CONDS == 1:
                        continue
                    plan.append((cell, metric, cond))
    return plan


def cell_cond_plan() -> list:
    """Every (cell, condition) pair, in order: corpus > condition > split.

    The nesting `column_plan` uses, for the tables that carry no metric axis.
    Kept beside it so one edit reorders every table in the paper.
    """
    return [(cell, cond)
            for corpus in corpus_order(CELLS)
            for cond in (0, 1)
            for cell in splits_of(corpus, CELLS)]


def _boundary_gap(a, b):
    """The gap that separates two adjacent columns, or None if they are a pair."""
    if a[0][0] != b[0][0]:
        return _GAP_CORPUS
    if a[2] != b[2]:
        return _GAP_COND
    if a[0] != b[0]:
        return _GAP_SPLIT
    # MAE and $F_1$ are the pair a reader compares, so they get air between
    # them; $F_1$ and the rate beside it are not, and stay tight.
    return _GAP_MAE if a[1] == "m" else _GAP_METRIC


def rule_after(i: int) -> bool:
    """Whether a vertical rule follows numeric column `i` (0-based): always.

    Ruling only the corpus and condition boundaries left the MAE/$F_1$ pair
    unseparated, and ruling the metric boundary alone would have inverted the
    grouping -- a line between MAE and $F_1$, which belong together, and only a
    gap between one split's $F_1$ and the next split's MAE. Every boundary is
    therefore ruled, and the hierarchy is carried by the header spans and by the
    gaps, which stay graded from 1pt at the metric boundary to 7pt at the corpus.
    """
    return PAPER_RULES and i < len(column_plan()) - 1


def numeric_cols(slack: dict | None = None) -> str:
    """The column spec, with each group boundary split evenly across it.

    A gap written as one `@{\\hspace{G}}` between two groups is absorbed into the
    `\\multicolumn` that ends beside it, so a span header centres over its columns
    PLUS that trailing gap and sits G/2 to the right of the numbers it labels --
    measured at +2.0 to +6.4pt, which is what read as the columns being pushed
    left. Half the gap is therefore attached inside the last column of the left
    group and half inside the first column of the right group, so whatever a span
    absorbs, it absorbs symmetrically.
    """
    plan = column_plan()

    boundary = _boundary_gap

    def half(gap):
        # halved here, not in \dimexpr: TeX's \dimexpr has no decimal multiplier,
        # so "3pt*0.5" is a syntax error rather than 1.5pt.
        return f"{float(gap.rstrip('pt')) / 2:g}pt"

    gaps = [boundary(plan[i], plan[i + 1]) for i in range(len(plan) - 1)]
    slack = slack or {}
    out = []
    for i, (cell, metric, cond) in enumerate(plan):
        left = [half(gaps[i - 1])] if i > 0 and gaps[i - 1] else []
        right = [half(gaps[i])] if i < len(gaps) and gaps[i] else []
        # half the missing width on each side, so the column widens without its
        # contents moving off centre
        n = slack.get((metric, cell, cond), 0)
        if n:
            left.append(f"{n * 0.5:g}\\fabdgt")
            right.append(f"{n * 0.5:g}\\fabdgt")
        # Nudge the MAE number off the rule it shares with $F_1$. Equal and
        # opposite, so the column keeps its width and only the digits move: a
        # wider metric GAP would have to stay under the 2pt split gap to keep the
        # hierarchy, and there is no room under it.
        shift = _MAE_SHIFT if metric == "m" else ""
        l_expr = "+".join(left) + ("-" + shift if shift and left else "")
        r_expr = "+".join(right) + ("+" + shift if shift and right else "")
        if shift and not left:
            l_expr = "-" + shift
        if shift and not right:
            r_expr = shift
        pre = (">{\\hspace{\\dimexpr" + l_expr + "\\relax}}") if l_expr else ""
        post = ("<{\\hspace{\\dimexpr" + r_expr + "\\relax}}") if r_expr else ""
        out.append(pre + "c" + post)
        if rule_after(i):
            out.append("|")
    return " " + "".join(out)


def _metric_rules(first: int, f1_conds: int) -> str:
    """cmidrules under each metric group, whose widths differ when $F_1$ carries
    only the clean condition."""
    out, col = [], first
    for _ in PAPER_CELLS:
        out.append(f"\\cmidrule(lr){{{col}-{col + 1}}}")
        col += 2
        if f1_conds == 2:
            out.append(f"\\cmidrule(lr){{{col}-{col + 1}}}")
            col += 2
        else:
            out.append(f"\\cmidrule(lr){{{col}-{col}}}")
            col += 1
    return "".join(out)


def _span_row(lead_n, level, label_of, first):
    """One header row plus its rules, spanning runs of `column_plan` that agree
    at `level`. Built from the plan so a reordering cannot desynchronize a span
    from the columns beneath it."""
    plan = column_plan()
    cells, rules, start = [], [], 0
    for k in range(1, len(plan) + 1):
        if k == len(plan) or level(plan[k]) != level(plan[start]):
            width = k - start
            # \multicolumn REPLACES the column spec for the span it covers, the
            # trailing rule included, so a span ending on a rule has to carry it
            # or the rule disappears from that header row only.
            spec = "c|" if rule_after(k - 1) else "c"
            cells.append(f"\\multicolumn{{{width}}}{{{spec}}}{{{label_of(plan[start])}}}")
            rules.append(f"\\cmidrule(lr){{{first + start}-{first + k - 1}}}")
            start = k
    return ["& " * lead_n + " & ".join(cells) + r"\\", "".join(rules)]


def _f1_tol(ms: str) -> str:
    """The $F_1$ header with its tolerance on it, condensed to the width of
    the numbers underneath. A size down and a horizontal squeeze, the same
    treatment the rate label gets, because the superscript costs about 3pt a
    column and Table 1 has four of them across a single column of the page."""
    return (r"\scalebox{0.74}[1]{\fontsize{6pt}{6.6pt}\selectfont"
            r"$\boldsymbol{F_1^{\scriptscriptstyle " + ms + r"}}$}")


def metric_label(metric: str, rate: str | None = None) -> str:
    """The header cell for one metric. `rate` names what the rate slot holds
    when it is not _RATE_LABEL, "f50" for $F_1$ at 50 ms."""
    if metric == "m":
        return r"\scalebox{0.9}[1]{MAE}"
    if metric == "f":
        # The tolerance on the label, at the same size as the 50 ms column
        # beside it, so the two are read as one family rather than as a
        # metric and a variant of it.
        return _f1_tol("20")
    if rate == "f50":
        # A whole size down on the label, not just on the 50. It names a
        # second tolerance of the column beside it rather than a metric of
        # its own, and at the body size it drew the eye first.
        return _f1_tol("50")
    lab = rate or _RATE_LABEL
    # The rate label is condensed to the width of its numbers. "WER" is three
    # wide capitals, 14.7pt at the table size over two-digit rates 11.6pt
    # wide, and left alone it set all four rate columns 3pt wider than
    # anything in them, 12.5pt across the table, the width of the Grid column.
    return r"\scalebox{" + _RATE_SCALE.get(lab, "1") + "}[1]{" + lab + "}"


def metric_row(lead_n: int, rate: str | None = None) -> str:
    """One row of metric names under a track heading, off column_plan, so a
    track whose rate slot holds something else can say so."""
    return ("& " * lead_n
            + " & ".join(metric_label(e[1], rate) for e in column_plan()) + r"\\")


def header(colspec: str, lead_cols: list[str], size: str = r"\footnotesize",
           colsep: str = "1.2pt", cond_words: bool = False,
           block_metrics: bool = False, fill: bool = False) -> list[str]:
    """Three header rows: corpus+condition, split, metric.

    Each level names what varies, outermost to innermost, matching `column_plan`.
    Corpus and condition share the top row -- "TIMIT clean" rather than a TIMIT
    span above a clean span -- which costs nothing in width, since four columns
    of numbers are wider than the longest label, and saves a row and its rule in
    a table that is already four deep. Metric is innermost, so each split carries
    its MAE and $F_1$ as a pair.
    """
    n = len(lead_cols)
    first = 1 + n
    plan = column_plan()
    conds = ["clean", "noisy"] if cond_words else ["C", "N"]
    rows = []
    # One split per corpus and one condition leaves the split row saying what
    # the corpus row could say, so the two collapse into "TIMIT test".
    _flat = (len(PAPER_CONDS) == 1
             and all(len(splits_of(c)) == 1 for c in corpus_order()))
    if _flat:
        rows += _span_row(n, lambda e: e[0][0],
                          lambda e: f"{CORPUS_LABEL[e[0][0]]} {SPLIT_LABEL[e[0]]}",
                          first)
    else:
        _one_split = all(len(splits_of(c)) == 1 for c in corpus_order())
        rows += _span_row(n, lambda e: e[0][0],
                          lambda e: (f"{CORPUS_LABEL[e[0][0]]} {SPLIT_LABEL[e[0]]}"
                                     if _one_split else CORPUS_LABEL[e[0][0]]), first)
        rows += _span_row(n, lambda e: (e[0][0], e[2], e[0]),
                          lambda e: (SPLIT_LABEL[e[0]] if len(PAPER_CONDS) == 1
                                     else conds[e[2]] if _one_split
                                     else f"{SPLIT_LABEL[e[0]]}-{conds[e[2]]}"), first)
    # Direction of goodness on the column itself, so a reader scanning the body
    # need not hold "lower is better for one, higher for the other".
    leads = " & ".join("" if c == "Family" else c for c in lead_cols)
    if block_metrics:
        # The metric names go under each track heading, metric_row(), since
        # the rate slot is WER on one track and $F_1$ at 50 ms on the other.
        # The lead labels drop to the last header row, whose lead cells were
        # empty.
        last = max(i for i, r in enumerate(rows) if r.endswith(r"\\"))
        assert rows[last].startswith("& " * n), rows[last][:40]
        rows[last] = leads + " & " + rows[last][len("& " * n):]
    else:
        rows.append(leads + " & " + " & ".join(metric_label(e[1]) for e in plan) + r"\\")
    if lead_cols and lead_cols[0] == "Family":
        # The family header stands on its side over the whole header block,
        # as its tags stand over their runs, so the column is as wide as a
        # rotated word and not as wide as "Family".
        # With block metrics the first track heading is the block's third
        # row, and that heading starts in column 2 to leave this label its cell.
        n_rows = sum(1 for r in rows if r.endswith(r"\\")) + (1 if block_metrics else 0)
        rows[0] = (r"\multirow{" + str(n_rows) + r"}{*}{\rotatebox[origin=c]{90}{"
                   r"\fontsize{5.5pt}{6pt}\selectfont Family}} " + rows[0])
    return [size,
            # measured inside the table group, so it is a digit at THIS size
            r"\settowidth{\fabdgt}{0}",
            r"\setlength{\tabcolsep}{" + colsep + r"}",
            # tabular* to the column, with the fill glue set where the
            # colspec asks for it, so leftover width lands between the numeric
            # columns. The caller closes the environment.
            (r"\begin{tabular*}{\columnwidth}{@{}" if fill else r"\begin{tabular}{@{}")
            + colspec + "@{}}", r"\toprule"] + rows + (
                [] if block_metrics else [r"\midrule"])


def track_heading(lead_n: int, text: str) -> str:
    """A heading row spanning the table. With the family column on it starts
    in column 2, leaving the first cell to the rotated Family label above it
    and clear of any tag below."""
    if PAPER_FAMILY_COL:
        return "& " + r"\multicolumn{" + str(lead_n - 1 + len(column_plan())) + "}{l}{" + text + r"}\\"
    return r"\multicolumn{" + str(lead_n + len(column_plan())) + "}{l}{" + text + r"}\\"


_rows_seen: list = []
#: The rows each tier printed, word and phone, for the caption sentence that
#: names the open-source members of the Open group.
_TABLE_ROWS: dict = {}


#: Systems whose frame is a FIXED constant rather than a per-file ratio, with
#: the constant in ms. FALCON multiplies its frame index by a hardcoded
#: 161.34011627906978 samples at 16 kHz, the same in every file: the measured
#: frame moves by 0.0006 ms across 173 utterances, against 1.3 ms for BFA and
#: 0.2 ms for MMS-FA. It has a real global lattice, it is just not on a round
#: number, and the Grid column rounds 10.08 to 10.
FIXED_FRAME = {"falcon": "10.08"}


def _frame_note(m, rows, tier: str, ref: str | None = None) -> str:
    """The caption sentence about rows whose Grid is a frame, not a step.

    Read off the rows the table printed and the same measurement the Grid
    column uses, so a table that stops printing a system stops explaining it.
    `ref` points at the table that already spells the per-file case out, for
    the second table, whose ratio rows are a subset of the first's.
    """
    ratio, fixed = [], []
    for r in rows:
        t = r[3]
        parts = m.cascade_parts(t)
        base = parts[0] if parts else t
        d = recipe_dirs().get(base)
        if d is None:
            continue
        hyp = d / GRID_CELL / "hyp.jsonl"
        if not hyp.is_file():
            continue
        g = load_measure_grid().grid_of(str(hyp), cap=4000, key=tier)
        if g["step"] or g["frame"] is None or g["frame_share"] < 0.5:
            continue
        name = disp_paper(m, base).partition(" \u2192 ")[-1] or disp_paper(m, base)
        if base in FIXED_FRAME:
            if (name, FIXED_FRAME[base]) not in fixed:
                fixed.append((name, FIXED_FRAME[base]))
        elif name not in ratio:
            ratio.append(name)

    def join(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

    out = []
    if ratio and ref:
        out.append("Grid reads as in " + ref + ".")
    elif ratio:
        out.append(join(ratio) + (" turns" if len(ratio) == 1 else " turn")
                   + " a frame index into seconds by a per-file ratio, so the "
                   "figure is the frame behind it and the times land just off.")
    for name, ms in fixed:
        out.append(name + "'s frame is a fixed " + ms + "\\,ms.")
    return " ".join(out)


def _no_noisy_note(m, rows) -> str:
    """One caption sentence naming the printed rows that have a clean cell but
    no noisy mean, read off the data rather than asserted.

    A cell reports a noisy mean only with all four conditions in hand, so a row
    part way through a sweep still counts as missing and keeps saying so until
    the sweep finishes. The old sentence named ElevenLabs in the source, which
    would have stayed in the caption after its cells were filled.
    """
    mae: dict = {}
    for kind in ("aligners", "timestamp_asrs"):
        for tool, cells in collect(kind, "wbe_ms").items():
            mae.setdefault(tool, {}).update(cells)
    missing = []
    for r in rows:
        cells = mae.get(r[3]) or {}
        # PAPER_CELLS only. The dev splits are in records/ and a row that
        # is short there says nothing about the table a reader is holding.
        if not any(cells.get(k, (None, None))[0] is not None
                   and cells.get(k, (None, None))[1] is None
                   for k in PAPER_CELLS):
            continue
        name = disp_paper(m, r[3])
        if name not in missing:
            missing.append(name)
    if not missing:
        return ""
    who = (missing[0] if len(missing) == 1
           else ", ".join(missing[:-1]) + " and " + missing[-1])
    return f" {who} {'has' if len(missing) == 1 else 'have'} no noisy cells."


def _access_note(m, rows) -> str:
    """One caption sentence saying what Open means for the rows printed.

    Built from the rows and PAPER_AVAIL, so a system that changes side there
    changes side here in the same run. A cascade is judged by its aligner, as
    its family tag is.
    """
    opens, openw = [], False
    for r in rows:
        t = r[3]
        a = _avail(m, t)
        if a == "api":
            continue
        if a != "opens":
            openw = True
            continue
        parts = m.cascade_parts(t)
        name = disp_paper(m, parts[0] if parts else t)
        name = name.partition(" \u2192 ")[-1] or name
        if name not in opens:
            opens.append(name)

    def join(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

    head = "Open means the weights are published, "
    if not openw:
        return head + "and every open row here also publishes the code that trained it."
    return head + "and " + join(opens) + " also publish the code that trained them."


def mark_mode_b(lines: list[str], m) -> list[str]:
    """Append a dagger to the system name of every PHONE_MODE_B row.

    Matched on the DISPLAY name rather than the tool key, because that is all
    the emitted line carries by the time body() has formatted it.
    """
    out, marked = [], set()
    for line in lines:
        for tool in PHONE_MODE_B:
            name = disp_paper(m, tool)
            if not name:
                continue
            # Match the NAME as a whole token, not the citation that follows it.
            # Keying on "& <name>~\cite" broke silently the day \cite gained a
            # size wrapper: the dagger simply stopped being emitted, and the
            # caption went on explaining a symbol no row carried.
            # The System cell is the first cell when the family column is off,
            # so the name may open the line as well as follow an ampersand.
            pat = _re.compile(r"((?:^|&)\s*" + _re.escape(name) + r")(?![A-Za-z])")
            if pat.search(line):
                line = pat.sub(r"\1\\smash{$^\\dagger$}", line, count=1)
                marked.add(tool)
                break
        out.append(line)
    want = {t for t in PHONE_MODE_B if any(t == r[3] for r in _rows_seen)}
    missing = want - marked
    if missing:
        raise SystemExit(f"mark_mode_b: no row matched {sorted(missing)} -- the "
                         f"caption explains a dagger that no row carries")
    return out


def phone_table(m) -> str:
    global _WER_IN_PLAN, _RATE_LABEL, _GAP_MAE
    _WER_IN_PLAN, _RATE_LABEL = True, "PER"
    _gap_was, _GAP_MAE = _GAP_MAE, _GAP_MAE_PHONE
    mae, f1 = collect("aligners", "mae_ms"), collect("aligners", F1_PHONE)
    # Phone error rate against the gold phones, in percent, in the column the
    # word table gives to WER. On Track 1 it is what "given the words" costs a
    # system that derives its own phones. Track 2 here is the cascades whose
    # aligner emits phones, and their PER carries the recognizer's word errors
    # through the dictionary as well.
    per = collect("aligners", "per")
    t_mae, t_f1 = collect("timestamp_asrs", "mae_ms"), collect("timestamp_asrs", F1_PHONE)
    t_wer = collect("timestamp_asrs", "per")
    rows = order(m, sorted(set(mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), mae, f1=f1)
    # TRACK 2 IS ORDERED BY THE WORD TIER, so the cascades stand in the same
    # order here as in Table 1 and a reader can carry a row across. Phone MAE
    # separates the three Olign cascades by 0.9 ms, which is not an ordering
    # worth contradicting the other table for.
    t_rows = order(m, sorted(set(t_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS),
                   collect("timestamp_asrs", "wbe_ms"))
    # No float wrapper and no caption: combined_table() supplies both.
    L = []
    # Columns one width down the whole table, Track 1 and Track 2 together.
    pads = col_pads(rows, mae, f1, per)
    for k, v in col_pads(t_rows, t_mae, t_f1, t_wer).items():
        pads[k] = max(pads.get(k, 1), v)
    _n = n_lead(None, t_wer)
    # NO GRID COLUMN. It does not move with the condition, so it was paying
    # for itself four times over in a table that shows four of them, and the
    # supplement's grid table carries every system with its phase. Table 3
    # keeps the column for the rows a reader is comparing on timing.
    L += header((r"l@{\hspace{0.2pt}}>{" + TABLE_NAME_SIZE + "}l" if PAPER_FAMILY_COL
                 else r">{" + TABLE_NAME_SIZE + "}l") + r"|@{\extracolsep{\fill}}"
                + numeric_cols(col_slack(pads)),
                (["Family", "System"] if PAPER_FAMILY_COL else ["System"]),
                colsep="0.05pt", cond_words=True, block_metrics=True, fill=True)
    _TABLE_ROWS["phone"] = rows + t_rows
    # The same spanning row the word tier carries, and it says something the
    # word tier does not need to: at the phone tier "given the reference" means
    # given the WORDS, from which each system derives its own phones. FALCON
    # is handed the phone sequence itself, which is why it is daggered.
    L.append(track_heading(_n, r"\small\textbf{Track~1}\emph{, reference words, except FALCON}"
                           r"\smash{$^\dagger$}"))
    L += [metric_row(_n), r"\midrule"]
    global _rows_seen
    _rows_seen = rows
    cited: set = set()
    L += mark_mode_b(body(rows, mae, f1, m, family_col=PAPER_FAMILY_COL, pads=pads,
                          seen_cites=cited, wer=per, grid=None), m)
    L.append(r"\midrule")
    # No one-step ASR emits phones, so Track 2 here is the two-step block
    # alone and the heading says so in one line.
    L.append(track_heading(_n, r"\small\textbf{Track~2}\emph{, two steps. $\boldsymbol{\to}$ denotes ASR then aligner}"))
    L += [metric_row(_n), r"\midrule"]
    t_best = best_values(t_rows, t_mae, t_f1)
    L += body(t_rows, t_mae, t_f1, m, family_col=PAPER_FAMILY_COL, aligner_names=True,
              bestv=t_best, pads=pads, seen_cites=cited, wer=t_wer, grid=None)
    L += [r"\bottomrule", r"\end{tabular*}"]
    out = "\n".join(L)
    _GAP_MAE = _gap_was
    return out


#: The recognisers whose decoded words Track 2's two-step rows are aligning.
#: Every "Qwen3 -> X" row reads the first; WhisperX reads the second.
TRANSCRIPT_SOURCES = [
    ("whisper3", "Whisper"),
    ("qwen3_asr", "Qwen3-ASR"),
]

#: Recognisers whose transcript the TWO-STEP rows align. They are listed below a
#: rule in Table 3 rather than among the one-step systems: their WER is an input
#: to other rows, not just their own result. Parakeet-TDT joined when it began
#: feeding the Olign and MFA cascades.
CASCADE_SOURCES = [
    ("qwen3_asr", "Qwen3-ASR"),
    ("parakeet_tdt", "Parakeet-TDT"),
]


def word_table(m) -> str:
    a_mae, a_f1 = collect("aligners", "wbe_ms"), collect("aligners", F1_WORD)
    # Track 1 is given the words and has no WER, so its rate slot carries
    # the same F1 at 50 ms. Beside the 20 ms figure it says whether a low F1
    # is fine timing or gross error, which for a system on an 80 ms grid is
    # the whole question.
    a_f150 = collect("aligners", F1_WORD.replace("_20ms", "_50ms"))
    t_mae, t_f1 = collect("timestamp_asrs", "wbe_ms"), collect("timestamp_asrs", F1_WORD)
    # WER sits beside the timing so the two can be read off one row. It is the
    # reason Track 2 is not comparable to Track 1 and the evidence for the
    # paper's claim that a recogniser's word accuracy says nothing about its
    # timestamps, and having it only in the supplement made that claim take a
    # reader two tables to check.
    t_wer = collect("timestamp_asrs", "wer")
    global _WER_IN_PLAN, _RATE_LABEL
    _WER_IN_PLAN, _RATE_LABEL = True, "WER"
    a_rows = order(m, sorted(set(a_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), a_mae,
                   f1=a_f1)
    # Track 2 reads the same way as Track 1, best mean clean $F_1$ first, so
    # one rule orders the whole table instead of MAE here and $F_1$ above.
    t_rows = order(m, sorted(set(t_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS),
                   t_mae, f1=t_f1)
    # No float wrapper and no caption: this is subtable (a) of the merged
    # float that combined_table() builds, and both halves are captioned there.
    #
    # Width history worth keeping. The noisy $F_1$ pair is dropped so MAE can
    # keep both conditions -- degradation stays visible and noisy $F_1$ stays
    # in the records. The System column only fits once "TorchAudio (ASR)" and
    # "Whisper large-v3" hand their qualifiers to the caption, and names at or
    # over _SHRINK_AT characters are set a size down.
    L = []
    # Same columns as Table 1. The Pipeline column is gone: the system names
    # already say it -- an arrow IS the two-step marker -- and a column that
    # repeats the name costs width for nothing.
    pads = col_pads(a_rows, a_mae, a_f1)
    for k, v in col_pads(t_rows, t_mae, t_f1, t_wer).items():
        pads[k] = max(pads.get(k, 1), v)
    # 0.85pt against the phone table's 1.0: the metric pairs carry their own 1pt
    # boundary, and naming the recognizer on every two-step row widened the
    # System column enough to run 1.9pt past the text block at 1.0pt.
    # Grid beside the name, the step every boundary of the row sits on. It
    # came back once the rate label stopped over-setting its columns; a
    # cascade's is measured from its own output and is its aligner's.
    _n = n_lead(None, t_wer)
    # NO GRID COLUMN. It does not move with the condition, so it was paying
    # for itself four times over in a table that shows four of them, and the
    # supplement's grid table carries every system with its phase. Table 3
    # keeps the column for the rows a reader is comparing on timing.
    L += header((r"l@{\hspace{0.2pt}}>{" + TABLE_NAME_SIZE + "}l" if PAPER_FAMILY_COL
                 else r">{" + TABLE_NAME_SIZE + "}l") + r"|@{\extracolsep{\fill}}"
                + numeric_cols(col_slack(pads)),
                (["Family", "System"] if PAPER_FAMILY_COL else ["System"]),
                colsep="0.05pt", cond_words=True, block_metrics=True, fill=True)
    _TABLE_ROWS["word"] = a_rows + t_rows
    L.append(track_heading(_n, r"\small\textbf{Track~1}\emph{, given the reference transcript}"))
    L += [metric_row(_n, "f50"), r"\midrule"]
    cited: set = set()
    L += body(a_rows, a_mae, a_f1, m, family_col=PAPER_FAMILY_COL, pads=pads, seen_cites=cited,
              wer=a_f150, wfmt=(PAPER_F1_DIGITS, False),
              bestv=best_values(a_rows, a_mae, a_f1, w=a_f150), grid=None)
    # A rule closes Track 1. The tracks are not comparable, so the boundary
    # between them should read as a division of the table, not a gap in a list.
    L.append(r"\midrule")
    # Track 2 splits again by pipeline: a system that times its own decode and
    # one that hands the words to a separate aligner are different machines, and
    # the block boundary says so without a column spent repeating it. Family
    # order runs inside each block, as in Track 1.
    one = [r for r in t_rows if m.pipe(r[3]) == "one-step"]
    two = [r for r in t_rows if m.pipe(r[3]) != "one-step"]
    # The heading sat hard against Track 1's last row, so the two blocks read
    # as one list with a rule through it.
    L.append(track_heading(_n, r"\small\textbf{Track~2}\emph{, one step. The ASR times its own words}"))
    L += [metric_row(_n), r"\midrule"]
    # One winner per column across the whole of Track 2, not one per block.
    t_best = best_values(t_rows, t_mae, t_f1)
    L += body(one, t_mae, t_f1, m, family_col=PAPER_FAMILY_COL, bestv=t_best, pads=pads, seen_cites=cited,
              wer=t_wer, grid=None)
    # Still Track 2, so the label is not repeated; the indent is what says
    # this is the second half of the block above rather than a third track.
    L.append(track_heading(_n, r"\quad\small\emph{two steps. $\boldsymbol{\to}$ denotes ASR then aligner}"))
    L += body(two, t_mae, t_f1, m, family_col=PAPER_FAMILY_COL, aligner_names=True, bestv=t_best, pads=pads,
              seen_cites=cited, wer=t_wer, grid=None)
    L += [r"\bottomrule", r"\end{tabular*}"]
    # WER belongs with track 2 and nowhere else: a track-1 system was handed the
    # words, so its WER is not a property of the system at all.
    return "\n".join(L)


#: Data-row font and row stretch for Table 1. The float is single-column now,
#: so its budget is a COLUMN and not a page: at \footnotesize LaTeX reported
#: "Float too large for page by 82.05pt". Measured, not chosen.
#: 6.6pt on a 7.4pt line rather than \scriptsize's 7 on 8. With F1 keeping
#: its leading zero the thirteen columns ran 11.5pt past the text block at 7pt,
#: and this is the one lever left that changes no number and no spacing.
TABLE_SIZE = r"\fontsize{8pt}{8.8pt}\selectfont"
#: A size down from TABLE_SIZE for the two widest two-step names, on the
#: table's own baseline so the row does not grow. \scriptsize is 7pt and
#: \tiny 5pt, one above the table and one too far below it.
NAME_SMALL = r"\fontsize{5.8pt}{7.4pt}\selectfont"
#: Every system name in Tables 1 and 2, a size under the numbers beside it.
TABLE_NAME_SIZE = r"\fontsize{8pt}{8.8pt}\selectfont"
TABLE_STRETCH = "1.0"
#: Space booktabs leaves above and below each rule. The defaults are 0.4ex
#: and 0.65ex, which on a table whose blocks are closed by a dozen rules adds
#: a visible ~1ex gap at every block break and makes the Open/API split look
#: like a paragraph break rather than a row. At 0pt a rule costs only its own
#: 0.25pt and a block boundary is spaced like any other row. All three tables
#: set it, since \setlength inside table is local and Table 3 would otherwise
#: keep the defaults and stop matching.
RULE_ABOVE = "0pt"
RULE_BELOW = "0pt"


def grid_table(m) -> str:
    """Every system's timestamp grid, three systems to a row.

    It left Table 1 when that table took on clean and noisy for both corpora
    and had no width left for a column that does not change with the
    condition. A cascade is not listed, since its grid is its aligner's.
    """
    a_mae = collect("aligners", "wbe_ms")
    t_mae = collect("timestamp_asrs", "wbe_ms")
    p_mae = collect("aligners", "mae_ms")
    seen, items = set(), []
    for rows, tier in ((order(m, sorted(set(a_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), a_mae), "words"),
                       (order(m, sorted(set(t_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), t_mae), "words"),
                       (order(m, sorted(set(p_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), p_mae), "phones")):
        for _, _, _, t, _ in rows:
            if m.cascade_parts(t) or "\u2192" in disp_paper(m, t):
                continue
            name = _drop_version(unshrink(tex_name(disp_paper(m, t))))
            if name in seen:
                continue
            seen.add(name)
            items.append((name, grid_label(t, tier)))
    cols = 4
    per = -(-len(items) // cols)
    lines = []
    for i in range(per):
        cells = []
        for c in range(cols):
            j = i + c * per
            cells.append(f"{items[j][0]} & {items[j][1]}" if j < len(items) else " & ")
        lines.append(" & ".join(cells) + r"\\")
    return "\n".join([
        r"\begin{table}[!t]", r"\centering", TABLE_SIZE,
        r"\setlength{\tabcolsep}{3pt}",
        r"\caption{Timestamp grid of each system in Table~\ref{tab:main}, in "
        r"ms, measured from its hypotheses. $\sim$ is a frame computed per "
        r"file, a dash no lattice down to 1\,ms, and a cascade has its "
        r"aligner's. Full names: Google Chirp~2, ElevenLabs Scribe~v2, Amazon "
        r"Transcribe, AssemblyAI Universal~3.5, IBM Watson Large, Azure AI "
        r"Speech, Deepgram Nova-3, Speechmatics enhanced, Whisper large-v3, "
        r"Whisper-timestamped, Parakeet-TDT, Qwen3-ASR, and NeMo-FA's conformer "
        r"checkpoint.}",
        r"\label{tab:grid}",
        r"\begin{tabular}{@{}lr@{\hspace{5pt}}lr@{\hspace{5pt}}lr@{\hspace{5pt}}lr@{}}", r"\toprule",
        r"System & Grid & System & Grid & System & Grid & System & Grid\\", r"\midrule",
        *lines,
        r"\bottomrule", r"\end{tabular}", r"\end{table}"])


PAPER_MERGED = False


def merged_table(m) -> str:
    """One two-column float. A Track 1 row carries the word tier and the phone
    tier side by side under each condition, MAE, F1, PMAE, PF1, and a Track 2
    row carries MAE, F1 and WER in the same columns with the fourth left blank.
    The phone tier stopped being a table of its own the day the word tier
    took on clean and noisy for both corpora and there was no column left to
    put it under.
    """
    a_mae, a_f1 = collect("aligners", "wbe_ms"), collect("aligners", F1_WORD)
    p_mae, p_f1 = collect("aligners", "mae_ms"), collect("aligners", F1_PHONE)
    t_mae, t_f1 = collect("timestamp_asrs", "wbe_ms"), collect("timestamp_asrs", F1_WORD)
    t_wer = collect("timestamp_asrs", "wer")
    # The precision and recall behind the label-checked F1, Track 2 only,
    # where a missed word shows in recall and an inserted one in precision.
    t_p = collect("timestamp_asrs", F1_WORD.replace("_f1_", "_p_"))
    t_r = collect("timestamp_asrs", F1_WORD.replace("_f1_", "_r_"))
    tools1 = sorted((set(a_mae) | set(p_mae)) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS)
    # Sorted on word MAE like every other block; a phone-only system has none
    # and is placed by its phone MAE, which the caption says.
    sort1 = {t: (a_mae[t] if any((a_mae.get(t) or {}).get(c) for c in PAPER_CELLS)
                 else p_mae.get(t, {})) for t in tools1}
    rows1 = order(m, tools1, sort1)
    rows2 = order(m, sorted(set(t_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), t_mae)
    one = [r for r in rows2 if m.pipe(r[3]) == "one-step"]
    two = [r for r in rows2 if m.pipe(r[3]) != "one-step"]
    groups = [(cell, cond) for corpus in corpus_order()
              for cond in PAPER_CONDS for cell in splits_of(corpus)]
    SLOTS = 5
    ncol = 1 + SLOTS * len(groups)

    def val(src, t, cell, cond):
        return (src.get(t, {}).get(cell) or (None, None))[cond]

    def cells1(t):
        return [(val(a_mae, t, c, k), val(a_f1, t, c, k), val(p_mae, t, c, k), val(p_f1, t, c, k), None)
                for c, k in groups]

    def cells2(t):
        return [(val(t_mae, t, c, k), val(t_f1, t, c, k), val(t_p, t, c, k), val(t_r, t, c, k),
                 val(t_wer, t, c, k)) for c, k in groups]

    DIG1 = (1, 2, 1, 2, 1)          # MAE, F1, PMAE, PF1, blank
    DIG2 = (1, 2, 2, 2, 1)          # MAE, F1, P, R, WER

    def best(rows, cellsf, want):
        out = {}
        for gi in range(len(groups)):
            for si in range(SLOTS):
                vs = [cellsf(r[3])[gi][si] for r in rows]
                vs = [v for v in vs if v is not None]
                out[(gi, si)] = (None if not vs or want[si] is None
                                 else min(vs) if want[si] == "min" else max(vs))
        return out

    b1 = best(rows1, cells1, ("min", "max", "min", "max", None))
    b2 = best(rows2, cells2, ("min", "max", "max", "max", None))
    seen: set = set()

    def line(r, cellsf, bestv, dig, aligner_names=False):
        t = r[3]
        label = r[2]
        if aligner_names:
            name = cascade_label(disp_paper(m, t))
            label = name + cite_for(t)
        label = drop_repeat_cite(label, seen)
        if t in PHONE_MODE_B:
            label = label.replace(disp_paper(m, t), disp_paper(m, t) + r"\smash{$^\dagger$}", 1)
        out = [label]
        for gi, tup in enumerate(cellsf(t)):
            for si, v in enumerate(tup):
                if v is None:
                    out.append("")
                    continue
                sv = f"{v:.{dig[si]}f}"
                b = bestv[(gi, si)]
                out.append(f"\\textbf{{{sv}}}" if b is not None and v == b else sv)
        return " & ".join(out) + r"\\"

    def block(rows, cellsf, bestv, dig, aligner_names=False):
        L = []
        runs = fam_runs(rows, m)
        ends = {r[1] + r[2] - 1 for r in runs[:-1]}
        for i, r in enumerate(rows):
            L.append(line(r, cellsf, bestv, dig, aligner_names))
            if i in ends:
                L.append(r"\cmidrule(lr){1-" + str(ncol) + "}")
        return L

    def metric_row(labels):
        return " & " + " & ".join(" & ".join(labels) for _ in groups) + r"\\"

    def heading(text):
        return r"\multicolumn{" + str(ncol) + r"}{l}{" + text + r"}\\"

    group_spec = "|".join(["r"] * SLOTS)
    colspec = "@{}l|" + r"@{\hspace{2.5pt}}|@{\hspace{2.5pt}}".join([group_spec] * len(groups)) + "@{}"
    conds = ["clean", "noisy"]
    mid = "System & " + " & ".join(r"\multicolumn{" + str(SLOTS) + r"}{c}{" + CORPUS_LABEL[c[0]] + " "
                                   + SPLIT_LABEL[c] + " " + conds[k] + "}"
                                   for c, k in groups) + r"\\"
    mid_rules = "".join(r"\cmidrule(lr){" + f"{2 + SLOTS * i}-{1 + SLOTS * (i + 1)}" + "}"
                        for i in range(len(groups)))
    L = [
        r"\begin{table*}[!t]", r"\centering",
        r"\caption{\small Boundary error on the test split of each corpus, on clean "
        r"audio and under degradation, \emph{noisy} being the mean of the four. "
        r"MAE in ms and boundary $F_1$ at 20\,ms, counting a boundary only when "
        r"the units on both sides of it are the aligned, same-labeled units. "
        r"PMAE and P$F_1$ are the same on the phone tier, and P and R are the precision and recall behind $F_1$. WER is per split and "
        r"condition. A Track~1 row is given the reference words, so it has no "
        r"WER, and one without phone cells is word-only. FALCON, daggered, is "
        r"phone-only, is handed the gold phones, an easier task than deriving "
        r"them, overlaps our Buckeye split in its training data, and is placed "
        r"by its phone MAE. Rules split "
        r"each block into \emph{OpenS}, then \emph{OpenW}, then \emph{API}, "
        r"worst to best within each. OpenS can be rebuilt from published "
        r"source and recipe, OpenW is a released checkpoint and nothing more, "
        r"and API is a service. A two-step row takes its aligner's. The "
        r"endpoints are Google Chirp~2, ElevenLabs Scribe~v2, Amazon "
        r"Transcribe, AssemblyAI Universal~3.5, IBM Watson Large, Azure AI "
        r"Speech, Deepgram Nova-3 and Speechmatics enhanced. Whisper is "
        r"large-v3, Whisper-ts Whisper-timestamped, CrisperW CrisperWhisper, "
        r"Parakeet Parakeet-TDT, Qwen3 Qwen3-ASR and NeMo-FA its conformer "
        r"checkpoint. Timestamp grids are in the supplement. ElevenLabs has no "
        r"noisy cells, its credit having run out. \emph{MFA} 3.4 and "
        r"\emph{Olign} 1.0 throughout. MAPS trained on 7 of 8 speakers in both "
        r"Buckeye splits.}",
        r"\label{tab:main}", r"\label{tab:phone}",
        r"\vspace{0pt}",
        TABLE_SIZE,
        r"\renewcommand{\arraystretch}{" + TABLE_STRETCH + "}",
        r"\setlength{\tabcolsep}{2pt}",
        r"\setlength{\arrayrulewidth}{0.25pt}",
        r"\setlength{\aboverulesep}{0.05pt}\setlength{\belowrulesep}{0.05pt}",
        r"\begin{tabular}{" + colspec + "}", r"\toprule",
        mid, mid_rules,
        heading(r"\small\textbf{Track~1}\emph{, given the reference transcript}"),
        metric_row(["MAE", r"$F_1$", "PMAE", r"P$F_1$", ""]), r"\midrule",
        *block(rows1, cells1, b1, DIG1),
        heading(r"\small\textbf{Track~2}\emph{, one step. The ASR times its own words}"),
        metric_row(["MAE", r"$F_1$", "P", "R", "WER"]), r"\midrule",
        *block(one, cells2, b2, DIG2),
        heading(r"\quad\small\emph{two steps. $\boldsymbol{\to}$ denotes ASR then aligner}"),
        heading(_CASCADE_KEY),
        *block(two, cells2, b2, DIG2, aligner_names=True),
        r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    return "\n".join(L)


#: THE CLASSES TABLE 3 SHOWS, in the order it shows them. The two interior
#: classes first, then the two utterance edges, then the catch-all. ``rest``
#: gathers the interior boundaries with neither word matched and the edges
#: whose word is wrong, which is the five-way reading of the six classes the
#: scorer keeps. A name leads with how many of its adjacent labels matched
#: the reference, and carries the boundary's place underneath, Internal,
#: Begin or End. An interior boundary has two adjacent words and an edge has
#: one, against silence, so the edges can only reach M1. M0 spans both places
#: and takes no letter.
CTX_COLS = ("int_both", "int_one", "start_ok", "end_ok", "rest")


def _M(n: int, place: str = "") -> str:
    """``M2_I`` and friends. The place rides in a scriptscript subscript so
    the five heads still fit the column, which a full-size one overran."""
    sub = rf"_{{\scriptscriptstyle {place}}}" if place else ""
    return rf"$\mathrm{{M{n}}}{sub}$"


CTX_HEAD = {"int_both": _M(2, "I"), "int_one": _M(1, "I"),
            "start_ok": _M(1, "B"), "end_ok": _M(1, "E"), "rest": _M(0)}


def _ctx_share(m, kind, rows, cell, tier):
    """Share of reference boundaries per class for one track and cell, and
    whether every row of it agrees. A Track 1 row is handed the reference, so
    the split is the corpus's own and every row shows the same one; a Track 2
    row brings its recognizer's errors, so the split is the row's."""
    pre = "wbnd" if tier == "word" else "bnd"
    per = {}
    for r in rows:
        t = r[3]
        tot = 0.0
        got = {}
        for c in CTX_COLS:
            v = collect(kind, f"n_{pre}_gold_{c}").get(t, {}).get(cell)
            got[c] = (v[0] if v else 0.0) or 0.0
            tot += got[c]
        if tot:
            per[t] = {c: 100.0 * got[c] / tot for c in CTX_COLS}
    if not per:
        return None, False
    first = next(iter(per.values()))
    same = all(all(abs(v[c] - first[c]) < 0.05 for c in CTX_COLS) for v in per.values())
    mean = {c: sum(v[c] for v in per.values()) / len(per) for c in CTX_COLS}
    return (first if same else mean), same


def class_table(m, tier: str = "word") -> str:
    """Table 3: boundary $F_1$ by recognition class, clean audio only.

    Tables 1 and 2 give one number per system per cell, which says how well a
    system did and not where it failed. This one splits that number by what
    the system had around each boundary. Reading a row across separates a
    timing failure from a recognition failure, and reading the two edge
    columns against the interior says whether a system that places the middle
    of an utterance well can also find where the speech starts and stops.
    """
    pre = "wbnd" if tier == "word" else "bnd"
    mae_key = "wbe_ms" if tier == "word" else "mae_ms"
    # TRACK 2 ONLY. A Track 1 row is handed the reference words, so every one
    # of its boundaries falls in the matched classes and two of the five
    # columns are empty down the whole block. The classes exist to separate a
    # timing failure from a recognition failure, and a system that cannot
    # misrecognize anything has nothing to separate. What Track 1 does show
    # here, that some aligners place the interior well and the utterance edges
    # badly, is in the text instead.
    t_mae = collect("timestamp_asrs", mae_key)
    t_rows = order(m, sorted(set(t_mae) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS), t_mae)
    f1 = {k: {"timestamp_asrs": collect("timestamp_asrs", f"{pre}_f1_{k}_20ms")}
          for k in CTX_COLS}

    ncol = len(CTX_COLS) * len(PAPER_CELLS)
    # A family column, as Tables 1 and 2 carry, so the Open rows and the API
    # rows are separated here too rather than only by where they sit.
    # Grid comes here from Tables 1 and 2, where it cost width four times
    # over in a table of four conditions while never changing with one. These
    # are the rows a reader compares on timing, so this is where it earns a
    # column. The supplement lists every system, Track 1 included.
    lead = 3
    L = [r"\begin{tabular*}{\columnwidth}{@{}l@{\hspace{2pt}}lc@{\extracolsep{\fill}}"
         + ("r" * len(CTX_COLS) + "|") * (len(PAPER_CELLS) - 1)
         + "r" * len(CTX_COLS) + "@{}}", r"\toprule",
         "& " * lead + " & ".join(r"\multicolumn{" + str(len(CTX_COLS)) + "}{c}{"
                                  + CELL_LABEL[c] + "}" for c in PAPER_CELLS) + r"\\",
         "".join(r"\cmidrule(lr){" + f"{1+lead+len(CTX_COLS)*i}-{lead+len(CTX_COLS)*(i+1)}" + "}"
                 for i in range(len(PAPER_CELLS))),
         "& & " + r"\scalebox{0.8}[1]{Grid}" + " & "
         + " & ".join(" & ".join(CTX_HEAD[c] for c in CTX_COLS)
                      for _ in PAPER_CELLS) + r"\\",
         r"\midrule"]

    # The reference counts decide whether a cell exists at all, and they are
    # read once here rather than per row per column, which was one CSV pass
    # per number printed.
    gold_n = {c: {k: collect(k, f"n_{pre}_gold_{c}") for k in ("timestamp_asrs", "aligners")}
              for c in CTX_COLS}

    def block(kind, rs, heading=None):
        out = ([r"\multicolumn{" + str(ncol + 2) + r"}{@{}l}{" + heading + r"}\\"]
               if heading else [])
        sh, same = {}, {}
        for cell in PAPER_CELLS:
            sh[cell], same[cell] = _ctx_share(m, kind, rs, cell, tier)
        if any(sh.values()):
            cells = []
            for cell in PAPER_CELLS:
                v = sh[cell]
                cells += ["--" if not v or v[c] < 0.05 else f"{v[c]:.1f}" for c in CTX_COLS]
            # A rule under the shares, because they are a property of the
            # corpus and the transcript rather than a system's score, and
            # without it a reader takes the first line for another row.
            out.append(r"& \emph{\% of boundaries} & & " + " & ".join(cells) + r"\\")
            out.append(r"\midrule")
        vals = []
        for r in rs:
            t = r[3]
            row = []
            for cell in PAPER_CELLS:
                for c in CTX_COLS:
                    v = f1[c][kind].get(t, {}).get(cell)
                    n = gold_n[c][kind].get(t, {}).get(cell)
                    row.append(v[0] if (v and n and n[0]) else None)
            vals.append((t, row))
        # Best in each column, so a reader can find the winner of a category
        # without reading the column twice. Judged on the PRINTED value, two
        # decimals, because bolding one of two identical-looking numbers is
        # read as a typesetting fault rather than as a third decimal.
        r2 = lambda v: None if v is None else round(v, 2)
        best = []
        for j in range(len(PAPER_CELLS) * len(CTX_COLS)):
            col = [r2(row[j]) for _, row in vals if row[j] is not None]
            best.append(max(col) if col else None)
        # Runs of one family, tagged once on the run's first row.
        fams = [_fam_label(m, t) for t, _ in vals]
        runs = {}
        i = 0
        while i < len(fams):
            j = i
            while j < len(fams) and fams[j] == fams[i]:
                j += 1
            runs[i] = (fams[i], j - i)
            i = j
        for i, (t, row) in enumerate(vals):
            cells = [fmt(v, digits=2, lead_zero=False,
                         bold=(v is not None and best[j] is not None
                               and r2(v) == best[j]))
                     for j, v in enumerate(row)]
            if i in runs:
                f, n = runs[i]
                inner = (r"\smash{\rotatebox[origin=c]{90}{\tiny " + f + "}}"
                         if n >= FAM_ROTATE_MIN else r"{\tiny " + f + "}")
                tag = inner if n == 1 else r"\multirow{" + str(n) + r"}{*}{" + inner + "}"
                if i:
                    out.append(r"\cmidrule(lr){1-" + str(ncol + 2) + "}")
            else:
                tag = ""
            out.append(tag + " & " + disp_paper(m, t) + " & " + grid_label(t, "words")
                       + " & " + " & ".join(cells) + r"\\")
        return out

    L += block("timestamp_asrs", t_rows)
    L += [r"\bottomrule", r"\end{tabular*}"]
    body = "\n".join(L)
    return "\n".join([
        # [t] and not [!t]. The bang overrides the float fraction, and with
        # Tables 1 and 2 already forced onto one page it stacked three floats
        # across two columns and ran that page 36pt over. Plain [t] lets this
        # one wait for the next page, which is where the text that needs it
        # begins. A size up on the other two as well, since eleven columns
        # leave the width for it.
        r"\begin{table}[t]", r"\centering",
        r"\fontsize{8pt}{8.8pt}\selectfont",
        r"\setlength{\tabcolsep}{0.05pt}\renewcommand{\arraystretch}{" + TABLE_STRETCH + "}",
        r"\setlength{\aboverulesep}{" + RULE_ABOVE + "}"
        r"\setlength{\belowrulesep}{" + RULE_BELOW + "}",
        r"\caption{\small The $F_1$s at 20\,ms of different types of word-tier "
        r"boundaries on clean audio of Track~2. "
        r"A boundary inside ($I$) an utterance has two adjacent "
        r"words. We use $\mathrm{M2}_{I}$ to denote both words are matched "
        r"and $\mathrm{M1}_{I}$ to denote one label is matched, where M "
        r"denotes matched. $\mathrm{M1}_{B}$ and $\mathrm{M1}_{E}$ denote "
        r"the beginning ($B$) and the ending ($E$) boundary of an utterance "
        r"respectively, each with only one adjacent word. $\mathrm{M0}$ "
        r"denotes the remaining boundaries. Grid is the step of boundaries "
        r"in ms. The first row is the share of reference boundaries in each "
        r"category, averaged over the rows.}",
        r"\label{tab:class}", body, r"\end{table}",
    ])


def combined_table(m) -> str:
    """Two single-column floats, the word tier and then the phone tier, with
    the same three columns under every condition, MAE, $F_1$ and WER.

    They were one float with two subtables until the stack outgrew a column,
    654pt against 651.6, then one two-column float with the phone tier beside
    the word tier until that grew past what a row can carry. Two floats let
    LaTeX place each where it fits, and the phone tier gets Track 2 back, the
    cascades whose aligner emits phones, which the merged float had no
    columns for.
    """
    word = word_table(m).replace(r"\footnotesize", TABLE_SIZE)
    phone = phone_table(m).replace(r"\footnotesize", TABLE_SIZE)
    setup = [
        r"\centering",
        r"\renewcommand{\arraystretch}{" + TABLE_STRETCH + "}",
        r"\setlength{\arrayrulewidth}{0.25pt}",
        # booktabs puts 0.4ex above and 0.65ex below every rule, and there are
        # a dozen of them closing the groups. Table 3 leaves them alone, so
        # these two match it and the three floats breathe the same way.
        r"\setlength{\aboverulesep}{" + RULE_ABOVE + "}"
        r"\setlength{\belowrulesep}{" + RULE_BELOW + "}",
    ]
    return "\n".join([
        r"\begin{table}[!t]", *setup,
        r"\caption{\small Word-tier boundary error on the test split of each "
        r"corpus, on clean audio and under degradation, \emph{noisy} being the "
        r"mean of the four. The dev splits are in \texttt{records/}\recfn. Every "
        r"number here comes from our own run of the system rather than from its "
        r"paper. MAE is over word boundaries in ms. $F_1$ is over every word "
        r"boundary of the utterance, the two utterance edges included. A "
        r"boundary is a hit only when the words on each side of it are the words "
        r"the reference has there and the time falls within the tolerance of the "
        r"reference boundary. The superscript on $F_1$ is that tolerance in ms. "
        + _access_note(m, _TABLE_ROWS["word"]) + r" \textbf{W} is Whisper "
        r"large-v3, \textbf{P} and Parakeet are Parakeet-TDT, \textbf{Q} and "
        r"Qwen3 are Qwen3-ASR, and \textbf{G} is Google Chirp~2. Whisper-ts is "
        r"Whisper-timestamped and NeMo-FA its conformer checkpoint. The APIs are "
        r"Speechmatics Enhanced, Deepgram Nova-3, IBM Large US English, Azure "
        r"en-US, AssemblyAI Universal~3.5 Pro, Amazon Transcribe en-US, "
        r"ElevenLabs Scribe~v2, Google Chirp~2 and \emph{Olign}~1.0."
        + _no_noisy_note(m, _TABLE_ROWS["word"]) +
        r" \emph{MFA} is Montreal Forced Aligner 3.4. "
        r"MAPS trained on 7 of 8 speakers in both Buckeye splits.}",
        r"\label{tab:main}",
        word,
        r"\end{table}",
        "",
        r"\begin{table}[!t]", *setup,
        r"\caption{\small Phone-tier boundary error on the test split of "
        r"each corpus, on clean audio and under degradation, \emph{noisy} "
        r"being the mean of the four, laid out as Table~\ref{tab:main}. The "
        r"dev splits are in \texttt{records/}\recfn. Every Track~1 aligner "
        r"is given the reference words and derives its own phones, and PER "
        r"is the phone error rate of what it derived against the gold "
        r"phones, per split and condition. FALCON, daggered, is handed the "
        r"gold phones, and overlaps our Buckeye split in its training data. "
        r"We use the FALCON released model and did not retrain it. No "
        r"one-step ASR in Table~\ref{tab:main} emits phone timestamps, so "
        r"Track~2 has only the two-step rows whose aligner does, and their "
        r"PER carries the recognizer's word errors too. The granularity of "
        r"a phone boundary is the Grid column of Table~\ref{tab:class}.}",
        r"\label{tab:phone}",
        phone,
        r"\end{table}",
    ])


#: Cells and tiers of the signed-bias table, in print order.
BIAS_CELLS = ("timit/dev", "buckeye/dev")
BIAS_TIERS = ("word", "phone")
#: Display names shared by two recipes, disambiguated by key in the table.
_BIAS_DUP: set = set()


def load_onset_bias() -> dict:
    """The cached signed biases, or {} if nobody has measured them yet.

    Measured rather than scored, like the Grid column, and cached because
    reading every hypothesis on both tiers takes minutes and this generator
    runs on every build. Refresh with `evals/measure_onset_bias.py --refresh`.
    """
    spec = importlib.util.spec_from_file_location(
        "mob", ROOT / "evals" / "measure_onset_bias.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_cache()


def onset_bias_table(m) -> str:
    """Median signed onset and offset error, both tiers, both dev splits.

    WHY THE SUPPLEMENT CARRIES THIS. Boundary MAE is absolute, so a system
    whose boundaries are uniformly 60 ms late and one whose boundaries scatter
    60 ms either way earn the same number, and only the second is irreducible.
    The signed median separates them, and it turns out to order the field:
    across the systems here the correlation between |onset bias| and word
    boundary $F_1$ is $-0.80$, which is a better single predictor than the
    timestamp grid.
    """
    data = load_onset_bias()
    if not data:
        return ""
    tools = sorted({t for tier in BIAS_TIERS for t in data.get(tier, {})}
                   - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS)

    def get(tool, tier, cell, k):
        return (data.get(tier, {}).get(tool, {}).get(cell) or {}).get(k)

    def key(t):
        v = get(t, "word", "timit/dev", "onset")
        return (0, v) if v is not None else (1, get(t, "phone", "timit/dev", "onset") or 0)

    _seen = [cascade_label(disp_paper(m, t)) for t in tools]
    global _BIAS_DUP
    _BIAS_DUP = {n for n in _seen if _seen.count(n) > 1}
    rows = []
    for t in sorted(tools, key=key):
        cells = []
        for tier in BIAS_TIERS:
            for cell in BIAS_CELLS:
                for k in ("onset", "offset"):
                    v = get(t, tier, cell, k)
                    # Blank, not a dash: a tier a system does not have is not a
                    # measurement of zero, and an em-dash is the one thing this
                    # document does not set.
                    cells.append("" if v is None else f"{v:+.1f}")
        if not any(cells):
            continue
        # cascade_label, not the raw display name: disp_paper returns a literal
        # U+2192 and this file is read by pdflatex.
        nm = cascade_label(disp_paper(m, t))
        # Two recipes are both called TorchAudio, the forced aligner and the
        # ASR. Adjacent here with nothing between them, so the key says which.
        if nm in _BIAS_DUP:
            nm += r" {\scriptsize(FA)}" if t.endswith("_fa") else r" {\scriptsize(ASR)}"
        rows.append(f"{_arch_label(m, t):<12} & {nm + cite_for(t):<26} & "
                    + " & ".join(f"{c:>7}" for c in cells) + r"\\")
    head = [
        r"\begin{table}[!t]", r"\centering", r"\footnotesize",
        r"\caption{Mean signed boundary error in ms, hypothesis minus "
        r"reference, over the units the label alignment paired. Negative is "
        r"early, and start and end are the word's or the phone's. Boundary MAE "
        r"is absolute and cannot tell a system whose "
        r"boundaries are uniformly late from one whose boundaries scatter, "
        r"and only the second is irreducible. The CTC aligners run 34 to "
        r"72\,ms late at the word onset whether they are open or sold, which "
        r"is the emission delay of the architecture rather than a property of "
        r"any vendor, while Whisper's own timestamps are early by more than "
        r"twice that. Measured by \texttt{evals/measure\_onset\_bias.py}.}",
        r"\label{tab:bias}",
        r"\setlength{\tabcolsep}{2.6pt}",
        r"\begin{tabular}{@{}ll" + "rr" * (len(BIAS_CELLS) * len(BIAS_TIERS)) + r"@{}}",
        r"\toprule",
        r"& & \multicolumn{4}{c}{\textbf{Word tier}} & "
        r"\multicolumn{4}{c}{\textbf{Phone tier}}\\",
        r"\cmidrule(lr){3-6}\cmidrule(lr){7-10}",
        r"& & \multicolumn{2}{c}{TIMIT dev} & \multicolumn{2}{c}{Buckeye dev}"
        r" & \multicolumn{2}{c}{TIMIT dev} & \multicolumn{2}{c}{Buckeye dev}\\",
        r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}\cmidrule(lr){9-10}",
        r"Family & System & " + " & ".join(
            r"{\scriptsize " + x + "}" for x in ("start", "end") * 4) + r"\\",
        r"\midrule",
    ]
    return "\n".join(head + rows + [r"\bottomrule", r"\end{tabular}",
                                    r"\end{table}"])



#: Two categorical slots from the data-viz reference palette, in fixed order.
#: Onset is slot 1 and offset is slot 2; the pair's separation is on record in
#: that palette (adjacent CVD $\Delta E$ 9.1, normal-vision 19.6).
BIAS_COLOR = {"onset": "2a78d6", "offset": "eb6834"}


def bias_rows_paper(m) -> set:
    """Track 1, plus the Track 2 systems that time the words they decoded.

    The two-step cascades are left out. A cascade's bias is its ALIGNER's --
    Qwen3-ASR to Olign sits on Olign's +0.5 and Whisper to WhisperX on
    WhisperX's +59 -- so plotting them repeats rows already on the figure and
    says nothing about the recognizer that supplied the words. The blocks are
    taken from the table's own definition rather than from the tool names, so
    the figure and Table~1 cannot disagree about which row is which.
    """
    a = set(collect("aligners", "wbe_ms"))
    t = {x for x in collect("timestamp_asrs", "wbe_ms") if m.pipe(x) == "one-step"}
    return (a | t) - m.SUPPRESS_PUBLIC - PAPER_SUPPRESS


#: Names shortened for the scatter, where a label is a box that has to find
#: somewhere to sit rather than a row in a column.
BIAS_SHORT = {
    # PAPER_SHORT cuts this one for the table's System column; the plot has
    # room and the reader there is matching a mark to a system, not scanning
    # a column.
    "CrisperW": "CrisperWhisper",
    "Whisper large-v3": "Whisper-v3", "Whisper-timestamped": "Whisper-ts",
    "AssemblyAI Universal 3.5": "AssemblyAI", "Speechmatics enhanced": "Speechmatics",
    "ElevenLabs Scribe v2": "ElevenLabs", "Deepgram Nova-3": "Deepgram",
    "Google Chirp 2": "Google", "NeMo-FA conformer": "NeMo-FA",
    # Only one NeMo-FA reaches the plot, so the grid in its name is width
    # spent on a distinction the figure does not draw.
    "NeMo-FA 40 ms": "NeMo-FA",
    "IBM Watson Large": "IBM", "Azure AI Speech": "Azure",
    "Parakeet-TDT": "Parakeet", }

#: Where a label may sit relative to its dot, tried in this order and at each
#: radius in turn. East first, because a label reads left to right and the eye
#: finds it fastest there.
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1),
         (0.92, 0.38), (-0.92, 0.38), (0.92, -0.38), (-0.92, -0.38),
         (0.71, 0.71), (-0.71, 0.71), (0.71, -0.71), (-0.71, -0.71),
         (0.38, 0.92), (-0.38, 0.92), (0.38, -0.92), (-0.38, -0.92)]
#: Rings a label is tried on, nearest first. The first two sit close enough to
#: their mark to need no leader line, and a label only gets one once it has
#: been pushed past them.
_RADII = (7.0, 10.0, 13.5, 18.0, 24.0, 31.0, 40.0, 50.0, 62.0)
#: Past this, the label is far enough from its mark to need the line. Set
#: generously: a leader is uglier than a label sitting a few points off its
#: mark, and with the rings this close every label lands beside its own dot.
_LEADER_AT = 20.0
#: Labels placed by hand, in WARPED axis coordinates, always with a leader.
#: The solver puts Speechmatics west of its own dot, inside the tightest
#: cluster on the panel. On the top edge it is clear of Azure and IBM and
#: its leader still says which dot is its own.
_LABEL_AT = {"Speechmatics": (2.98, 3.86)}


def _place_labels(pts, w_pt, h_pt, xlo, xhi, ylo, yhi):
    """Greedy non-overlapping label placement, in points, around each dot.

    Nine of the twenty-five systems sit inside a 15 by 12 ms box around the
    origin, so their labels cannot all go beside their dots. Each label takes
    the first free slot in `_DIRS` at the smallest radius in `_RADII` that
    clears every label and dot already placed, and gets a leader line when it
    ends up far enough away to be ambiguous. Isolated points are placed first,
    so the crowded ones inherit whatever room is left rather than the reverse.
    """
    sx, sy = w_pt / (xhi - xlo), h_pt / (yhi - ylo)
    def to_pt(x, y):
        return ((x - xlo) * sx, (y - ylo) * sy)
    # crowding: how many other dots sit within 25 pt
    dots = [to_pt(x, y) for x, y, _ in pts]
    crowd = [sum(1 for q in dots
                 if (q[0] - d[0]) ** 2 + (q[1] - d[1]) ** 2 < 625) for d in dots]
    order = sorted(range(len(pts)), key=lambda k: crowd[k])
    boxes = [(d[0] - 1.6, d[1] - 1.6, d[0] + 1.6, d[1] + 1.6) for d in dots]
    out = {}
    for k in order:
        dx0, dy0 = dots[k]
        tw = 3.6 * len(pts[k][2]) + 3.0
        th = 8.2
        best = None
        for r in _RADII:
            for ux, uy in _DIRS:
                cx = dx0 + ux * (r + tw / 2 if ux else 0)
                cy = dy0 + uy * (r + th / 2 if uy else 0)
                bx = (cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2)
                # Inside the plot box, near enough. Letting labels run into
                # the margin put one past the column edge and sat two others
                # on the tick row. Raising the right bound does not free the
                # top right corner either: what blocks Speechmatics from
                # sitting east of its dot is IBM's label, 6 ms above it, and
                # clearing that label needs 80pt of overhang, which is the
                # other column.
                if (bx[0] < -10 or bx[2] > w_pt + 12
                        or bx[1] < 0 or bx[3] > h_pt + 8):
                    continue
                if any(not (bx[2] < o[0] or bx[0] > o[2]
                            or bx[3] < o[1] or bx[1] > o[3]) for o in boxes):
                    continue
                best = (cx, cy, r, bx)
                break
            if best:
                break
        if not best:                      # nowhere free: sit on the dot
            best = (dx0 + tw / 2 + 5, dy0, _RADII[-1],
                    (dx0 + 5, dy0 - th / 2, dx0 + 5 + tw, dy0 + th / 2))
        boxes.append(best[3])
        # A leader when the label is far out, as before, and ALSO when another
        # dot is NEARER the label box than its own dot is. Radius alone drew no
        # leader anywhere on TIMIT test, and missed Speechmatics and Amazon,
        # each a short hop from its dot with a neighbour's dot inside that hop.
        # Measured margins split cleanly at zero: the mispaired labels run
        # -1.1 to -6.6 pt and the next clear one is +0.3, so no slack is added.
        def box_dist(bx, q):
            ddx = max(bx[0] - q[0], 0, q[0] - bx[2])
            ddy = max(bx[1] - q[1], 0, q[1] - bx[3])
            return (ddx * ddx + ddy * ddy) ** 0.5
        own = box_dist(best[3], dots[k])
        other = min((box_dist(best[3], dots[j]) for j in range(len(dots)) if j != k),
                    default=1e9)
        ambiguous = other < own
        out[k] = (xlo + best[0] / sx, ylo + best[1] / sy,
                  best[2] > _LEADER_AT or ambiguous)
    return out


#: Softening constant of the axis transform, in ms. Below it the axis is
#: effectively linear, above it logarithmic.
BIAS_K = 4.0
#: Tick positions in REAL ms. The axis is warped, the labels are not.
BIAS_TICKS = (-100, -50, -25, -10, -5, 0, 5, 10, 25, 50, 100)
#: The frame stops here on both axes. Everything interesting is above it and
#: the three systems below are drawn on the edge with their real numbers, so
#: the cut costs the reader nothing and buys the middle of the field the room
#: it needs.
BIAS_FLOOR = -15.0
#: Both cuts sit at -15, which is where the marks are. At -5 the figure named
#: NeMo-FA at -11, WhisperX at -6 and Charsiu at -12 on the edge, so three of
#: the four aligners the plot exists to place were text rather than points,
#: and WhisperX missed the frame by 1 ms. Whisper around -150 and TorchAudio
#: at -25 are still outside, which is the pair worth excluding.
BIAS_FLOOR_X = -15.0
#: And stops here at the top, above the highest system, which is the room the
#: Azure, IBM and Speechmatics corner needs for its labels.
BIAS_CEIL = 100.0


def _warp(v: float) -> float:
    """asinh(v/k): linear through zero, logarithmic in the tails.

    WHY THE AXIS IS NOT LINEAR. Nine of these systems sit inside a few ms of
    the origin and two sit at -137, so on a linear axis the interesting half of
    the field is a smudge. asinh is the standard way out: it is smooth and
    odd, so zero stays zero and the diagonal stays the diagonal, and it is
    linear for |v| well under BIAS_K, which keeps the near-zero spacing honest
    rather than exaggerating it the way a signed log would. At k=4 the first
    10\\,ms take 39% of the half-axis against 7% linear. Ticks are labeled in
    real ms, so nothing has to be read off the warp.
    """
    import math
    return math.asinh(v / BIAS_K)


def _unwarp(w: float) -> float:
    """Back to ms, for labeling a point the frame had to clamp."""
    import math
    return math.sinh(w) * BIAS_K


#: The three things the figure compares, with a mark that survives greyscale.
#: Shape carries the grouping and color only repeats it, because a printed
#: copy has no color and the referee reading it should not be worse off.
#: SHAPE is the pipeline and FILL is the access, so the figure's two questions
#: sit on two channels and neither needs color. Olign is commercial and
#: reaches this figure as a cascade, so marking access on the one-step rows
#: alone would have hidden the row a reader is most entitled to see marked.
BIAS_GROUPS = (
    ("one step, open", "o", "2a78d6"),
    ("one step, commercial", "*", "eb6834"),
    ("two steps, open aligner", "triangle", "2a78d6"),
    ("two steps, commercial aligner", "triangle*", "eb6834"),
)


#: Rows the figure carries that the paper's tables do not. Three more Qwen3
#: cascades, so the aligner families are represented rather than only their
#: best members, and WhisperX over its own Whisper decode, which is the
#: pairing a reader of Table 1 comes looking for.
BIAS_EXTRA = ("whisperx_asr", "nemo_fa_conformer_on_qwen3asr",
              "maps_on_qwen3asr", "charsiu_on_qwen3asr")
#: And one it drops. Whisper-timestamped lands within a few ms of Whisper
#: large-v3 on both axes and both are off the frame, so the pair spends two
#: edge labels saying one thing.
BIAS_DROP = ("whisper_ts",)


def bias_rows_track2(m, everything: bool = False):
    """`{tool: group index}` for Track 2, one step against two.

    The two-step rows are the cascades over Qwen3-ASR's transcript, so the
    recognizer is held fixed and what is left is the aligner. `everything`
    takes the whole of records/ rather than the rows the paper prints.
    """
    t2 = collect("timestamp_asrs", "wbe_ms")
    out = {}
    for t in t2:
        if not everything and (t in m.SUPPRESS_PUBLIC or t in PAPER_SUPPRESS
                               or t in BIAS_DROP):
            continue
        # m.fam resolves a cascade to its ALIGNER, which is what decides
        # whether the timing on the plot is open or bought.
        paid = m.fam(t) == "proprietary"
        if m.pipe(t) == "one-step":
            out[t] = 1 if paid else 0
        elif t == "qwen3_asr" or t.endswith("_on_qwen3asr"):
            out[t] = 3 if paid else 2
    if not everything:
        for t in BIAS_EXTRA:
            if t in t2 and t not in out:
                out[t] = 3 if m.fam(t) == "proprietary" else 2
    # TRACK 1 STAYS OUT. The figure holds the recognizer fixed so that what
    # varies is the aligner, and a row handed the reference words is a
    # different setting rather than another point in this one. The claim that
    # the bias survives being given the words is carried by the number in the
    # contribution, not by mixing two settings on one pair of axes.
    return out


def onset_bias_scatter(m, cell: str = "timit/core_test", tier: str = "word",
                       groups: dict | None = None, env: str = "figure",
                       side: float = 156.8, floor_ms: float | None = BIAS_FLOOR,
                       ceil_ms: float | None = BIAS_CEIL) -> str:
    """Onset against offset, one labeled mark per system, on a warped axis.

    A bar of the onset alone says a system is late. It cannot say whether the
    whole word moved or only its front. Here the dashed diagonal is the uniform
    shift, where onset and offset move together and the word keeps its
    duration, and distance from it is the duration error. Track 2's one-step
    rows scatter along and below it; the cascades collapse onto the origin,
    because a cascade's timing is its aligner's.
    """
    data = load_onset_bias().get(tier, {})
    groups = groups if groups is not None else bias_rows_track2(m)
    def short_name(t: str) -> tuple:
        """`(name, was a cascade)`. A cascade is named by its aligner alone.

        The caption names the recognizer once and the triangle says two steps,
        so the arrow is weight on the labels that can least afford it, and the
        three cascades were the only ones the placer had to push off their
        marks.
        """
        nm = unshrink(cascade_label(disp_paper(m, t)))
        casc = " $\\to$ " in nm
        if casc:
            nm = nm.split(" $\\to$ ", 1)[1]
        for long, short in BIAS_SHORT.items():
            nm = nm.replace(long, short)
        return nm, casc

    order = sorted(groups, key=lambda t: data.get(t, {}).get(cell, {}).get("onset", 0))
    live = [t for t in order if data.get(t, {}).get(cell)]
    # Collisions are judged on the FINAL name. Dropping the arrow makes the
    # supplement's one-step TorchAudio and its Qwen3-ASR cascade both read
    # "TorchAudio", so where that happens the arrow goes back on the cascade.
    names = [short_name(t)[0] for t in live]
    clash = {n for n in names if names.count(n) > 1}
    final = {}
    for t in live:
        nm, casc = short_name(t)
        if nm in clash and casc:
            nm = "$\\to$" + nm
        final[t] = nm
    # Two MFA cascades survive that, 2.0 and 3.4, because disp_paper drops the
    # version. Where a name is still shared, the version comes back.
    again = {n for n in final.values() if list(final.values()).count(n) > 1}
    for t, nm in list(final.items()):
        if nm in again:
            ver = unshrink(cascade_label(m.disp(t))).split("$\\to$")[-1].strip()
            final[t] = ("$\\to$" if nm.startswith("$\\to$") else "") + ver
    pts = [(_warp(data[t][cell]["onset"]), _warp(data[t][cell]["offset"]),
            final[t], groups[t]) for t in live]
    if not pts:
        return ""
    # The paper's figure is cut so the middle of the field has room. The
    # supplement's is not: ten of its systems sit below the cut and a frame
    # edge crowded with ten arrows is worse than a wide frame.
    lowest = min(min(p[0] for p in pts), min(p[1] for p in pts)) * 1.06
    fy = _warp(floor_ms) if floor_ms is not None else lowest
    fx = _warp(BIAS_FLOOR_X) if floor_ms is not None else lowest
    hi = (_warp(ceil_ms) if ceil_ms is not None
          else max(max(p[0] for p in pts), max(p[1] for p in pts)) * 1.06)
    # Off-scale points keep their identity and their real numbers; only their
    # DRAWN position is clamped, and an arrow says the value continues past
    # the edge. A mark at a clamped spot would assert a position it does not
    # have, so off-scale rows get an arrow instead of a mark.
    shown, off = [], []
    for x, y, nm, gi in pts:
        if x < fx or y < fy:
            ox = -1 if x < fx else 0
            oy = -1 if y < fy else 0
            v = _unwarp(x), _unwarp(y)
            # Clamped a little INSIDE the frame, not onto it. On the frame the
            # label sits level with the lowest tick label and the two read as
            # one string, which is how "-25" came to look like part of
            # Whisper's value.
            inset = 0.05 * (hi - fx)
            off.append((max(x, fx + inset), max(y, fy + inset), ox, oy,
                        f"{nm} ({v[0]:.0f}, {v[1]:.0f})", gi))
        else:
            shown.append((x, y, nm, gi))
    allp = [(x, y, nm) for x, y, nm, _ in shown] + [(x, y, nm) for x, y, _, _, nm, _ in off]
    lab = _place_labels(allp, side, side, fx, hi, fy, hi)
    for _k, (_x, _y, _nm) in enumerate(allp):
        if _nm in _LABEL_AT:
            lab[_k] = (*_LABEL_AT[_nm], True)
    label = {"timit/dev": "TIMIT dev", "timit/core_test": "TIMIT test",
             "buckeye/dev": "Buckeye dev", "buckeye/test": "Buckeye test"}[cell]
    # Four decimals on the limits: at two, xmax rounded DOWN below the 100
    # tick and pgfplots dropped it off the edge.
    xt = [t for t in BIAS_TICKS if fx <= _warp(t) <= hi]
    yt = [t for t in BIAS_TICKS if fy <= _warp(t) <= hi]
    L = [r"% GENERATED by evals/gen_paper_tables.py -- do not edit.",
         r"\begin{" + env + r"}[!t]", r"\centering"]
    for _, _, hexc in BIAS_GROUPS:
        L.append(r"\definecolor{bias" + hexc + r"}{HTML}{" + hexc + "}")
    L += [r"\begin{tikzpicture}",
          r"\begin{axis}[",
          # `side` is the HEIGHT and the width follows the RANGES. The two
          # axes no longer span the same number of warped units, and a square
          # box would draw $y=x$ at 40 degrees and invite the reader to
          # measure a distance from a line that is not where they think it
          # is. Taking it out of the width rather than adding it to the height
          # keeps the float the size the page was laid out around.
          r"  width=" + f"{side * (hi - fx) / (hi - fy):.0f}"
          + r"pt, height=" + f"{side:.0f}" + r"pt,",
          r"  scale only axis, clip=false,",
          r"  xmin=" + f"{fx:.4f}" + r", xmax=" + f"{hi:.4f}"
          + r", ymin=" + f"{fy:.4f}" + r", ymax=" + f"{hi:.4f}" + r",",
          r"  xlabel={Mean Signed Word Start Error (ms)},",
          r"  ylabel={Mean Signed Word End Error (ms)},",
          r"  xlabel style={font=\small}, ylabel style={font=\small},",
          r"  xticklabel style={font=\footnotesize},",
          r"  yticklabel style={font=\footnotesize},",
          r"  xtick={" + ",".join(f"{_warp(t):.4f}" for t in xt) + r"},",
          r"  xticklabels={" + ",".join(str(t) for t in xt) + r"},",
          r"  ytick={" + ",".join(f"{_warp(t):.4f}" for t in yt) + r"},",
          r"  yticklabels={" + ",".join(str(t) for t in yt) + r"},",
          r"  axis line style={draw=black!35, line width=0.3pt},",
          r"  tick style={draw=black!35},",
          r"  grid=major, grid style={draw=black!7, line width=0.3pt},",
          r"  legend style={font=\footnotesize, at={(0.5,1.02)}, anchor=south,",
          r"                legend columns=2, draw=none, fill=none, column sep=3pt},",
          r"]",
          r"\addplot[draw=black!22, line width=0.4pt, dashed, forget plot] coordinates "
          r"{(" + f"{max(fx, fy):.4f},{max(fx, fy):.4f}" + r") (" + f"{hi:.4f},{hi:.4f}" + r")};",
          r"\addplot[draw=black!45, line width=0.4pt, forget plot] coordinates "
          r"{(" + f"{fx:.4f}" + r",0) (" + f"{hi:.4f}" + r",0)};",
          r"\addplot[draw=black!45, line width=0.4pt, forget plot] coordinates "
          r"{(0," + f"{fy:.4f}" + r") (0," + f"{hi:.4f}" + r")};"]
    n_shown = len(shown)
    for k, (x, y, nm) in enumerate(allp):
        lx, ly, leader = lab[k]
        # Never for an off-scale row: its drawn position is a clamp, not a
        # measurement, and a line to it would point at a place the system is
        # not. The label carries the real pair instead.
        if leader and k < n_shown:
            # Visible at print size. 30 percent black at 0.2pt vanished, which
            # is why a reader saw no leaders at all. Still lighter than the
            # off-scale arrows so the two kinds of line stay distinct.
            L.append(r"\draw[draw=black!85, line width=0.45pt] (axis cs:"
                     f"{x:.3f},{y:.3f}" r") -- (axis cs:" f"{lx:.3f},{ly:.3f}" r");")
        # An off-scale label is named so an arrow can leave it. The arrow
        # runs from the side of the label that faces the missing point and
        # ends on the frame, which says the system is out there without
        # claiming a position for it.
        nid = "" if k < n_shown else f"(offlab{k - n_shown}) "
        L.append(r"\node[font=\footnotesize, inner sep=0.5pt, fill=white, "
                 r"fill opacity=0.8, text opacity=1] " + nid + r"at (axis cs:"
                 f"{lx:.3f},{ly:.3f}" r") {" + nm + r"};")
        if k >= n_shown:
            ox, oy = off[k - n_shown][2], off[k - n_shown][3]
            # The leader ends on the frame at the coordinate the system really
            # has on whichever axis is still in range, so a row that is off the
            # bottom but on scale horizontally gets an arrow under its true x.
            # It then travels away from the label rather than straight down
            # through whatever labels sit below it.
            anchor = ("south west" if ox and oy else "west" if ox else "east")
            ex = f"{fx:.4f}" if ox else f"{x:.3f}"
            ey = f"{fy:.4f}" if oy else f"{y:.3f}"
            # Curved and darker than the in-plot leaders, so the eye reads it
            # as "the point is out there" rather than as another hairline. The
            # bow carries it clear of the labels between the two ends.
            bend = "left" if ox and oy else "left=45"
            bend = bend if "=" in bend else bend + "=20"
            L.append(r"\draw[draw=black, line width=0.7pt, "
                     r"-{Stealth[length=2.6pt,width=2.6pt]}] "
                     f"(offlab{k - n_shown}.{anchor}) to[bend {bend}] "
                     f"(axis cs:{ex},{ey});")
    for gi, (gname, mark, hexc) in enumerate(BIAS_GROUPS):
        co = [q for q in shown if q[3] == gi]
        if co:
            L.append(r"\addplot[only marks, mark=" + mark + r", mark size=2.3pt, "
                     r"draw=bias" + hexc + r", fill="
                     + ("bias" + hexc if mark.endswith("*") else "white")
                     + r", line width=0.7pt] "
                     r"coordinates {"
                     + " ".join(f"({x:.3f},{y:.3f})" for x, y, _, _ in co) + "};")
            L.append(r"\addlegendentry{" + gname + r"}")
    L += [r"\end{axis}", r"\end{tikzpicture}",
          r"\caption{\small Mean signed word-boundary error on " + label + r", "
          r"hypothesis minus reference, over the words the label alignment "
          r"matched. Track~2 only. Every two-step point aligns Qwen3-ASR's "
          r"transcript, so the recognizer is fixed and only the aligner varies. "
          r"Both axes are warped by $\mathrm{asinh}(v/4)$. The distance from "
          r"the dashed line $y=x$ is the mean error in word duration.}",
          r"\label{fig:bias-" + cell.replace("/", "-") + "-" + tier
          + ("-all" if len(pts) > 20 else "") + r"}",
          # \textfloatsep is set with "minus 5pt", so it collapses to nothing
          # and the next section heading sits on the caption. Give this float
          # its own floor.
          r"\vspace{5pt}",
          r"\end{" + env + r"}"]
    return "\n".join(L)


def wer_table(m) -> str:
    """Table 3: recognition quality behind Track 2.

    Every system that decodes its own words -- the one-step rows -- plus
    Qwen3-ASR, whose decode the twelve two-step rows all align. The two-step
    rows themselves are NOT listed: they share their source's transcript, so a
    per-row list repeated one figure twelve times and buried the comparison
    that matters. WER alone: the S/D/I split is a different question and cost
    eight more columns than the page has.
    """
    wer = collect("timestamp_asrs", "wer")

    _srcs = {t for t, _ in CASCADE_SOURCES}

    def vals_for(tool):
        """One value per column, None where the cell was never run.

        A MISSING CELL USED TO DROP THE WHOLE ROW, which deleted ElevenLabs
        from this table entirely -- and ElevenLabs has the lowest clean WER of
        any recognizer here, so the one row a reader would most want to check
        was the one row that was not there. Table 1 already blanks the cells it
        lacks rather than dropping the system, and this now matches it. A row
        with no values at all is still dropped.
        """
        vals = []
        for cell, cond in cell_cond_plan():
            v = wer.get(tool, {}).get(cell)
            vals.append(v[cond] if v else None)
        return None if all(v is None for v in vals) else vals

    # Lowest WER per column, over every row the table will show -- one-step
    # systems and cascade sources together, so the bold marks the best
    # recogniser on that split and not the best within its own block.
    _all = [v for v in (vals_for(t) for t in
                        [x for x in sorted(wer) if m.pipe(x) == "one-step"
                         or x in _srcs]) if v]
    # min over the values PRESENT in each column. A column where one system was
    # not run is still a real column for everyone who was.
    best = [min([v for v in col if v is not None], default=None)
            for col in zip(*_all)] if _all else []

    def row_for(tool, label):
        vals = vals_for(tool)
        if vals is None:
            return None
        cells = []
        for i, v in enumerate(vals):
            if v is None:
                cells.append("---")
            elif best and best[i] is not None and v == best[i]:
                cells.append(r"\textbf{" + f"{v:.1f}" + "}")
            else:
                cells.append(f"{v:.1f}")
        return label + " & " + " & ".join(cells) + r"\\"

    # One-step systems in the same family order Table 2 lists them, so the two
    # tables can be read against each other row for row.
    one_step = [t for t in sorted(wer) if m.pipe(t) == "one-step" and t not in _srcs]
    rows, seen = [], set()
    for _, _, _, tool, _ in order(m, one_step, collect("timestamp_asrs", "wbe_ms")):
        r = row_for(tool, disp_paper(m, tool))
        if r:
            rows.append(r)
            seen.add(tool)
    # then the cascade transcript source, set apart: it is here as the input to
    # twelve other rows, not as a system being ranked beside these.
    extra = [(t, l) for t, l in CASCADE_SOURCES if t not in seen]
    if extra and rows:
        # A hair of space, not booktabs' default 0.5em -- enough to say this row
        # is here for a different reason, not enough to read as a section break.
        rows.append(r"\addlinespace[2pt]")
    for tool, label in extra:
        r = row_for(tool, label)
        if r:
            rows.append(r)
    if not rows:
        return ""

    first = 2                                 # one lead column
    # "TIMIT clean" in one row rather than a TIMIT span above a clean span, as
    # in Tables 1 and 2: the columns beneath are wider than the label either way.
    # corpus_order()/splits_of() rather than a local named `order`, which
    # shadowed the module-level row-ordering function of the same name.
    spans, rules, col = [], [], first
    # CELLS, not the paper's narrowed view: this table is the supplement's and
    # still carries every split. Without it the spans collapsed to one column
    # and the header no longer covered its numbers.
    for corpus in corpus_order(CELLS):
        for cond in ("clean", "noisy"):
            w = len(splits_of(corpus, CELLS))
            spans.append(
                f"\\multicolumn{{{w}}}{{c}}{{{CORPUS_LABEL[corpus]} {cond}}}")
            rules.append(f"\\cmidrule(lr){{{col}-{col + w - 1}}}")
            col += w
    plan = cell_cond_plan()

    return "\n".join([
        r"\begin{table}[!t]", r"\centering",
        r"\caption{Word error rate (\%) of the Track~2 systems that decode their "
        r"own words, and of Qwen3-ASR, whose transcript the twelve two-step rows "
        r"align. Those rows are not listed: each carries its source's WER. "
        r"\emph{Noisy} is the mean of the four degradations.}",
        r"\label{tab:wer}",
        r"\small",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}l" + ("rr" + "@{\\hspace{8pt}}") * (len(CELLS) - 1)
        + r"rr@{}}",
        r"\toprule",
        "& " + " & ".join(spans) + r"\\",
        "".join(rules),
        "Recognizer & " + " & ".join(r"{\scriptsize " + SPLIT_LABEL[c] + "}"
                                     for c, _ in plan)
        + r"\\",
        r"\midrule"] + rows + [r"\bottomrule", r"\end{tabular}", r"\end{table}"])


def sdi_table(m) -> str:
    """Table 4: Table 3's rows and columns, with WER broken into S, D and I.

    Full width: four splits x two conditions x four metrics is 32 numeric
    columns, which no single column holds at a readable size. Same rows and the
    same ordering as Table~3 so the two can be read against each other; WER is
    repeated rather than dropped because it is the sum a reader checks the parts
    against.
    """
    src = {k: collect("timestamp_asrs", c) for k, c in
           (("WER", "wer"), ("S", "w_sub_pct"), ("D", "w_del_pct"), ("I", "w_ins_pct"))}
    METRICS = ("WER", "S", "D", "I")
    _srcs = {t for t, _ in CASCADE_SOURCES}

    def vals_for(tool):
        out = []
        for cell, cond in cell_cond_plan():
            for k in METRICS:
                v = src[k].get(tool, {}).get(cell)
                out.append(v[cond] if v else None)
        # Blank the cell, do not drop the system. Same reason as Table 3: a row
        # that is missing its noisy half still carries its clean half, and
        # dropping it hid the lowest-WER recognizer in the benchmark.
        return None if all(v is None for v in out) else out

    def row_for(tool, label):
        v = vals_for(tool)
        return None if v is None else (
            label + " & " + " & ".join("---" if x is None else f"{x:.1f}"
                                       for x in v) + r"\\")

    rows, seen = [], set()
    one_step = [t for t in sorted(src["WER"]) if m.pipe(t) == "one-step" and t not in _srcs]
    for _, _, _, tool, _ in order(m, one_step, collect("timestamp_asrs", "wbe_ms")):
        r = row_for(tool, disp_paper(m, tool))
        if r:
            rows.append(r); seen.add(tool)
    extra = [(t, l) for t, l in CASCADE_SOURCES if t not in seen]
    if extra and rows:
        rows.append(r"\addlinespace[2pt]")
    for tool, label in extra:
        r = row_for(tool, label)
        if r:
            rows.append(r)
    if not rows:
        return ""

    per_split = len(METRICS)                 # 4 columns under one split
    per_cond = 2 * per_split                 # dev + test, inside one condition
    first = 2                                # one lead column

    def spans(width, labels, start=first):
        cells, rules, col = [], [], start
        for lab in labels:
            cells.append(f"\\multicolumn{{{width}}}{{c}}{{{lab}}}")
            rules.append(f"\\cmidrule(lr){{{col}-{col + width - 1}}}")
            col += width
        return "& " + " & ".join(cells) + r"\\", "".join(rules)

    corpora = [CORPUS_LABEL[c] for c in corpus_order()]
    plan = cell_cond_plan()
    # corpus and condition on one row, as in Tables 1 and 2
    r1, u1 = spans(per_cond, [f"{c} {w}" for c in corpora
                              for w in ("clean", "noisy")])
    r2, u2 = spans(per_split, [SPLIT_LABEL[c] for c, _ in plan])
    return "\n".join([
        r"\begin{table*}[!t]", r"\centering",
        r"\caption{Word error rate (\%) of Table~\ref{tab:wer}, split into its "
        r"substitution, deletion and insertion components. Same rows and order as "
        r"Table~\ref{tab:wer}; WER is repeated as the sum the parts should meet.}",
        r"\label{tab:sdi}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{1.0pt}",
        r"\begin{tabular}{@{}l" + "r" * (per_split * 2 * len(CELLS)) + r"@{}}",
        r"\toprule", r1, u1, r2, u2,
        "Recognizer & " + " & ".join(METRICS * (2 * len(CELLS))) + r"\\",
        r"\midrule"] + rows + [r"\bottomrule", r"\end{tabular}", r"\end{table*}"])



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "paper" / "tables.tex"))
    ap.add_argument("--out-supp",
                    default=str(ROOT / "docs" / "paper" / "tables_supp.tex"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if either file would change (for CI)")
    a = ap.parse_args(argv)
    m = load_tables_module()
    banner = ("% GENERATED by evals/gen_paper_tables.py from summary/ -- do not edit.\n"
              "% Same source as the published records, so the paper and the site\n"
              "% cannot disagree. \"Noisy\" is the mean of reverb, noise, music and\n"
              "% babble, exactly as the records pages define it.\n")
    # The paper carries the two boundary-error tables; the WER table and its
    # S/D/I decomposition go to the supplement, which has the room for 33
    # columns. Both files come off the same scored summaries in one run, so the
    # two documents cannot disagree either.
    # Word tier leads: word timestamps are what most readers of this benchmark
    # are choosing a system for, and the phone tier is the narrower question.
    # grid_table() is not emitted: the supplement's grid table already lists
    # every system with its phase, and Table 1's column could not pay for a
    # second copy once clean and noisy were both in.
    globals()["_SHORT_NAMES"] = True
    text = (banner + "\\newlength{\\fabdgt}\n\n"
            + (merged_table(m) if PAPER_MERGED else combined_table(m)) + "\n\n"
            + class_table(m) + "\n")
    globals()["_SHORT_NAMES"] = True
    # table* is a two-column float; the supplement is a one-column article, where
    # it is undefined. The S/D/I table is 33 columns and runs 130pt past a
    # one-column text block even so, hence its own landscape page: turning the
    # paper beats shrinking 7pt type another 22%.
    def onecol(t):
        return t.replace(r"\begin{table*}", r"\begin{table}") \
                .replace(r"\end{table*}", r"\end{table}")
    _fig = onset_bias_scatter(m)
    globals()["_SHORT_NAMES"] = False
    _figs = onset_bias_scatter(m, cell="timit/dev",
                               groups=bias_rows_track2(m, everything=True),
                               env="figure", side=372.0, floor_ms=None,
                               ceil_ms=None)
    if _figs:
        (pathlib.Path(a.out).parent / "fig_bias_supp.tex").write_text(_figs + "\n")
        print(f"wrote {pathlib.Path(a.out).parent / 'fig_bias_supp.tex'}")
    # The paper's figures live together in figs.tex, which paper.tex inputs
    # where the float should be allowed to start floating from.
    if _fig:
        (pathlib.Path(a.out).parent / "figs.tex").write_text(_fig + "\n")
        print(f"wrote {pathlib.Path(a.out).parent / 'figs.tex'}")
    _bias = onset_bias_table(m)
    if not _bias:
        print("note: no summary/onset_bias.json; run evals/measure_onset_bias.py "
              "--refresh to include Table 'bias'", file=sys.stderr)
    supp = (banner + onecol(wer_table(m)) + "\n\n"
            + "\\begin{landscape}\n" + onecol(sdi_table(m)) + "\n\\end{landscape}\n"
            + ("\n" + _bias + "\n" if _bias else ""))
    pairs = [(pathlib.Path(a.out), text), (pathlib.Path(a.out_supp), supp)]
    if a.check:
        stale = [o for o, t in pairs if (o.read_text() if o.is_file() else "") != t]
        for o in stale:
            print(f"STALE: {o}", file=sys.stderr)
        if stale:
            return 1
        print("up to date: " + ", ".join(str(o) for o, _ in pairs))
        return 0
    for o, t in pairs:
        o.write_text(t)
        print(f"wrote {o} ({t.count(chr(92) + chr(92))} table rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
