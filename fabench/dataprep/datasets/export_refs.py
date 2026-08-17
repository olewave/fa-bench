#!/usr/bin/env python3
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

"""Materialise gold as ``ref.jsonl``, mirroring each tool's ``hyp.jsonl``.

WHY THIS EXISTS. Gold used to be in-memory only: ``fabench score`` called
``ingest_corpus()`` and held a dict keyed by utt_id. That works, but it means
the reference side of every published number has no artefact you can diff,
checksum, or hand to someone re-running the benchmark. hyp.jsonl is on disk;
the reference now is too.

LAYOUT. One file per (subset, level), beside the split list that defines it:

    datasets/languages/<lang>/<corpus>/split/<subset>.phone.ref.jsonl
    datasets/languages/<lang>/<corpus>/split/<subset>.word.ref.jsonl

Phone and word are separate files because they are separate evaluations: a
word-only system (whisperx, qwen3_fa) has no phone reference to score against,
and splitting them makes that explicit rather than encoding it as an empty
list.

*** THESE FILES ARE GITIGNORED, AND THAT IS DELIBERATE. ***

They are TIMIT's ``.PHN`` and Buckeye's ``.phones`` reformatted -- the licensed
annotation itself, not a derivative. TIMIT is sold under an LDC licence and
Buckeye released only under an OSU agreement; both forbid redistribution. The
path is inside the repo so the reference sits next to the split list that
selects it, but ``.gitignore`` keeps the content out of history. Committing
them would republish LDC and OSU material, and git history is not easy to
retract. To publish gold anyway, remove the ignore rule knowingly.

JSONL, one record per line, matching hyp.jsonl. Metadata rides on every
record (``source``/``corpus``/``subset``/``level``) rather than in a header
line, because that is what hyp.jsonl already does -- its records each carry
``aligner``/``condition``/``corpus`` -- and because a header line makes naive
``for line in f: json.loads(line)`` readers trip on the first record.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def ref_path(repo_root: Path, corpus: str, subset: str, level: str,
             lang: str = "en") -> Path:
    """``datasets/languages/<lang>/<corpus>/split/<subset>.<level>.ref.json``.

    ``level`` is ``phone`` or ``word`` -- the two evaluations are scored
    separately and not every system produces both.
    """
    if level not in ("phone", "word"):
        raise ValueError(f"level must be phone|word, got {level!r}")
    from fabench.paths import split_dir

    return (split_dir(repo_root, lang, corpus)
            / f"{subset}.{level}.ref.jsonl")


def _ivals(seq) -> list[dict]:
    out = []
    for iv in seq or []:
        out.append({
            "label": iv.label,
            "start": round(float(iv.start), 6),
            "end": round(float(iv.end), 6),
            "conf": getattr(iv, "conf", None),
        })
    return out


def export(corpus: str, cfg, repo_root: Path, lang: str = "en") -> list[tuple[Path, int]]:
    """Write the phone and word references for this config's subset."""
    from fabench.dataprep.datasets import ingest_corpus

    subset = cfg.subset_of(corpus) or "all"
    utts = ingest_corpus(corpus, cfg)
    written = []
    for level, attr in (("phone", "phones"), ("word", "words")):
        recs = []
        for u in utts:
            ivals = _ivals(getattr(u, attr, None))
            if not ivals:
                continue        # a corpus without this tier contributes nothing
            recs.append({"utt_id": u.utt_id, "source": "gold",
                         "corpus": corpus, "subset": subset, "level": level,
                         "lang": lang, "intervals": ivals})
        if not recs:
            continue
        out = ref_path(repo_root, corpus, subset, level, lang)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in recs)
        written.append((out, len(recs)))
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Optional, like every other entry point: load_config(None) composes a
    # complete run from datasets/languages/ and fabench/, so exporting the gold
    # references needs no file. It was required back when a run config was the
    # only source of a corpus root; roots now come from .fabench.env.
    ap.add_argument("--config", default=None,
                    help="run config YAML; omit to use the composed defaults")
    ap.add_argument("--corpus", help="restrict to one corpus")
    ap.add_argument("--repo-root", default=".",
                    help="repo root; refs land under datasets/languages/<lang>/<corpus>/split/")
    a = ap.parse_args(argv)

    # This file is an ENTRY POINT, so it applies .fabench.env the way the CLI
    # does. fabench/envfile.py deliberately never applies it on import -- a
    # library that absorbed a machine's settings would make tests and sweeps
    # depend on where they ran -- but that left a script invoked directly
    # without the staged corpus roots: `fabench ingest` found TIMIT and this
    # failed on the same machine, in the same run, one line apart.
    from fabench.config import load_config
    from fabench.envfile import load_env_file

    load_env_file()
    cfg = load_config(a.config)

    corpora = [a.corpus] if a.corpus else [c for c, _ in cfg.enabled_gold()]
    rc = 0
    for c in corpora:
        try:
            for out, n in export(c, cfg, Path(a.repo_root)):
                print(f"  {c}: {n} utterances -> {out}")
        except Exception as e:                      # one corpus must not lose the rest
            print(f"  {c}: FAILED {type(e).__name__}: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
