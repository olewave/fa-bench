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

"""Audio I/O shared by ingestion and mixing.

Reads WAV/FLAC via libsndfile and NIST-SPHERE (TIMIT) via a minimal PCM parser
with a ``sph2pipe`` fallback for shorten-compressed spheres. Everything is
returned as **mono float64 in [-1, 1]** so downstream SNR math is unit-consistent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


def to_mono(x: np.ndarray) -> np.ndarray:
    if x.ndim == 2:
        x = x.mean(axis=1)
    return x.astype(np.float64, copy=False)


def read_audio(path: str | Path) -> tuple[np.ndarray, int]:
    """Return (mono float64 samples, sample_rate). Handles WAV/FLAC and SPHERE."""
    path = Path(path)
    try:
        x, sr = sf.read(str(path), always_2d=False)
        return to_mono(np.asarray(x)), int(sr)
    except Exception:
        return _read_sphere(path)


def _read_sphere(path: Path) -> tuple[np.ndarray, int]:
    """Minimal NIST SPHERE reader (uncompressed PCM); falls back to sph2pipe."""
    with open(path, "rb") as f:
        magic = f.readline().strip()
        if magic not in (b"NIST_1A", b"NIST_1a"):
            raise ValueError(f"{path}: not a WAV/FLAC/SPHERE file (magic={magic!r})")
        hdr_size = int(f.readline().strip())
        header = f.read(hdr_size - len(magic) - len(str(hdr_size)) - 2)
        fields: dict[str, str] = {}
        for line in header.split(b"\n"):
            parts = line.split()
            if len(parts) >= 3 and parts[1].startswith(b"-"):
                fields[parts[0].decode()] = parts[2].decode()
        n = int(fields.get("sample_count", "0"))
        sr = int(fields.get("sample_rate", "16000"))
        nb = int(fields.get("sample_n_bytes", "2"))
        chans = int(fields.get("channel_count", "1"))
        coding = fields.get("sample_coding", "pcm")
        byte_fmt = fields.get("sample_byte_format", "01")  # 01=LE, 10=BE
        if "shorten" in coding or "wavpack" in coding:
            return _sph2pipe(path)
        raw = f.read(n * nb * chans) if n else f.read()
    dtype = "<i2" if byte_fmt == "01" else ">i2"
    if nb != 2:
        raise ValueError(f"{path}: unsupported sample_n_bytes={nb}")
    data = np.frombuffer(raw, dtype=dtype).astype(np.float64) / 32768.0
    if chans > 1:
        data = data.reshape(-1, chans).mean(axis=1)
    return data, sr


def _sph2pipe(path: Path) -> tuple[np.ndarray, int]:
    try:
        out = subprocess.run(
            ["sph2pipe", "-f", "wav", str(path)],
            capture_output=True, check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise RuntimeError(
            f"{path} is a compressed SPHERE (shorten). Install `sph2pipe` or "
            f"convert TIMIT to PCM WAV first. ({e})"
        ) from e
    import io

    x, sr = sf.read(io.BytesIO(out), always_2d=False)
    return to_mono(np.asarray(x)), int(sr)


def resample(x: np.ndarray, sr: int, target_sr: int) -> tuple[np.ndarray, int]:
    """Polyphase resample to target_sr (no-op if already there)."""
    if sr == target_sr:
        return x, sr
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr, target_sr)
    up, down = target_sr // g, sr // g
    return resample_poly(x, up, down).astype(np.float64), target_sr


def load_resample(path: str | Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    x, sr = read_audio(path)
    return resample(x, sr, target_sr)


def write_audio(path: str | Path, x: np.ndarray, sr: int, subtype: str = "PCM_16") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(x, -1.0, 1.0), sr, subtype=subtype)


def write_sphere_pcm(path: str | Path, x: np.ndarray, sr: int) -> None:
    """Write a minimal uncompressed NIST-SPHERE PCM file (used to make TIMIT-like
    test fixtures)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    body = pcm.tobytes()
    header_fields = (
        "NIST_1A\n"
        "   1024\n"
        f"sample_count -i {len(pcm)}\n"
        "sample_n_bytes -i 2\n"
        f"sample_rate -i {sr}\n"
        "channel_count -i 1\n"
        "sample_byte_format -s2 01\n"
        "sample_coding -s3 pcm\n"
        "end_head\n"
    )
    header = header_fields.encode()
    header = header + b"\x00" * (1024 - len(header))
    with open(path, "wb") as f:
        f.write(header)
        f.write(body)
