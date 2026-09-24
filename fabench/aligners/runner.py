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
from fabench.aligners.relabel import relabel_to_input
from fabench.config import load_config
from fabench.schema import dump_jsonl, load_jsonl


def _audio_dur(path: str) -> float:
    try:
        info = sf.info(path)
        return info.frames / info.samplerate
    except Exception:
        return 0.0


def _asr_transcripts(spec) -> dict[str, str]:
    """Words decoded by another tool, for the CASCADE case.

    An aligner normally receives the reference transcript. With

        params:
          transcript_hyp: evals/timestamp_asrs/qwen3_asr/en/timit/dev/origin/hyp.jsonl

    it instead receives the words that tool decoded for the SAME cell, which is
    what makes a two-step ASR-then-align pipeline measurable: the aligner must
    place words that may be wrong, exactly as it would in production.

    The path is explicit rather than inferred from the tool name and cell. A
    cascade is only meaningful if the upstream hypothesis came from the matching
    corpus, split AND condition, and naming the file makes a mismatch visible in
    the config instead of silently pairing clean text with noisy audio.

    Only the aligner's INPUT changes. Scoring still compares against the
    reference gold, so a misrecognised word costs the cascade what it costs a
    timestamped ASR, and the two are directly comparable.

    Returns {} when unset, leaving the ordinary path untouched.
    """
    params = getattr(spec, "params", None) or {}
    rel = params.get("transcript_hyp")
    if not rel:
        if params.get("requires_transcript_hyp"):
            # A cascade recipe carries this so it can never quietly degrade into
            # a gold run. The recipe exists to make the tool discoverable to the
            # cross-tool rescore; it has no per-cell hypothesis of its own, and
            # falling back to the reference words here would publish a
            # gold-transcript score under a track-2 name -- the one error this
            # benchmark's two-track split exists to prevent.
            raise AlignerError(
                "this is a cascade recipe: it needs params.transcript_hyp for the "
                "cell being aligned. Generate per-cell configs with "
                "evals/gen_cascade_configs.py rather than running the recipe directly.")
        return {}
    import json
    import pathlib
    hyp = pathlib.Path(rel)
    if not hyp.is_absolute():
        hyp = pathlib.Path(__file__).resolve().parents[2] / hyp
    if not hyp.is_file():
        raise AlignerError(
            f"transcript_hyp: no hypothesis at {hyp}. Run the upstream ASR on "
            "this cell first -- a cascade cannot invent its own upstream.")
    out: dict[str, str] = {}
    for line in hyp.open():
        r = json.loads(line)
        words = [w["label"] if isinstance(w, dict) else w[0]
                 for w in (r.get("words") or [])]
        if words:
            out[r["utt_id"]] = " ".join(words)
    if not out:
        raise AlignerError(f"transcript_hyp: {hyp} produced no usable words")
    return out


def align_items(cfg, spec, gold_by_id, items, modes, limit=None):
    """Yield hyp records for (item x mode)."""
    _ASR_TXT = _asr_transcripts(spec)   # {} unless this is a cascade
    # A noisy run reads a SHADOW ROOT: the gold manifest is symlinked through
    # unchanged and only the audio is swapped, so every item still says
    # condition="clean". The run config's condition_tag is the only thing that
    # knows better, and without it the `condition` column of every noisy
    # leaderboard reads "clean" -- the metrics are right, the label is not.
    _COND = cfg.condition_tag()
    adapter = get_adapter(spec)
    adapter.load()
    if getattr(adapter, "batch", False):
        yield from _align_batch(adapter, spec, gold_by_id, items, modes, limit,
                                cond_tag=_COND)
        return
    done = 0
    for it in items:
        gold = gold_by_id.get(it["utt_id"] if isinstance(it, dict) else it.utt_id)
        if gold is None:
            continue
        item_id = it["item_id"] if isinstance(it, dict) else it.item_id
        utt_id = gold.utt_id
        condition = _COND or (it["condition"] if isinstance(it, dict) else it.condition)
        audio_path = it["mixed_audio_path"] if isinstance(it, dict) else it.mixed_audio_path
        # Keep the TOKENS, not only the joined string. The aligner is given the
        # string but owes us timings for THESE tokens; most return their own
        # lexicon's normalisation instead (MFA splits tom-boy and drops the
        # apostrophe from kids', BFA has no apostrophe at all), so the output is
        # mapped back onto this list before it is written. See
        # fabench.aligners.relabel for why that belongs here and not in scoring.
        in_tokens = (_ASR_TXT.get(utt_id, "").split() if _ASR_TXT
                     else [w.label for w in gold.words])
        transcript = (_ASR_TXT.get(utt_id, "") if _ASR_TXT
                      else " ".join(w.label for w in gold.words))
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
                "words": [w.to_dict()
                          for w in relabel_to_input(in_tokens, out.words)],
                "phones": [p.to_dict() for p in out.phones],
                **(getattr(out, "meta", None) or {}),
            }
        done += 1
        if limit and done >= limit:
            break


