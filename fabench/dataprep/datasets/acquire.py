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

"""Shared machinery for the per-corpus ``download.py`` scripts.

None of FA-Bench's gold corpora can be downloaded by a script. TIMIT is sold
under an LDC licence, Buckeye is released only after OSU accepts a signed
agreement, and L2-ARCTIC is gated behind a request form. So ``download.py``
does the honest three things a download script can still do:

1. print exactly where the corpus comes from, what it costs, and who holds it;
2. VERIFY a copy you have already obtained -- the layout the processor expects,
   reported per-probe so a wrong root is obvious;
3. exit non-zero when the corpus is not usable, so a pipeline stage can gate on
   it instead of failing later inside an ingest.

It never fetches, and never will: automating around a licence check would be
circumventing it. A corpus that COULD be fetched (MUSAN, RIRS) is handled by
the noise recipe, not here.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Probe:
    """One structural expectation, matched with rglob.

    rglob, not glob, because every processor here uses ``root.rglob(...)`` --
    Buckeye in particular extracts to ``sNN/sNNNNx.phones`` (two levels) though
    its README documents three. A fixed-depth probe reported a correct corpus as
    broken, so the probe must be exactly as depth-agnostic as the code it
    speaks for.
    """
    glob: str
    what: str
    min_count: int = 1


@dataclass(frozen=True)
class Corpus:
    name: str
    holder: str
    url: str
    access: str               # one short line: what a user must actually do
    licence: str              # redistribution terms, in the user's interest
    catalog_id: str = ""
    citation: str = ""
    layout: str = ""
    probes: tuple[Probe, ...] = field(default_factory=tuple)
    roots: tuple[str, ...] = ()      # alternative root spellings to try


def _bar(s: str = "") -> str:
    return s or "-" * 72


def notice(c: Corpus) -> str:
    L = [_bar(), f"{c.name}  --  NOT downloadable by this script", _bar(), ""]
    if c.catalog_id:
        L.append(f"  catalog   {c.catalog_id}")
    L += [f"  holder    {c.holder}",
          f"  url       {c.url}",
          "",
          f"  ACCESS    {c.access}",
          f"  LICENCE   {c.licence}", ""]
    if c.layout:
        L += ["  Expected layout once obtained:", ""]
        L += [f"      {ln}" for ln in c.layout.strip().splitlines()]
        L.append("")
    if c.citation:
        L += ["  Cite:", f"      {c.citation}", ""]
    return "\n".join(L)


def _resolve(c: Corpus, root: Path) -> Path:
    """Accept the common re-nestings (``<root>/TIMIT/TRAIN`` vs ``<root>/TRAIN``)."""
    if not c.roots:
        return root
    for alt in ("",) + c.roots:
        cand = root / alt if alt else root
        if cand.is_dir() and any(
                next(iter(cand.rglob(p.glob)), None) for p in c.probes):
            return cand
    return root


def verify(c: Corpus, root: Path) -> bool:
    """Report each structural probe against ``root``. True if all pass."""
    root = Path(root).expanduser()
    print(f"  checking {root}")
    if not root.is_dir():
        print("    MISSING  root is not a directory")
        return False
    actual = _resolve(c, root)
    if actual != root:
        print(f"    (corpus found nested at {actual})")
    ok = True
    for p in c.probes:
        n = sum(1 for _ in actual.rglob(p.glob))
        if n >= p.min_count:
            print(f"    ok       {n:>6} {p.what}")
        else:
            ok = False
            print(f"    MISSING  {n:>6} {p.what}  (expected >= {p.min_count})")
            print(f"             glob: {actual}/{p.glob}")
    return ok


def cli(c: Corpus, argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=f"Acquisition notice and layout check for {c.name}.")
    ap.add_argument("root", nargs="?", help="path to your copy of the corpus")
    ap.add_argument("--quiet", action="store_true",
                    help="skip the notice; just check and set the exit code")
    a = ap.parse_args(argv)

    if not a.quiet:
        print(notice(c))
    if not a.root:
        print("  No root given -- nothing to check.")
        print(f"  Once obtained:  python {sys.argv[0]} <root>")
        return 1
    ok = verify(c, Path(a.root))
    print()
    print("  USABLE" if ok else "  NOT USABLE -- see MISSING lines above")
    return 0 if ok else 1
