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

"""Where a tool's raw output lives.

ONE definition, used by both the writer (`fabench.aligners.runner`) and the
reader (`fabench.score.runner`). They previously each built the path inline; if
they ever disagreed, a sweep would write hypotheses the scorer could not find
and every cell would silently score as empty.

Layout — a cell's raw output AND its scores sit with the tool that produced
them, in one directory:

    evals/<kind>/<tool>/<lang>/<corpus>/<subset>/<condition>/
        hyp.jsonl              the alignment
        leaderboard.csv        its score
        leaderboard.parquet
        per_type.parquet

    evals/aligners/mfa/en/timit/core_test/origin/hyp.jsonl
    evals/aligners/mfa/en/buckeye/dev/babble/hyp.jsonl

`<condition>` is a directory, not a `__` suffix on the subset: `origin` for the
un-augmented audio, else the noise type. A suffix made the subset name carry
structure, which is unparseable in both directions -- subsets and conditions
both contain underscores -- and it sorted `dev` away from `dev__babble`.

`<kind>` is `aligners` or `timestamp_asrs`, mirroring `fabench.aligners` /
`fabench.timestamp_asrs`: the split is by INPUT (transcript given vs audio only), so a
tool's directory says which contract it satisfies.

`summary/` keeps only DERIVED, cross-tool artefacts — leaderboards, reports,
per-type tables. That division is what makes `evals/rescore_all.sh` cheap: the
expensive alignments are never regenerated, only re-read.
"""

from __future__ import annotations

from pathlib import Path

#: Tool families, each mirroring a fabench package. `timestamp_asrs` are
#: ASRs that emit word timestamps -- they IGNORE the reference transcript,
#: so their rows mix recognition error with timing error and must not be
#: ranked head-to-head against aligners.
KINDS = ("aligners", "timestamp_asrs")


def evals_dir(root: Path) -> Path:
    return Path(root) / "evals"


#: Where the per-language dataset trees live: `datasets/languages/<lang>/`,
#: with each corpus one level below that.
#:
#: ONE definition, for the same reason as the hyp path above. Every consumer
#: globs by DEPTH -- `<lang>/config.yaml` at 1, `<lang>/<corpus>/config.yaml`
#: at 2 -- so a path that is off by one level does not raise; it silently
#: reinterprets the language file as a corpus. Moving `datasets/en/` under
#: `datasets/languages/` did exactly that: `en` became a corpus and TIMIT and
#: Buckeye disappeared from every composed config, with only a "no gold corpus
#: enabled" warning to show for it.
_LANGUAGES = ("datasets", "languages")


def languages_dir(root: Path) -> Path:
    """`datasets/languages/` under `root`, whether or not it exists."""
    return Path(root).joinpath(*_LANGUAGES)


def language_dir(root: Path, lang: str) -> Path:
    """`datasets/languages/<lang>/` — the tree for one language."""
    return languages_dir(root) / lang


def split_dir(root: Path, lang: str, corpus: str) -> Path:
    """Where a corpus's split lists live: `<lang>/<corpus>/split/`."""
    return language_dir(root, lang) / corpus / "split"


#: A tool directory may sit at three depths under `evals/<kind>/`:
#:
#:     <tool>/                 the official, current recipe
#:     <tool>/exps/<name>/     a manipulation of it (ablations, sweeps)
#:     <tool>/v<version>/      a historical version, kept runnable
#:
#: so variants of one system stay under that system instead of sprawling
#: across the aligner list as siblings (mfa2, <tool>_<variant>, ...).
#: Every recipe declares its own `name:`, which is what a config and a
#: leaderboard row use; the directory is free to be nested.
_TOOL_GLOBS = ("*/config.yaml", "*/exps/*/config.yaml", "*/v*/config.yaml")


