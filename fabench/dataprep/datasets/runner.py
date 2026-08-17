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

"""`fabench ingest` (Plan S1): corpora -> canonical gold + sanity gates."""

from __future__ import annotations

import sys

from fabench.config import load_config
from fabench.dataprep.datasets import _gold_spec, _variant_tag, canonical_path, ingest_corpus
from fabench.normalize import make_canon
from fabench.schema import validate_utterance

_SOURCE = {"timit": "timit", "buckeye": "buckeye", "l2arctic": "l2arctic"}


def cmd_ingest(args) -> int:
    cfg = load_config(args.config)
    corpora = (
        [args.corpus]
        if getattr(args, "corpus", None)
        else [name for name, _ in cfg.enabled_gold()]
    )
    rc = 0
    for corpus in corpora:
        rc |= _ingest_one(cfg, corpus, getattr(args, "limit", None))
    return rc


def _ingest_one(cfg, corpus: str, limit) -> int:
    print(f"\n=== ingest {corpus} ===")
    try:
        utts = ingest_corpus(corpus, cfg, limit=limit, use_cache=False)
    except (FileNotFoundError, ValueError) as e:
        print(f"  SKIP/ABORT: {e}", file=sys.stderr)
        return 1
    if not utts:
        print("  no utterances found", file=sys.stderr)
        return 1

    canon = make_canon(_SOURCE.get(corpus, corpus))
    n_err = n_warn = 0
    total_phones = 0
    speakers = set()
    for u in utts:
        speakers.add(u.speaker_id)
        total_phones += len(u.phones)
        rep = validate_utterance(u, require_phone_no_gaps=(corpus == "timit"))
        n_err += len(rep.errors)
        n_warn += len(rep.warnings)
        if rep.errors:
            print(f"  [invalid] {u.utt_id}: {rep.errors[:3]}", file=sys.stderr)

    print(
        f"  utts={len(utts)} speakers={len(speakers)} phones={total_phones} "
        f"errors={n_err} warnings={n_warn}"
    )
    print(f"  canonical -> {canonical_path(cfg, corpus, _variant_tag(corpus, _gold_spec(cfg, corpus)))}")

    # plausibility: render 3 utts to TextGrid + automated energy-step check
    _plausibility(cfg, corpus, utts[:3], canon)
    return 1 if n_err else 0


def _plausibility(cfg, corpus, sample, canon) -> None:
    from fabench.audio import load_resample
    from fabench.dataprep.datasets.plausibility import plausibility
    from fabench.dataprep.datasets.textgrid import render_textgrid

    tg_dir = cfg.work_dir() / "textgrid" / corpus
    print(f"  plausibility (TextGrids -> {tg_dir}):")
    for u in sample:
        try:
            render_textgrid(u, tg_dir / f"{u.utt_id}.TextGrid")
        except Exception as e:
            print(f"    {u.utt_id}: textgrid render failed ({e})", file=sys.stderr)
        try:
            x, sr = load_resample(u.audio_path, 16000)
            pl = plausibility(u, x, sr, canon)
            print(
                f"    {u.utt_id}: sil-bnds={pl['n_sil_boundaries']} "
                f"step@sil={pl['mean_step_at_sil_db']:.1f}dB "
                f"step@rand={pl['mean_step_random_db']:.1f}dB "
                f"plausible={pl['plausible']}"
            )
        except Exception as e:
            print(f"    {u.utt_id}: audio plausibility skipped ({e})", file=sys.stderr)
