#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""What timestamp resolution does each system actually emit, and what does that
cap?

WHY THIS IS NOT A FOOTNOTE. A system that places boundaries only at multiples
of g milliseconds cannot land within a tolerance tau of an arbitrary reference
boundary more often than chance allows. For round-to-nearest the quantisation
error is uniform on [-g/2, g/2], so the share of reference positions reachable
within tau is

    min(1, 2 * tau / g)

At the 20 ms tolerance this benchmark reports, an 80 ms system is capped near
0.50 and a 40 ms one is not capped at all. That is not a small correction. It
is most of the gap between the 80 ms systems and the continuous ones, and
reading their F1 as an acoustic result rather than an arithmetic one is simply
wrong.

The grid is MEASURED, never declared, and in three readings, because one word
was hiding three things. A STEP is a global grid: 99% of offsets share one
residue modulo it, and the residue is the phase, since Olign places 80% of
its boundaries 3 or 8 ms past a 10 ms tick and a multiples-of-g test calls
that no grid at all. A FRAME is a per-utterance lattice: the torchaudio-style
aligners turn frame indices into seconds with a per-file ratio, so the step is
20.08 ms in one utterance and 20.14 ms in the next and no global modulus fits,
while within each utterance the gaps are exact multiples. WRITTEN AT is how
finely the numbers are expressed, 1 ms for Olign, AssemblyAI and WhisperX,
and a float for MAPS, which is the only system in which no lattice of any
kind was found. Vendors do not publish any of this and two have changed it
between releases without saying so, both times getting COARSER (Deepgram
nova-2 10 ms to nova-3 80 ms, IBM BroadbandModel 10 ms to 20 ms).

The second table is the part that matters for reading Table 1. It measures the
ceiling against the real gold boundaries rather than assuming they are uniform,
because a corpus whose annotators favoured round numbers would sit above the
theoretical figure.

    measure_grid.py
    measure_grid.py --tol-ms 50
    measure_grid.py --cell en/buckeye/dev/origin
