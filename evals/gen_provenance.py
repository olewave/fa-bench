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

"""Generate the aligner-provenance table: version, commit, release date.

WHY GENERATED. The provenance table was hand-written, and a hand-written
version number is a claim nobody re-checks. This reads what is ACTUALLY
INSTALLED -- the lock files, the conda-meta entries, the git checkouts -- so
the table cannot drift from the environment that produced the numbers.

Release dates come from PyPI's upload_time for the exact pinned version, or
from the commit date for git-installed tools. They are cached in
`docs/_provenance.json` so a build works offline and so a re-run cannot
silently change a published date.

Usage:
    gen_provenance.py            # refresh from the environment (+ PyPI)
    gen_provenance.py --offline  # rebuild the table from the cache only
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Beside the script that writes it. It used to live in docs/, and went with
# that tree -- leaving --offline pointing at a file that no longer existed.
CACHE = ROOT / "evals" / "_provenance.json"

#: display name, how to find the version, and the PyPI project to date it by.
#: `git` entries take version+date from the checkout instead.
TOOLS = [
    ("MFA 3.4", "mfa", {"conda": ("mfa", "montreal-forced-aligner"),
                        "pypi": "montreal-forced-aligner"}),
    ("MFA 2.0", "mfa2", {"conda": ("mfa20", "montreal-forced-aligner"),
                         "pypi": "montreal-forced-aligner"}),
    ("Charsiu", "charsiu", {"git": "evals/aligners/charsiu/repo/charsiu"}),
    ("MAPS", "maps", {"git": "evals/aligners/maps/repo/MAPS"}),
    ("BFA", "bfa", {"lock": ("evals/aligners/bfa/requirements.lock",
                             "bournemouth-forced-aligner"),
                    "pypi": "bournemouth-forced-aligner"}),
    ("WhisperX", "whisperx", {"lock": ("evals/aligners/whisperx/requirements.lock",
                                       "whisperx"), "pypi": "whisperx"}),
    ("Qwen3", "qwen3_fa",
     {"lock": ("evals/aligners/qwen3_fa/requirements.lock", "qwen-asr"),
      "pypi": "qwen-asr"}),
    ("CrisperWhisper-FA", "crisperwhisper_fa",
     {"lock": ("evals/timestamp_asrs/crisperwhisper/requirements.lock",
               "crisperwhisper"), "pypi": "crisperwhisper"}),
    ("TorchAudio", "torchaudio_fa",
     {"import": "torchaudio", "pypi": "torchaudio"}),
    ("Parakeet-TDT", "parakeet_tdt",
     {"lock": ("evals/timestamp_asrs/parakeet_tdt/requirements.observed",
               "nemo-toolkit"), "pypi": "nemo-toolkit"}),
    ("stable-ts", "stable_ts",
     {"gitlock": ("evals/aligners/stable_ts/requirements.lock", "stable-ts")}),
    # One version, the released one. The second number was an internal
    # build id and said nothing a reader could use.
    ("Olign", "olign", {"fixed": ("v1.0.0", "—", "undisclosed")}),
]


def from_gitlock(rel: str, pkg: str) -> tuple[str | None, str | None]:
    """Commit from a uv-freeze line of the form `pkg @ git+URL@SHA`."""
    p = ROOT / rel
    if not p.is_file():
        return None, None
    for line in p.read_text().splitlines():
        if line.lower().startswith(pkg.lower() + " @ git+") and "@" in line:
            sha = line.rsplit("@", 1)[-1].strip()
            if len(sha) >= 12:
                return "(git)", sha
    return None, None


def from_lock(rel: str, pkg: str) -> str | None:
    p = ROOT / rel
    if not p.is_file():
        return None
    for line in p.read_text().splitlines():
        name, _, ver = line.partition("==")
        if name.strip().lower().replace("_", "-") == pkg.lower():
            return ver.strip().split("+")[0] or None
    return None


def from_conda(env: str, pkg: str) -> str | None:
    for base in ("mfa", "mfa2"):
        d = ROOT / "evals" / "aligners" / base / "repo" / "mamba" / "envs" / env / "conda-meta"
        if not d.is_dir():
            continue
        for f in d.glob(f"{pkg}-*.json"):
            m = re.search(rf"{re.escape(pkg)}-([0-9][^-]*)-", f.name)
            if m:
                return m.group(1)
    return None


def from_git(rel: str) -> tuple[str | None, str | None]:
    d = ROOT / rel
    if not (d / ".git").is_dir():
        return None, None
    def run(*a):
        try:
            return subprocess.run(["git", "-C", str(d), *a], capture_output=True,
                                  text=True, timeout=20, check=False).stdout.strip() or None
        except Exception:
            return None
    return run("rev-parse", "HEAD"), run("log", "-1", "--format=%cd", "--date=short")


def pypi_date(pkg: str, ver: str) -> str | None:
    try:
        import urllib.request
        with urllib.request.urlopen(
                f"https://pypi.org/pypi/{pkg}/{ver}/json", timeout=20) as r:
            urls = json.load(r).get("urls") or []
            return urls[0]["upload_time"][:10] if urls else None
    except Exception:
        return None


def collect(offline: bool) -> dict:
    cache = json.loads(CACHE.read_text()) if CACHE.is_file() else {}
    out = {}
    for disp, slug, how in TOOLS:
        prev = cache.get(slug, {})
        if "fixed" in how:
            ver, commit, date = how["fixed"]
        else:
            commit = date = None
            ver = None
            if "gitlock" in how:
                ver, commit = from_gitlock(*how["gitlock"])
            elif "git" in how:
                commit, date = from_git(how["git"])
                # No release version exists for these -- they are research
                # repos with no PyPI release, so the COMMIT is the version.
                # Repeating the hash in both columns just wastes a column.
                ver = "(git)" if commit else None
            elif "conda" in how:
                ver = from_conda(*how["conda"])
            elif "lock" in how:
                ver = from_lock(*how["lock"])
            elif "import" in how:
                try:
                    mod = __import__(how["import"])
                    ver = getattr(mod, "__version__", "").split("+")[0] or None
                except Exception:
                    ver = None
            if date is None and ver and "pypi" in how and not offline:
                date = pypi_date(how["pypi"], ver)
            # never lose a previously recorded value to a transient failure
            ver = ver or prev.get("version")
            commit = commit or prev.get("commit")
            date = date or prev.get("released")
        out[slug] = {"display": disp, "version": ver, "commit": commit,
                     "released": date}
    return out


def table(data: dict) -> str:
    L = ["| System | Version | Commit | Released |", "|---|---|---|---|"]
    for slug in sorted(data, key=lambda s: data[s]["display"].lower()):
        d = data[slug]
        c = d.get("commit") or "—"
        if c not in ("—", None) and len(c) > 12:
            c = f"`{c[:12]}`"
        L.append(f"| {d['display']} | {d.get('version') or '—'} | {c} "
                 f"| {d.get('released') or '—'} |")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true",
                    help="rebuild from docs/_provenance.json, no network")
    # The published snapshot, not summary/ -- which is script output now.
    # publish_records.py passes the dated directory; this default is the
    # current one for a manual run.
    ap.add_argument("--doc", default=str(ROOT / "records" / "aligners" / "en"
                                        / "latest" / "README.md"))
    a = ap.parse_args(argv)

    data = collect(a.offline)
    CACHE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    missing = [s for s, d in data.items() if not d.get("version")]
    if missing:
        print(f"  no version resolved for: {', '.join(missing)}", file=sys.stderr)

    body = table(data)
    # resolve() so a relative --doc still prints (and compares) correctly:
    # relative_to(ROOT) raised on the unresolved path AFTER the file was
    # already written, which read as a failed run that had in fact succeeded
    doc = Path(a.doc).resolve()
    text = doc.read_text()
    b, e = "<!-- BEGIN GENERATED: provenance -->", "<!-- END GENERATED: provenance -->"
    if b not in text:
        print(f"  no provenance markers in {doc}; add:\n    {b}\n    {e}",
              file=sys.stderr)
        return 1
    new = re.sub(re.escape(b) + r".*?" + re.escape(e), f"{b}\n{body}\n{e}",
                 text, flags=re.DOTALL)
    if new != text:
        doc.write_text(new)
        rel = doc.relative_to(ROOT) if doc.is_relative_to(ROOT) else doc
        print(f"  wrote {rel} ({len(data)} systems)")
    else:
        print("  no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
