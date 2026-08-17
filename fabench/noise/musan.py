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
    import requests

    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / "musan.tar.gz"
    if not tarball.exists():
        # Download to a .part name and rename only on a verified, complete
        # body. An 11 GB stream WILL sometimes be cut, and a truncated file
        # under the final name is worse than no file: the next run would skip
        # the download and fail (or worse, half-succeed) at extraction.
        part = cache / "musan.tar.gz.part"
        print(f"[musan] downloading {url} -> {tarball} (~11 GB, once)")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            expected = int(r.headers.get("Content-Length", 0))
            with open(part, "wb") as f:
                f.writelines(r.iter_content(chunk_size=1 << 20))
        got = part.stat().st_size
        if expected and got != expected:
            part.unlink()
            raise RuntimeError(
                f"musan download truncated: got {got} of {expected} bytes; re-run to retry"
            )
        part.rename(tarball)
    _extract(tarball, cache)


def _extract(tarball: Path, cache: Path) -> None:
    """Extract so the final ``musan/`` dir only ever appears complete.

    Extraction goes to a scratch dir that is renamed into place at the end,
    with the three corpus kinds verified first — ``ensure_musan`` treats the
    presence of ``cache/musan`` as "already fetched", so an interrupted
    extraction must never leave a partial tree under that name (a 9%-extracted
    pool would silently reseed the held-out split and change every mix).
    """
    import shutil

    scratch = cache / "musan.extracting"
    if scratch.exists():
        shutil.rmtree(scratch)
    print(f"[musan] extracting {tarball}")
    with tarfile.open(tarball) as tf:
        tf.extractall(scratch)
    tree = scratch / "musan"
    missing = [k for k in ("noise", "speech", "music") if not (tree / k).is_dir()]
    if missing:
        shutil.rmtree(scratch)
        raise RuntimeError(
            f"musan archive incomplete after extraction (missing {'/'.join(missing)}); "
            f"delete {tarball} and re-run to re-download"
        )
    tree.rename(cache / "musan")
    shutil.rmtree(scratch)


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
