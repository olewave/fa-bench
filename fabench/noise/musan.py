# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""MUSAN noise pool (Plan 1.4): fetch, held-out split, babble construction.

MUSAN (OpenSLR SLR17) is open — fetched once and cached. We reserve a **disjoint
held-out split** (seeded) for the eval mix so a system trained on MUSAN is
detectable. Babble is built by summing >=6 random ``speech/`` clips.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import numpy as np

from fabench.audio import load_resample


def ensure_musan(cfg) -> Path:
    """Return a MUSAN root dir (with noise/ speech/), fetching+caching if needed."""
    spec = cfg.datasets.get("noise", {}).get("musan", {})
    root = spec.get("root")
    if root and Path(root).exists():
        return _musan_root(Path(root))
    cache = Path(spec.get("cache_dir", "data/musan"))
    extracted = cache / "musan"
    if extracted.exists():
        return _musan_root(extracted)
    url = spec.get("url", "https://www.openslr.org/resources/17/musan.tar.gz")
    _download_and_extract(url, cache)
    return _musan_root(extracted)


def _musan_root(p: Path) -> Path:
    if (p / "noise").exists() or (p / "speech").exists():
        return p
    for cand in p.glob("**/musan"):
        if (cand / "noise").exists():
            return cand
    return p


def _download_and_extract(url: str, cache: Path) -> None:
    """Fetch the MUSAN tarball once into ``cache``, then unpack it there."""
    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / "musan.tar.gz"
    if not tarball.exists():
        _fetch(url, tarball)
    _extract(tarball, cache)


def _fetch(url: str, dest: Path) -> None:
    """Stream ``url`` to ``dest``, which only appears once the body is whole.

    The bytes go to a sibling name and are renamed at the end, after the size
    matches the server's Content-Length. A dropped connection on an 11 GB file
    then leaves nothing at ``dest``, so the next call downloads again instead of
    unpacking a short archive.
    """
    import requests

    part = dest.with_name(dest.name + ".download")
    print(f"[musan] fetching {url} into {dest} (about 11 GB, once)")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        want = int(resp.headers.get("Content-Length") or 0)
        with part.open("wb") as out:
            for block in resp.iter_content(chunk_size=8 << 20):
                out.write(block)
    have = part.stat().st_size
    if want and have != want:
        part.unlink()
        raise RuntimeError(f"[musan] short download, {have} of {want} bytes. Run again to retry.")
    part.replace(dest)


def _extract(tarball: Path, cache: Path) -> None:
    """Unpack into a private staging dir and move ``musan/`` into place last.

    ``ensure_musan`` reads an existing ``cache/musan`` as a finished fetch, so
    that directory must never exist half filled. A partial pool would reseed
    the held-out split and change every mix built from it.
    """
    import shutil
    import tempfile

    stage = Path(tempfile.mkdtemp(prefix="musan.unpack.", dir=cache))
    try:
        print(f"[musan] unpacking {tarball}")
        with tarfile.open(tarball) as tf:
            if hasattr(tarfile, "data_filter"):
                tf.extractall(stage, filter="data")
            else:  # Python builds older than the tarfile filter backport
                tf.extractall(stage)
        tree = stage / "musan"
        absent = [k for k in ("noise", "speech", "music") if not (tree / k).is_dir()]
        if absent:
            raise RuntimeError(f"[musan] archive incomplete, it has no {', '.join(absent)}. "
                               f"Delete {tarball} and run again.")
        tree.rename(cache / "musan")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def list_files(musan_root: Path, kind: str) -> list[Path]:
    """kind in {'noise','speech','music'}. 'noise' = free-field ambient."""
    d = Path(musan_root) / kind
    return sorted(d.rglob("*.wav"))


def _stable_seed(*parts) -> int:
    h = hashlib.sha256("::".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big")


def held_out_split(files: list[Path], seed: int, eval_frac: float = 0.5):
    """Deterministic disjoint split -> (train_pool, eval_pool). Only eval_pool is
    used for mixing (Plan 1.4)."""
    idx = np.arange(len(files))
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    cut = int(len(files) * (1 - eval_frac))
    train = [files[i] for i in idx[:cut]]
    eval_ = [files[i] for i in idx[cut:]]
    return train, eval_


def _random_segment(path: Path, length: int, rng: np.random.Generator, sr: int = 16000):
    x, _ = load_resample(path, sr)
    if len(x) < length:
        reps = int(np.ceil(length / max(1, len(x))))
        x = np.tile(x, reps)
    off = int(rng.integers(0, len(x) - length + 1)) if len(x) > length else 0
    return x[off : off + length], off / sr


def get_ambient(eval_pool: list[Path], length: int, seed: int, sr: int = 16000):
    """Pick one ambient noise segment. Returns (segment, source_file, offset_s)."""
    rng = np.random.default_rng(seed)
    path = eval_pool[int(rng.integers(0, len(eval_pool)))]
    seg, off = _random_segment(path, length, rng, sr)
    return seg, str(path), off


def build_babble(
    speech_eval_pool: list[Path],
    length: int,
    seed: int,
    n_sources: int = 6,
    sr: int = 16000,
):
    """Sum >=n_sources random speech clips -> babble. Returns (segment, provenance)."""
    rng = np.random.default_rng(seed)
    k = max(6, n_sources)
    picks = rng.choice(len(speech_eval_pool), size=min(k, len(speech_eval_pool)), replace=False)
    acc = np.zeros(length)
    srcs = []
    for i in picks:
        seg, off = _random_segment(speech_eval_pool[int(i)], length, rng, sr)
        acc += seg
        srcs.append(f"{speech_eval_pool[int(i)].name}@{off:.2f}")
    return acc, "musan_babble[" + "+".join(srcs) + "]", 0.0
