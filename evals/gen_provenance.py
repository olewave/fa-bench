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
    ("Qwen3-FA", "qwen3_fa",
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
    # The rest of the systems the records score. An environment that lives on
    # another machine (the GPU box) is read there; here its entry falls back to
    # the cached value, which is why the cache is committed.
    ("FALCON", "falcon", {"git": "evals/aligners/falcon/repo"}),
    ("MMS-FA", "mms_fa", {"venv": ("evals/aligners/torchaudio_fa/venv", "torchaudio"),
                          "pypi": "torchaudio"}),
    ("NeMo-FA", "nemo_fa", {"venv": ("evals/aligners/nemo_fa/venv", "nemo_toolkit"),
                            "pypi": "nemo-toolkit"}),
    ("NeuFA", "neufa", {"git": "evals/aligners/neufa/repo"}),
    ("UnitY2", "unity2", {"git": "evals/aligners/unity2/repo"}),
    ("CrisperWhisper", "crisperwhisper",
     {"lock": ("evals/timestamp_asrs/crisperwhisper/requirements.lock",
               "crisperwhisper"), "pypi": "crisperwhisper"}),
    ("Qwen3-ASR", "qwen3_asr", {"venv": ("evals/timestamp_asrs/qwen3_asr/venv", "qwen_asr"),
                                "pypi": "qwen-asr"}),
    ("TorchAudio (ASR)", "torchaudio_asr", {"import": "torchaudio", "pypi": "torchaudio"}),
    ("Whisper large-v3", "whisper3", {"venv": ("evals/timestamp_asrs/whisper3/venv",
                                               "transformers"), "pypi": "transformers"}),
    ("Whisper-timestamped", "whisper_ts",
     {"venv": ("evals/timestamp_asrs/whisper_ts/venv", "whisper_timestamped"),
      "pypi": "whisper-timestamped"}),
    ("WhisperX (ASR)", "whisperx_asr",
     {"lock": ("evals/aligners/whisperx/requirements.lock", "whisperx"),
      "pypi": "whisperx"}),
]

#: Which checkpoint each row ran, when the recipe does not say it plainly or
#: several recipes share the row. Everything else is read from the recipe's
#: `model` (and `phoneme_model`) parameter.
CHECKPOINT = {
    # The recipe names the checkpoint our own sweep used, which the authors
    # say is wrong; the published rows are the authors' output.
    "neufa": "neufa-fabench-220k.pt, the authors', not released "
             "(SHA-256 `68b163eb3599`)",
    "nemo_fa": "stt_en_fastconformer_hybrid_large_pc (80 ms), "
               "stt_en_conformer_ctc_large (40 ms)",
    "bfa": "Tabahi/CUPE-2i en_libri1000_ua01c_e4 (preset en-us)",
    "stable_ts": "Whisper base",
    "whisper_ts": "Whisper large-v3",
    "mfa": "english_us_arpa acoustic model and dictionary",
    "mfa2": "english_us_arpa acoustic model and dictionary",
    "olign": "—",
    "qwen3_asr": "Qwen/Qwen3-ASR-1.7B, with Qwen/Qwen3-ForcedAligner-0.6B",
    "whisperx_asr": "Whisper large-v3, then WAV2VEC2_ASR_BASE_960H",
}

#: The commercial endpoints, by the name the records print. The model and
#: request settings come from the recipe; the dates are those of the calls the
#: published rows were built from.
APIS = [
    ("Amazon Transcribe", "aws"),
    ("AssemblyAI Universal 3.5", "assemblyai"),
    ("Azure AI Speech", "azure"),
    ("Deepgram Nova-3", "deepgram"),
    ("ElevenLabs Scribe v2", "elevenlabs"),
    ("Google Chirp 2", "google_stt_chirp2"),
    ("IBM Watson Large", "ibm"),
    ("Speechmatics enhanced", "speechmatics"),
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


def from_venv(rel: str, dist: str) -> str | None:
    """Version of `dist` installed in a venv, from its dist-info directory."""
    real = (ROOT / rel).resolve()
    want = dist.lower().replace("-", "_")
    for d in real.glob("lib/python*/site-packages/*.dist-info"):
        name, _, ver = d.name[:-len(".dist-info")].rpartition("-")
        if name.lower().replace("-", "_") == want:
            return ver.split("+")[0] or None
    return None


def recipe(slug: str) -> dict:
    """The tool's own config.yaml, or {} when there is none."""
    import yaml

    sys.path.insert(0, str(ROOT))
    from fabench.paths import tool_index
    hit = tool_index(ROOT).get(slug)
    if not hit:
        return {}
    p = ROOT / hit[1] / "config.yaml"
    return (yaml.safe_load(p.read_text()) or {}) if p.is_file() else {}


def checkpoint(slug: str) -> str:
    if slug in CHECKPOINT:
        return CHECKPOINT[slug]
    params = recipe(slug).get("params") or {}
    names = []
    for k in ("model", "phoneme_model"):
        v = str(params.get(k) or "")
        if v.startswith(("repo/", "pretrained_models/")):
            v = v.rsplit("/", 1)[-1]          # a local file: its name, not our path
        if v:
            names.append(v)
    return ", ".join(names) or "—"


def api_called(slug: str) -> str | None:
    """First and last day of the calls behind a published API row.

    A record replayed from the response cache carries `fetched_at`; one from a
    fresh call carries the call's `latency_s`, which the cache entry stores
    beside its own `fetched_at`. Either way the date is the response's, not
    the day the file was written. Reads local files only."""
    sys.path.insert(0, str(ROOT))
    from fabench.paths import tool_index
    hit = tool_index(ROOT).get(slug)
    if not hit:
        return None
    base = ROOT / hit[1]
    by_latency = {}
    for p in (base / "cache").rglob("*.json"):
        try:
            e = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if e.get("latency_s") is not None and e.get("fetched_at"):
            by_latency[round(e["latency_s"], 9)] = e["fetched_at"][:10]
    days = set()
    for h in base.glob("en/*/*/*/hyp.jsonl"):
        for line in h.open():
            r = json.loads(line)
            day = (r.get("fetched_at") or "")[:10] or by_latency.get(
                round(r["latency_s"], 9) if r.get("latency_s") is not None else None)
            if day:
                days.add(day)
    return f"{min(days)} to {max(days)}" if days else None


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
            elif "venv" in how:
                ver = from_venv(*how["venv"])
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
                     "released": date, "checkpoint": checkpoint(slug)}
    apis = {}
    for disp, slug in APIS:
        params = recipe(slug).get("params") or {}
        prev = (cache.get("_apis") or {}).get(slug, {})
        called = prev.get("called") if offline else (api_called(slug) or prev.get("called"))
        model = str(params.get("model") or "—")
        if params.get("api_version"):
            model += f", API {params['api_version']}"
        apis[slug] = {"display": disp, "model": model, "called": called}
    out["_apis"] = apis
    return out


