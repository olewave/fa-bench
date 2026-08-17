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

"""Automated gold-plausibility proxy (Plan S1 gate #2).

The plan asks the agent to open rendered TextGrids and confirm boundaries land on
acoustic events, not mid-vowel silence. We add a *quantitative* proxy so the gate
is reproducible: silence<->speech boundaries should coincide with large frame-
energy steps. We report the mean |dE| at true silence boundaries vs at random
interior points — the former should dominate for correctly placed gold.
"""

from __future__ import annotations

import numpy as np

from fabench.schema import Utterance

_SIL = "sil"


def frame_energy_db(x: np.ndarray, sr: int, hop_s: float = 0.005, win_s: float = 0.025):
    hop = max(1, round(hop_s * sr))
    win = max(hop, round(win_s * sr))
    n = 1 + max(0, (len(x) - win) // hop)
    e = np.empty(n)
    for i in range(n):
        seg = x[i * hop : i * hop + win]
        e[i] = 10 * np.log10(np.mean(seg**2) + 1e-10)
    return e, hop


def _energy_step_at(e: np.ndarray, hop: int, sr: int, t: float, pad_s: float = 0.02):
    """|mean energy after - mean energy before| across time t (dB)."""
    f = t * sr / hop
    k = max(1, round(pad_s * sr / hop))
    lo, hi = int(f) - k, int(f) + k
    if lo < 0 or hi >= len(e):
        return None
    before = e[lo : int(f)]
    after = e[int(f) : hi]
    if before.size == 0 or after.size == 0:
        return None
    return abs(after.mean() - before.mean())


def plausibility(
    utt: Utterance,
    x: np.ndarray,
    sr: int,
    canon,
) -> dict:
    """Return silence-boundary energy-step stats vs random interior points.

    ``canon`` maps a raw gold label to canonical (to detect silence phones).
    """
    e, hop = frame_energy_db(x, sr)
    sil_steps: list[float] = []
    for i, p in enumerate(utt.phones):
        left = canon(utt.phones[i - 1].label) if i > 0 else _SIL
        right = canon(p.label)
        # silence<->speech transition at this onset?
        is_sil_boundary = (left == _SIL) != (right == _SIL)
        if is_sil_boundary:
            s = _energy_step_at(e, hop, sr, p.start)
            if s is not None:
                sil_steps.append(s)
    # random interior baseline
    rng = np.random.default_rng(0)
    rand_steps = []
    if utt.duration_s > 0.1:
        for t in rng.uniform(0.05, utt.duration_s - 0.05, size=max(10, len(sil_steps))):
            s = _energy_step_at(e, hop, sr, float(t))
            if s is not None:
                rand_steps.append(s)
    mean_sil = float(np.mean(sil_steps)) if sil_steps else float("nan")
    mean_rand = float(np.mean(rand_steps)) if rand_steps else float("nan")
    return {
        "n_sil_boundaries": len(sil_steps),
        "mean_step_at_sil_db": mean_sil,
        "mean_step_random_db": mean_rand,
        # plausible if silence boundaries show clearly larger energy steps
        "plausible": bool(mean_sil > mean_rand + 3.0) if sil_steps and rand_steps else None,
    }