"""
from __future__ import annotations

import argparse
import collections
import statistics
import glob
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: Gold manifests, one per evaluation split.
SPLITS = {
    "timit dev":       "timit__dev__*.jsonl",
    "timit core_test": "timit__*core_test*.jsonl",
    "buckeye dev":     "buckeye__paper__dev__*.jsonl",
    "buckeye test":    "buckeye__paper__test__*.jsonl",
}


def boundaries_ms(words) -> list[int]:
    out = []
    for w in words or []:
        if isinstance(w, dict):
            s, e = w.get("start"), w.get("end")
        else:
            s, e = w[1], w[2]
        for t in (s, e):
            if t is None:
                continue
            ms = round(float(t) * 1000)
            if ms > 0:
                out.append(ms)
    return out


#: Candidate steps, coarsest first. A system on 80 ms is also on 40, 20 and
#: 10, so the first that fits is the answer.
STEPS = (80, 40, 20, 10, 5, 2)
#: Share of boundaries that must sit on ONE residue of the step. Not 100%,
#: because three stray boundaries out of 3,134 once collapsed ElevenLabs from
#: a 20 ms grid to "continuous" under a GCD. And ONE RESIDUE, not residue
#: zero: Olign places 40% of its boundaries 3 ms past a 10 ms tick and 40%
#: 8 ms past it, which a multiples-of-g test scores as no grid at all.
ON_GRID = 0.99
#: A SECOND READING, for a system that quantises to a frame and then moves the
#: boundary WITHIN it. Olign is the case: 92% of its offsets sit at +0, +3 or
#: +8 ms past a 10 ms tick, onsets and offsets alike, so no single residue holds
#: anything like 99% and the strict test above calls it no grid at all. The
#: phase set is what gives the frame away, and it is scale-invariant: 3 phases
#: per 10 ms, 6 per 20, 24 per 80, all the same DENSITY of 0.3 phases per ms of
#: period, while folding to 5 ms merges two of them and the density doubles. The
#: frame is therefore the FINEST step at which the density is still at its
#: minimum. A system written at 1 ms with no lattice needs ~0.9 phases per ms at
#: every step, which is what MAX_PHASE_DENSITY rejects, so AssemblyAI and
#: WhisperX stay where they are.
MULTI_PHASE = 0.90
MAX_PHASE_DENSITY = 0.35
#: How close to the minimum density still counts as the minimum. The coarse
#: steps inherit the fine step's structure and land a few percent under it,
#: purely because 90% of the mass is reached a phase sooner.
DENSITY_SLACK = 1.15


def _residue_mass(us: list[int], g_us: int) -> tuple[float, int]:
    """Largest single-residue share of offsets modulo g, and that residue."""
    c = collections.Counter(v % g_us for v in us)
    r, n = c.most_common(1)[0]
    return n / len(us), r


def _phase_lattice(us: list[int]) -> tuple[int, int, float]:
    """`(step, phases, density)` for a frame with a sub-frame offset, or zeros.

    `phases` is how many residues modulo the step it takes to cover
    MULTI_PHASE of the offsets, and `density` is that count per ms of period.
    """
    best = None
    for g in STEPS:
        c = collections.Counter(v % (g * 1000) for v in us)
        acc = k = 0
        for _, n in c.most_common():
            acc += n
            k += 1
            if acc / len(us) >= MULTI_PHASE:
                break
        d = k / g
        if d <= MAX_PHASE_DENSITY and (best is None or d < best[2]):
            best = (g, k, d)
    if best is None:
        return 0, 0, 0.0
    # The finest step that is still within slack of the best density. Ties go
    # finer, because a coarse step only repeats the fine one's phases.
    floor = best[2] * DENSITY_SLACK
    for g in sorted(STEPS):
        c = collections.Counter(v % (g * 1000) for v in us)
        acc = k = 0
        for _, n in c.most_common():
            acc += n
            k += 1
            if acc / len(us) >= MULTI_PHASE:
                break
        if k / g <= floor:
            return g, k, k / g
    return best


#: A lattice whose phase is not a whole millisecond. Amazon writes its offsets
#: to 3 decimals but the value behind them sits on a half-millisecond, so every
#: offset comes out as one of TWO residues, k*10+9 or k*10+10, and neither the
#: single-residue test nor the phase lattice reads that as 10 ms. The reading
#: below asks the question the other two ask, with the rounding put back: what
#: is the coarsest step on which ON_GRID of the offsets lie within half a
#: millisecond of one phase. It runs AFTER the exact test, so a system already
#: on a clean grid is returned by that test and never reaches this one.
HALF_MS = 500                             # microseconds either side of a phase
#: The window is a whole millisecond wide, so it only says something when the
#: step is several times that. At 10 ms chance coverage is 10% and the 99% bar
#: is a real test; at 2 ms the window is half the period and EVERY system
#: written at 1 ms passes it, which is the degenerate reading the comment below
#: _phase_lattice warns about. So this reading stops at 10 ms.
MIN_HALFMS_STEP = 10


def _residue_mass_near(us: list[int], p: int, phase_ms: float) -> float:
    """Share of offsets within half a millisecond of `phase_ms` modulo `p`."""
    r = int(round(phase_ms * 1000))
    n = sum(1 for v in us
            if min((v % p - r) % p, (r - v % p) % p) <= HALF_MS)
    return n / len(us)


def _halfms_lattice(us: list[int]) -> tuple[int, float]:
    """`(step, phase in ms)` for a lattice read through millisecond rounding."""
    for g in (g for g in STEPS if g >= MIN_HALFMS_STEP):
        p = g * 1000
        # Phases on a half-millisecond grid: an offset rounded to the nearest
        # millisecond can only have come from one of these.
        best_r, best_n = 0, 0
        h = collections.Counter(v % p for v in us)
        for r in range(0, p, HALF_MS):
            n = sum(c for res, c in h.items()
                    if min((res - r) % p, (r - res) % p) <= HALF_MS)
            if n > best_n:
                best_r, best_n = r, n
        if best_n / len(us) >= ON_GRID:
            return g, best_r / 1000.0
    return 0, 0.0


def _per_utt_frame(utts: list[list[float]]) -> tuple[float | None, float]:
    """`(median frame in ms, share of utterances that fit one)`.

    THE TORCHAUDIO CASE. Several aligners turn a frame index into seconds with
    a per-file ratio, samples over frames, so their step is 20.08 ms in one
    utterance and 20.14 ms in the next and no global modulus ever fits. Within
    one utterance the lattice is exact, and that is where it is measured: the
    step is the smallest boundary gap or an integer fraction of it, accepted
    when 95% of the gaps in that utterance sit within 0.15 ms of a multiple.
    """
    frames = []
    fitted = 0
    for ts in utts:
        d = [(b - a) * 1000 for a, b in zip(ts, ts[1:]) if b - a > 0.0005]
        if len(d) < 3:
            continue
        best = (0.0, None)
        for k in (1, 2, 3, 4):
            s = min(d) / k
            if s < 4:
                continue
            fit = sum(min(x % s, s - x % s) <= 0.15 for x in d) / len(d)
            if fit > best[0]:
                best = (fit, s)
        if best[1] is not None and best[0] >= 0.95:
            fitted += 1
            frames.append(best[1])
    if not utts:
        return None, 0.0
    med = statistics.median(frames) if frames else None
    return med, fitted / len(utts)


#: The floor a 1 ms-written system must clear before its smallest gap is read
#: as a frame. WhisperX writes at 1 ms and never emits two boundaries closer
#: than exactly 20.000 ms; AssemblyAI writes at 1 ms and goes down to 1.000. A
#: system cannot place two boundaries inside one frame, so the first is
#: quantised and the second is not.
MIN_GAP_FLOOR = 4.0
#: ... and enough of its gaps must be multiples of that smallest one for it to
#: be a lattice rather than one close pair. Chance is about a tenth of this for
#: 1 ms-written times.
MIN_GAP_SHARE = 0.25


def _min_gap_frame(utts: list[list[float]]) -> float | None:
    """The smallest gap any utterance shows, when it reads as a frame.

    THE ROUNDED-LATTICE CASE. WhisperX runs a wav2vec2 frame like TorchAudio,
    about 20.1 ms rescaled per file, but writes its times to 1 ms. That
    rounding costs the per-utterance fit above its lattice: a ten-frame gap of
    200.8 ms is written 201, which is a millisecond off any multiple of 20, so
    the drift breaks the fit long before the frame does. What rounding cannot
    hide is that no two boundaries are ever closer than one frame.
    """
    gaps = [(b - a) * 1000 for ts in utts for a, b in zip(ts, ts[1:])
            if (b - a) * 1000 > 1e-6]
    if len(gaps) < 50:
        return None
    g = min(gaps)
    if g < MIN_GAP_FLOOR:
        return None
    # Half the write resolution each side, so a rounded multiple still counts.
    share = sum(1 for x in gaps if min(x % g, g - x % g) <= 0.6) / len(gaps)
    return g if share >= MIN_GAP_SHARE else None


def grid_of(path: str, cap: int, key: str = "words") -> dict:
    """What step, if any, the times are on, in three independent readings.

    `key` picks the tier, "words" or "phones", so a phone-only system such as
    FALCON can be measured on the tier it has.

    step        a global grid, with its phase, when 99% of offsets share one
                residue modulo the step
    written_at  the finest unit the numbers are expressed in, 1 ms or float
    frame       a per-utterance lattice, for systems that rescale a frame per
                file and so have no global step
    """
    utts, n = [], 0
    with open(path) as f:
        for line in f:
            if n >= cap:
                break
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = sorted({float(t) for w in (r.get(key) or [])
                         for t in ((w["start"], w["end"]) if isinstance(w, dict)
                                   else (w[1], w[2]))
                         if t is not None and t > 0})
            if ts:
                utts.append(ts)
            n += 1
    us = [round(t * 1e6) for ts in utts for t in ts]
    out = {"n": len(us), "step": 0, "phase": 0, "share": 0.0,
           "written_at": "float", "frame": None, "frame_share": 0.0,
           "phases": 1}
    if not us:
        return out
    for g in STEPS:
        share, r = _residue_mass(us, g * 1000)
        if share >= ON_GRID:
            out.update(step=g, phase=r / 1000.0, share=share, phases=1)
            return out

    # The same grid, read through millisecond rounding. Amazon needs this and
    # nothing else does; it is tried before the phase lattice because a lattice
    # of two residues half a millisecond apart is one grid, not two phases.
    g, ph = _halfms_lattice(us)
    if g:
        out.update(step=g, phase=ph,
                   share=_residue_mass_near(us, g * 1000, ph), phases=1)
        return out

    # For a system with no global step, report its mass on the 10 ms step the
    # paper reasons about. NOT the best over all candidates: modulo 2 ms any
    # system written at 1 ms puts half its offsets on one residue, which says
    # nothing. Against 10 ms, chance is 10%, and Olign's 40% is its frame.
    # A frame with a sub-frame offset, before falling back to "no lattice".
    g, k, _ = _phase_lattice(us)
    if g:
        out.update(step=g, share=_residue_mass(us, g * 1000)[0], phases=k)
        return out
    out["share"] = _residue_mass(us, 10000)[0]
    if _residue_mass(us, 1000)[0] >= ON_GRID:
        out["written_at"] = "1 ms"
    med, fs = _per_utt_frame(utts)
    if med is None or fs < 0.5:
        # Last reading: the smallest gap, for a lattice that rounding hid.
        g = _min_gap_frame(utts)
        if g is not None:
            out.update(frame=g, frame_share=1.0)
            return out
    out.update(frame=med, frame_share=fs)
    return out


def label(g: dict) -> str:
    if g["step"]:
        if g.get("phases", 1) > 1:
            return f"{g['step']} ms /{g['phases']}"
        ph = f" +{g['phase']:g}" if g["phase"] else ""
        return f"{g['step']} ms{ph}"
    if g["frame"] is not None and g["frame_share"] >= 0.5:
        return f"~{g['frame']:.1f} ms/utt"
    return g["written_at"]


def systems(cell: str, cap: int):
    rows = []
    for cfg in sorted(glob.glob(str(ROOT / "evals/*/*/config.yaml"))
                      + glob.glob(str(ROOT / "evals/*/*/exps/*/config.yaml"))):
        d = os.path.dirname(cfg)
        name = ""
        for ln in open(cfg):
            if ln.startswith("name:"):
                name = ln.split(":", 1)[1].strip()
                break
        name = name or os.path.basename(d)
        hyp = os.path.join(d, cell, "hyp.jsonl")
        if not os.path.isfile(hyp):
            continue
        g = grid_of(hyp, cap)
        if not g["n"]:
            continue
        kind = "aligner" if "/aligners/" in d else "ASR"
        rows.append((g, name, kind))
    # Coarsest global step first, then per-utterance frames, then the rest.
    return sorted(rows, key=lambda r: (-r[0]["step"], -(r[0]["frame"] or 0), r[1]))


def ceilings(tol_ms: float) -> dict[str, dict[int, float]]:
    """Share of REAL gold boundaries reachable on each grid, per split."""
    out = {}
    for lbl, pattern in SPLITS.items():
        ms = []
        for f in glob.glob(str(ROOT / "data/work/canonical" / pattern)):
            for line in open(f):
                try:
                    ms += boundaries_ms(json.loads(line).get("words"))
                except json.JSONDecodeError:
                    continue
        if not ms:
            continue
        per = {}
        for g in (10, 20, 40, 80):
            h = collections.Counter(v % g for v in ms)
            near = sum(c for r, c in h.items() if min(r, g - r) <= tol_ms)
            per[g] = near / len(ms)
        per[0] = len(ms)                      # carried along for the header
        out[lbl] = per
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cell", default="en/timit/core_test/origin",
                    help="which cell's hypotheses to read the grid from")
    ap.add_argument("--tol-ms", type=float, default=20.0,
                    help="the tolerance the ceiling is computed for")
    ap.add_argument("--cap", type=int, default=4000,
                    help="utterances to read per system")
    a = ap.parse_args(argv)

    rows = systems(a.cell, a.cap)
    if not rows:
        print(f"no hypotheses under {a.cell}", file=sys.stderr)
        return 1
    print(f"TIMESTAMP GRID, measured from {a.cell}")
    print(f"step: a global grid, when {100 * ON_GRID:.0f}% of offsets share one "
          f"residue modulo it (phase shown if not zero).")
    print("~X ms/utt: no global step, but within each utterance the gaps fit a "
          "lattice of about X ms,\n           a frame rescaled per file. "
          "'1 ms' / 'float': no step or frame found; this is how finely the "
          "numbers are written.\n")
    print(f"  {'grid':>14} {'share':>6} {'frame':>7} {'utts fit':>8}  {'kind':<8} {'system':<30} {'bnd':>6}")
    for g, name, kind in rows:
        fr = f"{g['frame']:.2f}" if g["frame"] is not None else "  -"
        print(f"  {label(g):>14} {100 * g['share']:5.1f}% {fr:>7} {100 * g['frame_share']:7.0f}%  "
              f"{kind:<8} {name:<30} {g['n']:>6}")

    print(f"\nCEILING AT {a.tol_ms:.0f} ms TOLERANCE, measured on the gold "
          f"boundaries of each split.")
    print("A system on this grid cannot place more than this share of its "
          "boundaries\nwithin the tolerance, however good its acoustic model "
          "is.\n")
    cs = ceilings(a.tol_ms)
    if not cs:
        print("  no gold manifests staged; skipped")
        return 0
    grids = (10, 20, 40, 80)
    print(f"  {'split':<18} " + "  ".join(f"{g:>3} ms" for g in grids)
          + "     theory 2t/g")
    for lbl, per in cs.items():
        cells = "  ".join(f"{100 * per[g]:5.1f}%" for g in grids)
        print(f"  {lbl:<18} {cells}")
    theory = "  ".join(f"{100 * min(1.0, 2 * a.tol_ms / g):5.1f}%" for g in grids)
    print(f"  {'(uniform)':<18} {theory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
