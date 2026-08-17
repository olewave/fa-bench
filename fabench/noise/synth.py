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

"""Synthetic stationary noise (Plan 1.4): white + pink, generated on the fly.

Seeded and reproducible. Pink is 1/f amplitude spectrum via FFT shaping. Both
return unit-ish signals; the mixer rescales to the target SNR, so absolute level
here is irrelevant (we normalize to unit RMS for numeric stability).
"""

from __future__ import annotations

import numpy as np


def _unit_rms(x: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(x**2)) + 1e-12
    return x / rms


def white(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _unit_rms(rng.standard_normal(n))


def pink(n: int, seed: int) -> np.ndarray:
    """Pink (1/f) noise: shape white spectrum by 1/sqrt(f)."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    # rfft, scale by 1/sqrt(f), irfft
    spec = np.fft.rfft(w)
    freqs = np.arange(spec.size)
    scale = np.ones(spec.size)
    scale[1:] = 1.0 / np.sqrt(freqs[1:])
    x = np.fft.irfft(spec * scale, n=n)
    return _unit_rms(x)


def generate(noise_type: str, n: int, seed: int) -> np.ndarray:
    if noise_type == "white":
        return white(n, seed)
    if noise_type == "pink":
        return pink(n, seed)
    raise ValueError(f"synth.generate: unknown synthetic noise {noise_type!r}")