def table(data: dict) -> str:
    L = ["| System | Version | Commit | Released | Checkpoint |",
         "|---|---|---|---|---|"]
    rows = {s: d for s, d in data.items() if not s.startswith("_")}
    for slug in sorted(rows, key=lambda s: rows[s]["display"].lower()):
        d = rows[slug]
        c = d.get("commit") or "—"
        if c not in ("—", None) and len(c) > 12:
            c = f"`{c[:12]}`"
        L.append(f"| {d['display']} | {d.get('version') or '—'} | {c} "
                 f"| {d.get('released') or '—'} | {d.get('checkpoint') or '—'} |")
    apis = data.get("_apis") or {}
    if apis:
        L += ["", "Commercial endpoints, with the model as requested and the days "
              "of the calls the published rows come from (UTC).", "",
              "| Endpoint | Model | Called |", "|---|---|---|"]
        for slug in sorted(apis, key=lambda s: apis[s]["display"].lower()):
            d = apis[slug]
            L.append(f"| {d['display']} | {d.get('model') or '—'} | {d.get('called') or '—'} |")
    return "\n".join(L)



def fabench_release(release: str | None = None) -> str:
    """One line naming the FA-Bench commit this snapshot was cut from.

    The table below says which VERSION of each system produced the numbers. It
    says nothing about the version of the benchmark that measured them, and the
    scoring code moves: a matcher change, a normalisation fix or a new metric
    all shift published numbers without touching a single aligner. Without the
    commit, a snapshot cannot be reproduced -- you would know what was measured
    but not what did the measuring.

    A dirty tree is reported as such rather than silently attributed to HEAD,
    because a snapshot cut from uncommitted work is not reproducible from that
    commit and saying so is the whole point of recording it.
    """
    import subprocess

    # A published snapshot names the PUBLIC release that holds its numbers
    # (`--release v1.2.0` or a public commit). Read from the checkout it would
    # name the private branch it was cut on, which a reader cannot fetch.
    if release:
        return f"**FA-Bench release** `{release}`"

    def git(*args):
        try:
            # check=False: a missing git, or a directory that is not a
            # checkout, means "no commit to record" -- not a failed publish.
            return subprocess.run(("git", *args), cwd=ROOT, capture_output=True,
                                  text=True, timeout=30, check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    sha = git("rev-parse", "--short=12", "HEAD")
    if not sha:
        return "**FA-Bench release:** unknown (not a git checkout)"
    when = (git("log", "-1", "--format=%cs") or "").strip()
    dirty = " + uncommitted changes" if git("status", "--porcelain") else ""
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    where = f", branch `{branch}`" if branch and branch != "HEAD" else ""
    return f"**FA-Bench release** commit `{sha}`{where} ({when}){dirty}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true",
                    help="rebuild from docs/_provenance.json, no network")
    # The published snapshot, not summary/ -- which is script output now.
    # publish_records.py passes the dated directory; this default is the
    # current one for a manual run.
    ap.add_argument("--doc", default=str(ROOT / "records" / "latest" / "en"
                                        / "README.md"))
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the versions table on the page differs from "
                         "the cache; writes nothing. The release line is not "
                         "compared, since it names a release only at publish time")
    ap.add_argument("--release", default=None,
                    help="public tag or commit to name on the release line; "
                         "without it the line describes this checkout")
    a = ap.parse_args(argv)

    data = collect(a.offline)
    if a.check:
        doc = Path(a.doc).resolve()
        b, e = "<!-- BEGIN GENERATED: provenance -->", "<!-- END GENERATED: provenance -->"
        m = re.search(re.escape(b) + r"\n(.*?)\n" + re.escape(e), doc.read_text(), re.DOTALL)
        shown = m.group(1).split("\n\n", 1)[1] if m and "\n\n" in m.group(1) else None
        if shown != table(data):
            print(f"  STALE: the versions table in {doc} differs from the cache",
                  file=sys.stderr)
            return 1
        print("  provenance up to date")
        return 0
    CACHE.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    missing = [s for s, d in data.items()
               if not s.startswith("_") and not d.get("version")]
    if missing:
        print(f"  no version resolved for: {', '.join(missing)}", file=sys.stderr)

    body = fabench_release(a.release) + "\n\n" + table(data)
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
        print(f"  wrote {rel} ({sum(1 for s in data if not s.startswith('_'))} systems)")
    else:
        print("  no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
