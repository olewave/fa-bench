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

"""Gold ingestion orchestrator (Plan S1).

Turns user-staged corpora into canonical :class:`Utterance` JSONL, caching under
``work_dir/canonical/<corpus>.jsonl``. Restricted corpora are never downloaded:
if a root is missing we fail loudly with acquisition instructions (Plan 1.1).
"""

from __future__ import annotations

from pathlib import Path

from fabench.config import Config, is_excluded_gold
from fabench.schema import Utterance, dump_jsonl, load_jsonl

# Human-facing acquisition instructions per restricted corpus (Plan 1.1 / 9).
ACQUISITION = {
    "timit": (
        "TIMIT is restricted (LDC93S1 / LDC Catalog LDC93S1). Obtain via LDC "
        "license, then set datasets.gold.timit.root to the dir containing "
        "TRAIN/ and TEST/ (NIST layout: TEST/DR1/<SPKR>/<sent>.PHN)."
    ),
    "buckeye": (
        "The Buckeye Corpus is registration-gated (buckeyecorpus.osu.edu). "
        "Register, download, then set datasets.gold.buckeye.root to the dir of "
        "sNN/ speaker folders (each with .phones/.words/.wav)."
    ),
    "l2arctic": (
        "L2-ARCTIC is open under a research license (psi.engr.tamu.edu/l2-arctic). "
        "Download, then set datasets.gold.l2arctic.root to the corpus root "
        "(<speaker>/annotation/*.TextGrid holds the manual gold)."
    ),
}


def _root_tag(spec: dict) -> str:
    """Short digest of the audio root.

    REQUIRED FOR CORRECTNESS, not tidiness. The tag used to be subset-only, so
    a config pointing at a noise-augmented shadow root wrote its ingest to the
    SAME cache file as the clean config (`timit__core_test.jsonl`). The clean
    run then silently read noisy audio and would have reported it as clean --
    no error, just wrong numbers. Anything that changes the ingest output must
    be in the key, and the root does.
    """
    import hashlib
    root = str(spec.get("root", ""))
    if not root:
        return ""
    return "__r" + hashlib.sha1(root.encode()).hexdigest()[:8]


def _variant_tag(corpus: str, spec: dict) -> str:
    """Ingest-variant discriminator for the cache filename. Distinct variants of
    the same corpus (TIMIT core_test vs all; Buckeye fabench vs paper; clean vs
    a noisy shadow root) must not share a cache entry."""
    if corpus == "timit":
        tag = str(spec.get("subset", "core_test"))
        if spec.get("merge_closures"):
            tag += "__mergeclosures"  # Buckeye-style gold is a distinct cache variant
        return tag + _root_tag(spec)
    if corpus == "buckeye":
        proto = str(spec.get("protocol", "fabench"))
        sub = spec.get("subset")
        return (f"{proto}__{sub}" if sub else proto) + _root_tag(spec)
    if corpus == "l2arctic":
        return str(spec.get("subset", "manual"))
    return ""


def canonical_path(cfg: Config, corpus: str, variant: str = "") -> Path:
    name = f"{corpus}__{variant}.jsonl" if variant else f"{corpus}.jsonl"
    return cfg.work_dir() / "canonical" / name


def manifest_path(cfg: Config, corpus: str) -> Path:
    """Mix-manifest path, keyed the SAME way as the canonical cache.

    The manifest was `manifests/<corpus>.jsonl` -- corpus name only. Every
    condition of a corpus therefore wrote and read ONE file, so two runs over
    the same corpus at once (reverb and noise, say, pointing at different
    shadow roots) raced: the last writer won and both aligners then read that
    single root's audio. The alignments came out identical, both differed from
    clean, every check passed, and the published noise table carried one
    condition's numbers under two headings.

    This is the exact failure `_root_tag` was written to fix for the canonical
    cache -- see its docstring. Only the manifest was left behind, because it
    is written by the mix stage rather than by ingest. Same key, same reason.
    """
    variant = _variant_tag(corpus, _gold_spec(cfg, corpus))
    name = f"{corpus}__{variant}.jsonl" if variant else f"{corpus}.jsonl"
    return cfg.work_dir() / "manifests" / name


def _gold_spec(cfg: Config, corpus: str) -> dict:
    spec = cfg.datasets.get("gold", {}).get(corpus)
    if not isinstance(spec, dict):
        raise KeyError(f"no gold corpus {corpus!r} in config")
    return spec


def ingest_corpus(
    corpus: str,
    cfg: Config,
    *,
    limit: int | None = None,
    use_cache: bool = True,
) -> list[Utterance]:
    """Ingest one gold corpus into canonical Utterances (cached)."""
    spec = _gold_spec(cfg, corpus)
    cache = canonical_path(cfg, corpus, _variant_tag(corpus, spec))
    # The cache represents the FULL corpus; only read/write it on full runs.
    if use_cache and limit is None and cache.exists():
        return [Utterance.from_dict(d) for d in load_jsonl(cache)]

    root = spec.get("root")
    if not root:
        raise FileNotFoundError(
            f"gold corpus {corpus!r} is not staged (datasets.gold.{corpus}.root "
            f"is null).\n  {ACQUISITION.get(corpus, 'Stage the corpus and set its root.')}"
        )
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(
            f"gold corpus {corpus!r} root does not exist: {root}\n  "
            f"{ACQUISITION.get(corpus, '')}"
        )
    # Excluded-gold guard (gate #7): never accept machine-aligned corpora as gold.
    hit = is_excluded_gold(str(root), cfg.excluded_as_gold)
    if hit:
        raise ValueError(
            f"gold corpus {corpus!r} root {root} matches banned machine-aligned "
            f"source {hit!r}. Forced/MFA alignments are invalid as ground truth "
            f"(Plan 1.3)."
        )

    gen = _dispatch(corpus, root, spec, cfg)
    if limit is not None:
        # partial/dev run: stop early (Buckeye segments long tracks lazily) and
        # do NOT write the cache — it must only ever hold the full corpus.
        import itertools

        return list(itertools.islice(gen, limit))

    utts = list(gen)
    dump_jsonl(utts, cache)
    return utts


def _dispatch(corpus: str, root: Path, spec: dict, cfg: Config):
    if corpus == "timit":
        from fabench.dataprep.datasets.en import timit

        yield from timit.iter_utterances(root, subset=spec.get("subset", "core_test"),
                                         merge_closures=bool(spec.get("merge_closures", False)))
    elif corpus == "buckeye":
        from fabench.dataprep.datasets.en import buckeye

        yield from buckeye.iter_utterances(
            root, cfg.work_dir(), protocol=spec.get("protocol", "fabench"),
            subset=spec.get("subset")
        )
    elif corpus == "l2arctic":
        from fabench.dataprep.datasets.en import l2arctic

        yield from l2arctic.iter_utterances(root, subset=spec.get("subset", "manual"))
    else:
        raise KeyError(f"no ingester for corpus {corpus!r}")
