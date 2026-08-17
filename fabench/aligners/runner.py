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

"""`fabench align` (Plan S4): run an aligner over the mix matrix -> hyp JSONL.

Records per-utterance wall-clock -> RTF (compute_time / audio_duration, Plan
5.8). Adapters that cannot serve a (mode, granularity) are skipped; per-item
failures are logged and the run continues.
"""

from __future__ import annotations

import sys
import time

import soundfile as sf

from fabench.aligners import get_adapter
from fabench.aligners.base import AlignerError, ModeUnsupported
from fabench.config import load_config
from fabench.schema import dump_jsonl, load_jsonl


def _audio_dur(path: str) -> float:
    try:
        info = sf.info(path)
        return info.frames / info.samplerate
    except Exception:
        return 0.0


def align_items(cfg, spec, gold_by_id, items, modes, limit=None):
    """Yield hyp records for (item x mode)."""
    adapter = get_adapter(spec)
    adapter.load()
    if getattr(adapter, "batch", False):
        yield from _align_batch(adapter, spec, gold_by_id, items, modes, limit)
        return
    done = 0
    for it in items:
        gold = gold_by_id.get(it["utt_id"] if isinstance(it, dict) else it.utt_id)
        if gold is None:
            continue
        item_id = it["item_id"] if isinstance(it, dict) else it.item_id
        utt_id = gold.utt_id
        condition = it["condition"] if isinstance(it, dict) else it.condition
        audio_path = it["mixed_audio_path"] if isinstance(it, dict) else it.mixed_audio_path
        transcript = " ".join(w.label for w in gold.words)
        phone_seq = [p.label for p in gold.phones]
        dur = _audio_dur(audio_path) or gold.duration_s

        for mode in modes:
            if not adapter.supports(mode, "phone") and not adapter.supports(mode, "word"):
                continue
            try:
                t0 = time.time()
                out = adapter.align(audio_path, transcript, phone_seq, mode)
                comp = time.time() - t0
            except ModeUnsupported:
                continue
            except AlignerError as e:
                print(f"  [fail] {item_id} mode={mode}: {e}", file=sys.stderr)
                continue
            except Exception as e:  # never let one item kill the whole run
                print(f"  [error] {item_id} mode={mode}: {e}", file=sys.stderr)
                continue
            yield {
                "item_id": item_id,
                "utt_id": utt_id,
                "condition": condition,
                "aligner": spec.name,
                "mode": mode,
                "source": adapter.source,  # normalization source for hyp phones
                "rtf": comp / dur if dur else None,
                "words": [w.to_dict() for w in out.words],
                "phones": [p.to_dict() for p in out.phones],
                **(getattr(out, "meta", None) or {}),
            }
        done += 1
        if limit and done >= limit:
            break


def _align_batch(adapter, spec, gold_by_id, items, modes, limit):
    """Batch aligners (MFA, MAPS, every SubprocessAligner): one call per MODE.

    It used to make one call total, for a single mode picked as
    `"A" if "A" in modes else modes[0]`, so a batch tool could only ever emit
    its Mode A tier. That was invisible while every SubprocessAligner was
    word-only. torchaudio_fa is the first with a phone tier, and moving it to a
    private venv silently dropped its Mode B row -- 5,348 phone boundaries.
    """
    for mode in (modes or ["A"]):
        yield from _align_batch_mode(adapter, spec, gold_by_id, items, mode, limit)


def _align_batch_mode(adapter, spec, gold_by_id, items, mode, limit):
    import sys
    import time

    from fabench.aligners.base import BatchItem

    batch, meta = [], {}
    for it in items:
        utt_id = it["utt_id"] if isinstance(it, dict) else it.utt_id
        gold = gold_by_id.get(utt_id)
        if gold is None:
            continue
        item_id = it["item_id"] if isinstance(it, dict) else it.item_id
        condition = it["condition"] if isinstance(it, dict) else it.condition
        audio = it["mixed_audio_path"] if isinstance(it, dict) else it.mixed_audio_path
        batch.append(
            BatchItem(
                item_id=item_id,
                audio_path=audio,
                transcript=" ".join(w.label for w in gold.words),
                speaker=gold.speaker_id,
                phone_seq=[p.label for p in gold.phones],
                mode=mode,
            )
        )
        meta[item_id] = (gold.utt_id, condition, _audio_dur(audio) or gold.duration_s)
        if limit and len(batch) >= limit:
            break
    if not batch:
        return
    print(f"  [batch] {spec.name}: aligning {len(batch)} items in one corpus call…",
          file=sys.stderr)
    t0 = time.time()
    try:
        outputs = adapter.align_corpus(batch)
    except Exception as e:  # batch failure -> log, skip whole aligner
        print(f"  [batch-error] {spec.name}: {e}", file=sys.stderr)
        return
    elapsed = time.time() - t0
    total_audio = sum(meta[b.item_id][2] for b in batch) or 1.0
    rtf = elapsed / total_audio  # amortized batch RTF
    for b in batch:
        out = outputs.get(b.item_id)
        if out is None:
            continue
        utt_id, condition, _ = meta[b.item_id]
        yield {
            "item_id": b.item_id,
            "utt_id": utt_id,
            "condition": condition,
            "aligner": spec.name,
            "mode": mode,
            "source": adapter.source,
            "rtf": rtf,
            "words": [w.to_dict() for w in out.words],
            "phones": [p.to_dict() for p in out.phones],
            # BATCH path. The per-item path above needed the same line; adding
            # it there only was the third two-write-sites miss in this module
            # (hyp_path condition=, and the score-side read before it). Every
            # batch tool -- which is every SubprocessAligner -- comes through
            # HERE, so a diagnostic added only above reaches nothing.
            **(getattr(out, "meta", None) or {}),
        }


def cmd_align(args) -> int:
    cfg = load_config(args.config)
    spec = cfg.aligner(args.aligner)
    modes = [args.mode] if getattr(args, "mode", None) else spec.modes
    from fabench.dataprep.datasets import ingest_corpus

    # Raw output lives with the tool that produced it -- fabench.paths is the
    # single definition shared with the scorer.
    from fabench.paths import hyp_path
    rc = 0
    for corpus, _ in cfg.enabled_gold():
        try:
            gold = {u.utt_id: u for u in ingest_corpus(corpus, cfg)}
        except (FileNotFoundError, ValueError) as e:
            print(f"  SKIP {corpus}: {e}", file=sys.stderr)
            rc |= 1
            continue
        from fabench.dataprep.datasets import manifest_path
        man = manifest_path(cfg, corpus)
        if not man.exists():
            print(f"  SKIP {corpus}: no manifest ({man}); run `fabench mix` first",
                  file=sys.stderr)
            rc |= 1
            continue
        items = list(load_jsonl(man))
        recs = list(align_items(cfg, spec, gold, items, modes, getattr(args, "limit", None)))
        out = hyp_path(cfg.repo_root(), spec.name, corpus, cfg.subset_of(corpus),
                       condition=cfg.condition_tag())
        out.parent.mkdir(parents=True, exist_ok=True)
        dump_jsonl(recs, out)
        print(f"[align] {spec.name} x {corpus}: {len(recs)} hyp records -> {out}")
    return rc