def tool_index(root: Path) -> dict[str, tuple[str, Path]]:
    """``{declared name: (kind, directory)}`` for every recipe under evals/.

    Built by reading each ``config.yaml``'s ``name:`` rather than by guessing
    from the path, so a nested recipe is found by the same name a run config
    and a results row use.
    """
    import yaml

    out: dict[str, tuple[str, Path]] = {}
    base = evals_dir(root)
    for kind in KINDS:
        kdir = base / kind
        if not kdir.is_dir():
            continue
        for pattern in _TOOL_GLOBS:
            for cfg in sorted(kdir.glob(pattern)):
                try:
                    spec = yaml.safe_load(cfg.read_text()) or {}
                except (OSError, yaml.YAMLError):
                    continue
                name = spec.get("name") if isinstance(spec, dict) else None
                out.setdefault(str(name or cfg.parent.name), (kind, cfg.parent))
    return out


def tool_kind(root: Path, tool: str) -> str:
    """Which contract a tool satisfies, inferred from where its recipe lives.

    Inferred rather than configured so a tool cannot be declared one thing and
    installed as another. Defaults to `aligners` for a tool with no recipe yet
    (a config may name a tool before `evals/` catches up).
    """
    # A directory alone is NOT evidence: run_evals.sh used to `mkdir -p
    # evals/aligners/<tool>/log` unconditionally, which left PHANTOM dirs holding
    # only en/ and log/ for tools whose real recipe lives elsewhere. Once such a
    # dir existed, first-match-wins permanently misclassified the tool --
    # crisperwhisper (a timestamp_asr) was filed under aligners for its whole
    # history, and parakeet_tdt before it. Require the recipe itself.
    hit = tool_index(root).get(tool)
    if hit:
        return hit[0]
    for kind in KINDS:                      # fall back to mere existence
        if (evals_dir(root) / kind / tool).is_dir():
            return kind
    return "aligners"


def tool_dir(root: Path, tool: str, kind: str | None = None) -> Path:
    """The tool's directory, wherever it sits in the layout above."""
    hit = tool_index(root).get(tool)
    if hit and (kind is None or hit[0] == kind):
        return hit[1]
    return evals_dir(root) / (kind or tool_kind(root, tool)) / tool


def hyp_path(
    root: Path,
    tool: str,
    corpus: str,
    subset: str,
    lang: str = "en",
    kind: str | None = None,
    condition: str = "",
) -> Path:
    """The one true location of `<tool>`'s raw output for one cell.

    ``condition`` separates a noise-augmented run from the un-augmented one.
    Without it every noisy run wrote to the SAME path as clean -- the noisy
    configs carry `name: mfa`, so `mfa` under reverb would have overwritten the
    baseline the comparison exists to make. It is its OWN directory level, and
    the un-augmented run is `origin` rather than an absent segment, so every
    cell is the same depth and a listing shows the conditions side by side.
    """
    return cell_dir(root, tool, corpus, subset, lang, kind, condition) / "hyp.jsonl"


#: The un-augmented audio, as a directory name. Named rather than omitted so
#: every cell sits at the same depth -- `ls <subset>/` then answers "which
#: conditions did this tool run?" in one line.
ORIGIN = "origin"


def cell_dir(
    root: Path,
    tool: str,
    corpus: str,
    subset: str,
    lang: str = "en",
    kind: str | None = None,
    condition: str = "",
) -> Path:
    """Everything about one (tool, corpus, subset, condition): hyp AND scores.

    They were split across `evals/` and `summary/` on an identical key, so one
    cell meant two lookups. A score is only ever read together with the
    alignment it scored, so they share a directory; the CROSS-tool leaderboard,
    which belongs to no single tool, stays under `summary/`.
    """
    return (tool_dir(root, tool, kind) / lang / corpus / subset
            / (condition or ORIGIN))


def find_hyp(root: Path, corpus: str, subset: str, lang: str = "en",
             condition: str = "") -> dict[str, Path]:
    """Every tool that has output for this cell -> its hyp file.

    Used by scoring and by `rescore_all.sh` to discover which tools ran, since
    the files are now spread across per-tool directories rather than pooled in
    one `hyp/` folder.
    """
    out: dict[str, Path] = {}
    # Walks the INDEX, not each kind's top level: a tool nested under
    # <tool>/exps/<name>/ or <tool>/v<version>/ keeps its output beside its
    # own recipe, and a flat iterdir() would miss every one of them.
    for name, (_kind, tdir) in tool_index(root).items():
        p = tdir / lang / corpus / subset / (condition or ORIGIN) / "hyp.jsonl"
        if p.is_file():
            out[name] = p
    return out
