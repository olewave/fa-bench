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

"""SNR mixing (Plan S3), timing-preserving and reproducible.

SNR is defined as **active speech power** (ITU-T P.56) over **noise RMS power**.
Mixing is additive at a single sample rate, so it is sample-exact: the mixed
signal has identical length to the clean signal (the whole basis for zero-offset
gold transfer, Plan Section 0). This is asserted on every mix.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

EPS = 1e-12


# --------------------------------------------------------------------------
# ITU-T P.56 active speech level (method B)
# --------------------------------------------------------------------------
def asl_p56(x: np.ndarray, fs: int, nbits: int = 16) -> tuple[float, float]:
    """Return (active_mean_square, active_level_dBov).

    active_mean_square is the linear mean-square over active speech; the dBov
    value is 10*log10(active_mean_square) (0 dBov = full-scale square).
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return 0.0, -np.inf
    T, H, M = 0.03, 0.20, 15.9
    g = float(np.exp(-1.0 / (fs * T)))
    # two cascaded 1st-order low-passes on the rectified signal -> envelope q
    b, a = [1.0 - g], [1.0, -g]
    p = lfilter(b, a, np.abs(x))
    q = lfilter(b, a, p)

    sq = float(np.sum(x**2))
    if sq <= 0:
        return 0.0, -np.inf
    hang = int(np.ceil(fs * H))

    thresholds = 2.0 ** np.arange(-nbits, 0)  # amplitude thresholds, full-scale 1.0
    idx = np.arange(x.size)
    Lp, C = [], []
    for c in thresholds:
        active = q >= c
        if not active.any():
            continue
        # extend each active sample forward by `hang` samples (hangover)
        last = np.where(active, idx, -1)
        last = np.maximum.accumulate(last)
        activity = (idx - last) <= hang
        acount = int(activity.sum())
        if acount <= 0:
            continue
        Lp.append(10.0 * np.log10(sq / acount))       # active power level (dBov)
        C.append(20.0 * np.log10(c))                  # threshold level (dB)
    if not Lp:
        # fallback: whole-signal mean square
        ms = sq / x.size
        return ms, 10.0 * np.log10(ms + EPS)
    Lp = np.array(Lp)
    C = np.array(C)
    diff = Lp - C  # decreasing in threshold index; find where it crosses M
    # interpolate active level at diff == M
    order = np.argsort(diff)
    active_db = float(np.interp(M, diff[order], Lp[order]))
    active_ms = 10.0 ** (active_db / 10.0)
    return active_ms, active_db


def vad_rms_ms(x: np.ndarray, fs: int, frame_s: float = 0.02, thresh_db: float = -40.0) -> float:
    """Fallback active level: mean-square over frames above a relative threshold."""
    x = np.asarray(x, float)
    n = max(1, int(frame_s * fs))
    nf = len(x) // n
    if nf == 0:
        return float(np.mean(x**2) + EPS)
    frames = x[: nf * n].reshape(nf, n)
    ms = np.mean(frames**2, axis=1)
    peak = ms.max() + EPS
    keep = ms >= peak * (10 ** (thresh_db / 10))
    return float(ms[keep].mean()) if keep.any() else float(ms.mean())


def active_speech_ms(x: np.ndarray, fs: int, method: str = "p56") -> float:
    if method == "p56":
        ms, _ = asl_p56(x, fs)
        if ms > 0:
            return ms
    return vad_rms_ms(x, fs)


# --------------------------------------------------------------------------
# Mixing
# --------------------------------------------------------------------------
def mix_at_snr(
    speech: np.ndarray,
    noise: np.ndarray,
    snr_db: float,
    fs: int,
    *,
    method: str = "p56",
) -> tuple[np.ndarray, float, dict]:
    """Additively mix noise into speech at ``snr_db``.

    Returns (mixed, noise_scale, meta). ``noise`` must be at least as long as
    ``speech``; it is trimmed to speech length so mixing is sample-exact.
    """
    speech = np.asarray(speech, float)
    noise = np.asarray(noise, float)
    if len(noise) < len(speech):
        raise ValueError(
            f"noise ({len(noise)}) shorter than speech ({len(speech)}); "
            "pick a longer noise segment."
        )
    noise = noise[: len(speech)]

    s_ms = active_speech_ms(speech, fs, method=method)
    n_ms = float(np.mean(noise**2)) + EPS
    target_n_ms = s_ms / (10.0 ** (snr_db / 10.0))
    scale = float(np.sqrt(target_n_ms / n_ms))

    mixed = speech + scale * noise

    # Timing-preservation assertion (gate #1) — sample-exact.
    assert len(mixed) == len(speech), "mix changed length — timing broken"

    meta = {
        "speech_active_ms": s_ms,
        "noise_ms": n_ms,
        "target_noise_ms": target_n_ms,
    }
    return mixed, scale, meta


def measure_snr_db(
    speech: np.ndarray,
    scaled_noise: np.ndarray,
    fs: int,
    *,
    method: str = "p56",
) -> float:
    """Independently re-measure achieved SNR (Plan S3 gate #3)."""
    s_ms = active_speech_ms(speech, fs, method=method)
    n_ms = float(np.mean(np.asarray(scaled_noise, float) ** 2)) + EPS
    return 10.0 * np.log10(s_ms / n_ms)
