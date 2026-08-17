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

"""`fabench noise` and `fabench mix` (Plan S3)."""

from __future__ import annotations

import random
import sys
from pathlib import Path

from fabench.config import load_config
from fabench.noise.mixer import measure_snr_db
from fabench.schema import dump_jsonl


def cmd_noise(args) -> int:
    cfg = load_config(args.config)
    if args.noise_cmd == "fetch":
        from fabench.noise.musan import ensure_musan

        root = ensure_musan(cfg)
        print(f"[musan] ready at {root}")
        return 0
    if args.noise_cmd == "split":
        from fabench.noise.musan import ensure_musan, held_out_split, list_files

        root = ensure_musan(cfg)
        seed = int(cfg.seeds.get("noise_split", 0))
        for kind in ("noise", "speech"):
            files = list_files(root, kind)
            train, ev = held_out_split(files, seed)
            print(f"  {kind}: total={len(files)} train={len(train)} eval={len(ev)} (seed={seed})")
        return 0
    if args.noise_cmd == "info":
        print("noise config:", cfg.datasets.get("noise", {}))
        print("conditions:", [c.name for c in cfg.conditions()])
        return 0
    return 1


def cmd_mix(args) -> int:
    cfg = load_config(args.config)
    from fabench.dataprep.datasets import ingest_corpus
    from fabench.noise.manifest import build_manifest
    from fabench.noise.provider import NoiseProvider

    out_dir = cfg.work_dir() / "mix"
    provider = None
    rc = 0
    for corpus, _ in cfg.enabled_gold():
        try:
            utts = ingest_corpus(corpus, cfg, limit=getattr(args, "limit", None))
        except (FileNotFoundError, ValueError) as e:
            print(f"  SKIP {corpus}: {e}", file=sys.stderr)
            rc |= 1
            continue
        if provider is None:  # only fetch MUSAN once a corpus is confirmed staged
            provider = NoiseProvider.from_config(cfg)
        items = build_manifest(utts, cfg, provider, out_dir)
        from fabench.dataprep.datasets import manifest_path
        man_path = manifest_path(cfg, corpus)
        dump_jsonl(items, man_path)
        print(f"[mix] {corpus}: {len(items)} items -> {man_path}")
        _s3_gates(items, cfg)
    return rc


def _s3_gates(items, cfg) -> None:
    """Timing preservation, achieved-SNR ±0.5 dB on a random sample (gates 1,3)."""
    from fabench.audio import load_resample

    noisy = [it for it in items if it.noise_type is not None]
    if not noisy:
        return
    rng = random.Random(0)
    sample = rng.sample(noisy, min(20, len(noisy)))
    worst = 0.0
    for it in sample:
        clean, sr = load_resample(
            str(Path(it.mixed_audio_path).parent / "clean.wav"), 16000
        )
        mixed, _ = load_resample(it.mixed_audio_path, 16000)
        assert len(mixed) == len(clean), f"timing broken for {it.item_id}"
        # reconstruct scaled noise = mixed - clean
        scaled_noise = mixed[: len(clean)] - clean
        ach = measure_snr_db(clean, scaled_noise, sr)
        worst = max(worst, abs(ach - it.snr_db))
    print(f"    gate: timing OK; achieved-SNR max|err|={worst:.3f} dB (n={len(sample)})")
    assert worst < 0.5, f"achieved SNR off by {worst:.3f} dB (>0.5)"
