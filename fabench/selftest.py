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

"""Synthetic oracle-corpus end-to-end self-test (Plan S6, no restricted data).

This is the honest integration proof for the mix -> score -> report chain when no
licensed gold is staged. It builds a synthetic corpus with *known* boundaries and
three oracle "aligners" whose errors are prescribed, so every headline metric has
a predicted value:

* ``oracle_const10`` — every boundary off by exactly +10 ms => MAE == 10.0 ms,
  TA20 == 100 %, ARR == 1.0 (metric wiring anchor).
* ``oracle_degrade`` — boundary error grows as SNR drops (2/8/15/25 ms) =>
  monotone degradation curve (gate #8), TA20 collapses at 10 dB, real Spearman.
* ``oracle_lazy`` — drops every 4th phone => ARR < 1, exercises the cross-system
  common-matched (survivor-bias) set.

It also runs the real S3 mixer on the synthetic audio (timing + achieved-SNR
gates) so mixing is part of the E2E, and checks determinism (two runs identical).
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np

from fabench.audio import write_audio
from fabench.normalize import manner_of
from fabench.schema import Interval, Utterance
from fabench.score.aggregate import aggregate
from fabench.score.core import score_pair

SR = 16000
# canonical-39 phones with a spread of manners; sil separates "words"
_PATTERN = ["sil", "s", "iy", "sil", "hh", "ae", "d", "sil", "y", "er", "sil"]
_WORDS = [("she", 1, 2), ("had", 4, 6), ("your", 8, 9)]  # (label, first_phone, last_phone)


def _det_freq(label: str) -> float:
    """Deterministic label -> tone frequency (avoids per-process hash randomization)."""
    return 150 + 80 * (sum(ord(c) for c in label) % 7)

# per-condition base boundary error (seconds) for oracle_degrade
_DEGRADE = {"clean": 0.002, "white_snr20": 0.008, "white_snr15": 0.015, "white_snr10": 0.025}
_CONDITIONS = list(_DEGRADE.keys())


def make_corpus(n_utts: int, out_audio: Path, seed: int) -> list[Utterance]:
    np.random.default_rng(seed)
    utts = []
    for u in range(n_utts):
        phones, t = [], 0.0
        for i, lab in enumerate(_PATTERN):
            dur = 0.06 + 0.10 * ((i + u) % 3) / 2  # 0.06..0.16 s, deterministic
            phones.append(Interval(lab, t, t + dur))
            t += dur
        total = t
        words = [
            Interval(w, phones[a].start, phones[b].end) for (w, a, b) in _WORDS
        ]
        # audio: silence phones -> zeros; else colored tone, so the mixer/plausibility
        # operate on a real waveform
        x = np.zeros(round(total * SR))
        for p in phones:
            a, b = int(p.start * SR), int(p.end * SR)
            if p.label != "sil":
                f = _det_freq(p.label)
                x[a:b] = 0.3 * np.sin(2 * np.pi * f * np.arange(b - a) / SR)
        path = out_audio / f"synth_{u:03d}.wav"
        write_audio(path, x, SR)
        utts.append(
            Utterance(f"synth_{u:03d}", "synthetic", "read", f"spk{u%3}",
                      str(path), SR, total, words=words, phones=phones)
        )
    return utts


def _shift(iv: Interval, off: float, conf=None) -> Interval:
    return Interval(iv.label, iv.start + off, iv.end + off, conf)


def oracle_hyp(gold: Utterance, condition: str, kind: str) -> Utterance:
    """Produce a hypothesis alignment with prescribed error."""
    phones, words = [], []
    for i, p in enumerate(gold.phones):
        if kind == "const10":
            off, conf = 0.010, 0.9
        elif kind == "degrade":
            base = _DEGRADE[condition]
            off = base + 0.002 * (i % 4)          # within-utt variation for calibration
            conf = 1.0 - (i % 4) / 5.0            # higher conf <-> smaller error
        elif kind == "lazy":
            if i % 4 == 3:                         # drop every 4th phone
                continue
            off, conf = 0.006, 0.8
        else:
            off, conf = 0.0, None
        phones.append(_shift(p, off, conf))
    for w in gold.words:
        off = 0.010 if kind == "const10" else _DEGRADE.get(condition, 0.005)
        words.append(_shift(w, off, None))
    return Utterance(gold.utt_id, "hyp", "", "", "", SR, gold.duration_s,
                     words=words, phones=phones)


def run_selftest(out_dir: Path, seed: int = 20240607, n_utts: int = 12):
    out_dir = Path(out_dir)
    audio_dir = out_dir / "audio"
    gold = make_corpus(n_utts, audio_dir, seed)

    # --- S3 mix on the synthetic audio (timing + achieved-SNR gates) ---
    mix_report = _exercise_mixer(gold, out_dir)

    # --- oracle align + score across conditions/aligners ---
    uttscores = []
    for kind, name in [("const10", "oracle_const10"),
                       ("degrade", "oracle_degrade"),
                       ("lazy", "oracle_lazy")]:
        for cond in _CONDITIONS:
            for g in gold:
                hyp = oracle_hyp(g, cond, kind)
                uttscores.append(
                    score_pair(g, hyp, condition=cond, aligner=name, mode="B",
                               manner_of_canonical=manner_of, rtf=0.1)
                )
    leaderboard, per_type = aggregate(
        uttscores, bootstrap_iters=200, min_matched_per_cell=30, seed=seed
    )

    # --- report ---
    from fabench.report.runner import build_report

    class _Cfg:  # minimal shim for build_report
        pass

    md = build_report(leaderboard, per_type, _Cfg())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(md)
    import pandas as pd

    pd.DataFrame(leaderboard).to_parquet(out_dir / "leaderboard.parquet")
    pd.DataFrame(per_type).to_parquet(out_dir / "per_type.parquet")

    return leaderboard, per_type, mix_report


def _exercise_mixer(gold, out_dir):
    from fabench.audio import load_resample
    from fabench.config import Config
    from fabench.noise.manifest import build_manifest
    from fabench.noise.mixer import measure_snr_db
    from fabench.noise.provider import NoiseProvider

    cfg = Config(
        raw={
            "seeds": {"mix": 7},
            "conditions": {"noise_types": ["white"], "snr_db": [20, 15, 10],
                           "include_clean": True},
            "paths": {"work_dir": str(out_dir / "work")},
        },
        path=Path("cfg.yaml"),
    )
    items = build_manifest(gold, cfg, NoiseProvider(), out_dir / "mix")
    worst = 0.0
    for it in items:
        clean, sr = load_resample(str(Path(it.mixed_audio_path).parent / "clean.wav"), SR)
        mixed, _ = load_resample(it.mixed_audio_path, SR)
        assert len(mixed) == len(clean)
        if it.snr_db is not None:
            ach = measure_snr_db(clean, mixed[: len(clean)] - clean, sr)
            worst = max(worst, abs(ach - it.snr_db))
    return {"n_items": len(items), "worst_snr_err_db": worst}


def check(leaderboard, per_type, mix_report) -> list[tuple[str, bool, str]]:
    """Return list of (check_name, passed, detail)."""
    checks = []
    by = {(r["aligner"], r["condition"]): r for r in leaderboard}

    # anchor: const10 -> MAE 10ms, TA20 100%, ARR 1.0
    c = by[("oracle_const10", "clean")]
    checks.append(("const10 MAE==10ms", abs(c["mae_ms"] - 10.0) < 0.05, f"{c['mae_ms']:.3f}"))
    checks.append(("const10 TA20==100%", abs(c["ta_20ms"] - 1.0) < 1e-9, f"{c['ta_20ms']:.3f}"))
    checks.append(("const10 ARR==1.0", abs(c["arr"] - 1.0) < 1e-9, f"{c['arr']:.3f}"))

    # monotone degradation for oracle_degrade
    maes = [by[("oracle_degrade", cond)]["mae_ms"] for cond in _CONDITIONS]
    mono = all(a <= b + 1e-6 for a, b in itertools.pairwise(maes))
    checks.append(("degrade MAE monotone↑", mono, "->".join(f"{m:.1f}" for m in maes)))
    ta20 = by[("oracle_degrade", "white_snr10")]["ta_20ms"]
    checks.append(("degrade TA20 collapses@10dB", ta20 < 0.01, f"{ta20:.3f}"))
    sp = by[("oracle_degrade", "white_snr10")]["cal_spearman"]
    checks.append(("degrade calibration Spearman>0", sp > 0.3, f"{sp:.3f}"))

    # lazy: ARR < 1, common-matched present
    lz = by[("oracle_lazy", "clean")]
    checks.append(("lazy ARR<1 (dropped phones)", lz["arr"] < 1.0, f"{lz['arr']:.3f}"))
    checks.append(("common-matched computed",
                   not np.isnan(lz.get("mae_common_ms", float("nan"))),
                   f"{lz.get('mae_common_ms'):.3f}"))

    # mixer gates
    checks.append(("mix timing+SNR (±0.5dB)", mix_report["worst_snr_err_db"] < 0.5,
                   f"{mix_report['worst_snr_err_db']:.3f} dB"))
    return checks


def cmd_selftest(args) -> int:
    out = Path(args.out)
    seed = getattr(args, "seed", 20240607)
    lb1, pt1, mr1 = run_selftest(out, seed=seed)
    # determinism: a second run must reproduce every metric value (gate #6)
    lb2, _, _ = run_selftest(out.parent / (out.name + "_rerun"), seed=seed)
    det = _identical_metrics(lb1, lb2)

    checks = check(lb1, pt1, mr1)
    checks.append(("determinism (two runs identical)", det, ""))

    print(f"\n=== fabench selftest (synthetic oracle E2E) -> {out} ===")
    allok = True
    for name, ok, detail in checks:
        allok &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:38s} {detail}")
    print(f"  report -> {out / 'report.md'}   leaderboard -> {out / 'leaderboard.parquet'}")
    print(f"  {'ALL PASS' if allok else 'FAILURES PRESENT'}")
    return 0 if allok else 1


def _identical_metrics(lb1, lb2) -> bool:
    if len(lb1) != len(lb2):
        return False
    key = lambda r: (r["aligner"], r["mode"], r["condition"], r["corpus"])
    d1 = {key(r): r for r in lb1}
    d2 = {key(r): r for r in lb2}
    if set(d1) != set(d2):
        return False
    for k, v1 in d1.items():
        for col in ("mae_ms", "ta_20ms", "arr", "mae_ci_lo_ms", "mae_common_ms"):
            a, b = v1.get(col), d2[k].get(col)
            if a is None and b is None:
                continue
            if isinstance(a, float) and np.isnan(a) and np.isnan(b):
                continue
            if a != b:
                return False
    return True