def _align_batch(adapter, spec, gold_by_id, items, modes, limit, cond_tag=""):
    """Batch aligners (MFA, MAPS, every SubprocessAligner): one call per MODE.

    It used to make one call total, for a single mode picked as
    `"A" if "A" in modes else modes[0]`, so a batch tool could only ever emit
    its Mode A tier. That was invisible while every SubprocessAligner was
    word-only. torchaudio_fa is the first with a phone tier, and moving it to a
    private venv silently dropped its Mode B row -- 5,348 phone boundaries.
    """
    for mode in (modes or ["A"]):
        yield from _align_batch_mode(adapter, spec, gold_by_id, items, mode, limit,
                                     cond_tag=cond_tag)


def _align_batch_mode(adapter, spec, gold_by_id, items, mode, limit, cond_tag=""):
    _ASR_TXT = _asr_transcripts(spec)   # {} unless this is a cascade
    import sys
    import time

    from fabench.aligners.base import BatchItem

    batch, meta, empties = [], {}, []
    for it in items:
        utt_id = it["utt_id"] if isinstance(it, dict) else it.utt_id
        gold = gold_by_id.get(utt_id)
        if gold is None:
            continue
        item_id = it["item_id"] if isinstance(it, dict) else it.item_id
        condition = cond_tag or (it["condition"] if isinstance(it, dict) else it.condition)
        audio = it["mixed_audio_path"] if isinstance(it, dict) else it.mixed_audio_path
        in_tokens = (_ASR_TXT.get(utt_id, "").split() if _ASR_TXT
                     else [w.label for w in gold.words])
        # CASCADE, upstream recognised nothing. Do not hand the aligner an empty
        # transcript: it fails the item, and a failed item is dropped below, so
        # the utterance would leave the evaluation entirely and the cascade would
        # be scored only where its recogniser produced words -- precisely the
        # easier-subset bias the two-track split exists to expose. Emit a record
        # with no words instead, so every gold word in it counts as a deletion.
        # Parakeet-TDT returns nothing for 207 of 4456 utterances on babble-noised
        # Buckeye dev, where Qwen3 returns none: a real 4.6% of one cell.
        if _ASR_TXT and not in_tokens:
            empties.append((item_id, gold.utt_id, condition))
            continue
        batch.append(
            BatchItem(
                item_id=item_id,
                audio_path=audio,
                transcript=(_ASR_TXT.get(gold.utt_id, "") if _ASR_TXT
                            else " ".join(w.label for w in gold.words)),
                speaker=gold.speaker_id,
                phone_seq=[p.label for p in gold.phones],
                mode=mode,
            )
        )
        meta[item_id] = (gold.utt_id, condition, _audio_dur(audio) or gold.duration_s,
                         in_tokens)
        if limit and len(batch) >= limit:
            break
    def _empty_records():
        for item_id, utt_id, condition in empties:
            yield {
                "item_id": item_id, "utt_id": utt_id, "condition": condition,
                "aligner": spec.name, "mode": mode, "source": adapter.source,
                "rtf": 0.0, "words": [], "phones": [],
                "empty_transcript_hyp": True,
            }

    if not batch:
        yield from _empty_records()
        return
    if empties:
        print(f"  [batch] {spec.name}: {len(empties)} items have an empty upstream "
              f"transcript -- recorded with no words, not skipped", file=sys.stderr)
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
            # CASCADE: the aligner failed this item. Same accounting as an empty
            # upstream transcript -- dropping it would shrink the denominator and
            # score the pipeline only where it happened to succeed. Track 1 keeps
            # the old skip, since those numbers are already published.
            if _ASR_TXT:
                utt_id, condition, _, _ = meta[b.item_id]
                empties.append((b.item_id, utt_id, condition))
            continue
        utt_id, condition, _, _in_tok = meta[b.item_id]
        yield {
            "item_id": b.item_id,
            "utt_id": utt_id,
            "condition": condition,
            "aligner": spec.name,
            "mode": mode,
            "source": adapter.source,
            "rtf": rtf,
            "words": [w.to_dict()
                      for w in relabel_to_input(_in_tok, out.words)],
            "phones": [p.to_dict() for p in out.phones],
            # BATCH path. The per-item path above needed the same line; adding
            # it there only was the third two-write-sites miss in this module
            # (hyp_path condition=, and the score-side read before it). Every
            # batch tool -- which is every SubprocessAligner -- comes through
            # HERE, so a diagnostic added only above reaches nothing.
            **(getattr(out, "meta", None) or {}),
        }
    yield from _empty_records()


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
