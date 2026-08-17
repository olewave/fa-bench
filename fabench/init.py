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

"""``fabench init`` — write a machine's local run config, once.

Setting up FA-Bench has exactly one irreducible step: saying where the
licensed corpora are staged. TIMIT is LDC-licensed and Buckeye is
registration-gated, so FA-Bench can never fetch or guess them — but it can
look in the usual places, *verify* that what it finds really is the corpus,
and write the config for you.

Everything else already has a default, so the file this writes is short by
design: roots, the aligners to compare, and (commented) the two directory
knobs. Being a file rather than exported variables means it is inspectable,
diffable, and picked up automatically by every later command.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

import yaml

from fabench.envfile import parse_env_file

#: Where a staged corpus is plausibly kept. Each is combined with the corpus
#: name (and its upper/capitalised spellings); nothing is searched recursively,
#: because walking a filesystem to find a corpus is slower and less
#: predictable than asking.
DEFAULT_SEARCH = (
    "data", "data/speech", "corpora",
    "~/data", "~/corpora", "~/speech",
    "/data", "/data/speech", "/corpora", "/scratch", "/mnt/data",
)


def known_corpora(repo: Path) -> dict[str, list[str]]:
    """``{corpus: root_markers}`` for every dataset folder, in name order.

    The markers live in each corpus's own ``datasets/languages/<lang>/
    <corpus>/config.yaml`` — the same file that owns its defaults — so adding a
    corpus teaches ``init`` about it with no change here.
    """
    from fabench.paths import languages_dir

    out: dict[str, list[str]] = {}
    for p in sorted(languages_dir(repo).glob("*/*/config.yaml")):
        try:
            spec = yaml.safe_load(p.read_text()) or {}
        except OSError:
            continue
        if isinstance(spec, dict):
            out[p.parent.name] = list(spec.get("root_markers") or [])
    return out


def looks_staged(root: Path, markers: Iterable[str]) -> bool:
    """Does ``root`` actually hold this corpus? Any marker glob matching is
    enough. Without markers we cannot tell, so we do not claim to."""
    markers = list(markers)
    if not markers or not root.is_dir():
        return False
    for m in markers:
        try:
            if next(root.glob(m), None) is not None:
                return True
        except (OSError, ValueError):
            continue
    return False


#: How far below a search path a corpus may sit. Real trees nest: a corpus
#: staged at /scratch/data/speech/english/TIMIT is four levels under /scratch,
#: and a one-level check (the original) found nothing on the very machine the
#: benchmark was developed on. Bounded so the walk stays a few directory
#: listings rather than a filesystem crawl.
SEARCH_DEPTH = 4


def find_corpus(name: str, markers: Iterable[str], search: Iterable[str],
                depth: int = SEARCH_DEPTH) -> Path | None:
    """First verified staged copy of ``name`` under the search paths, or None.

    Each base is checked for the corpus by name at increasing depth, shallowest
    first, so an obvious location wins over a deeply buried one. Only
    directories NAMED like the corpus are validated, so this never reads inside
    unrelated trees.
    """
    markers = list(markers)
    variants = (name, name.upper(), name.capitalize())
    for base in search:
        b = Path(base).expanduser()
        if not b.is_dir():
            continue
        for lvl in range(depth + 1):
            prefix = "*/" * lvl
            for v in variants:
                try:
                    hits = sorted(b.glob(f"{prefix}{v}"))
                except (OSError, ValueError):
                    continue
                for cand in hits:
                    if looks_staged(cand, markers):
                        return cand.resolve()
    return None


# --------------------------------------------------------------------------
# Interactive setup
# --------------------------------------------------------------------------
def ask(prompt: str, default: str = "") -> str:
    """One question, with the current value offered as the default.

    Enter accepts the default, so a re-run is a series of confirmations rather
    than retyping. EOF (a piped or closed stdin) returns the default instead of
    raising, so this can never hang a script that reached here by accident.
    """
    try:
        got = input(f"  {prompt} [{default}]: " if default else f"  {prompt} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return got or default


def detect_gpus() -> int:
    """How many GPUs nvidia-smi reports; 0 if it is absent or fails."""
    import subprocess

    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return 0
    if r.returncode != 0:
        return 0
    return sum(1 for ln in r.stdout.splitlines() if ln.startswith("GPU "))


def gpu_answer_to_devices(answer: str, total: int) -> str | None:
    """Turn what a human typed into a CUDA device list, or None for 'all'.

    Three results, because CUDA_VISIBLE_DEVICES has three states:

    * ``None``  -- leave it unset, i.e. use every GPU. What "all" or a blank
      answer means. NOT stored as "0,1,2,3": that would silently cap a machine
      that later grows a fifth card, the bug this knob exists to avoid.
    * ``""``    -- set it empty, which is how CUDA is told to expose NO device.
      What "0", "cpu" or "none" means; "0" must not fall through to "all",
      since those are opposite instructions.
    * a list    -- explicit indices. A COUNT like "4" is expanded here, because
      the variable takes indices and people think in counts.
    """
    a = answer.strip().lower()
    if not a or a in ("all", "*"):
        return None
    if a in ("0", "cpu", "none"):
        return ""
    if a.isdigit():
        n = int(a)
        return ",".join(str(i) for i in range(min(n, total) if total else n))
    return ",".join(part.strip() for part in a.split(",") if part.strip())


def set_env_value(path: Path, key: str, value: str | None, template: Path) -> None:
    """Set ``KEY=value`` in a .fabench.env, keeping the file's comments.

    Starts from the tracked template when the file is absent, so a first run
    produces the documented file rather than two bare lines. A commented
    example line (``#KEY=...``) is replaced in place, so the setting lands
    where its explanation is. ``value=None`` re-comments the line, which is how
    "all GPUs" is expressed -- an unset variable, not a value.
    """
    if not path.exists() and template.is_file():
        path.write_text(template.read_text())
    lines = path.read_text().splitlines() if path.exists() else []
    new = f"{key}={value}" if value is not None else f"#{key}="
    for i, ln in enumerate(lines):
        s = ln.lstrip("#").strip()
        if s.startswith(f"{key}=") or s == key:
            indent = ln[: len(ln) - len(ln.lstrip("#"))] if ln.startswith("#") else ""
            lines[i] = new if value is not None else (ln if ln.startswith("#") else f"#{ln}")
            del indent
            break
    else:
        lines.append(new)
    path.write_text("\n".join(lines) + "\n")


def cmd_init(args) -> int:
    from fabench.config import corpus_root_env

    repo = Path(__file__).resolve().parents[1]
    # $FABENCH_ENV_FILE is where the CLI and evals/env.sh already look, so init
    # must write to the same place rather than a second file they would ignore.
    env_file = Path(os.environ.get("FABENCH_ENV_FILE") or repo / ".fabench.env").expanduser()
    template = repo / ".fabench.env.example"

    corpora = known_corpora(repo)
    if not corpora:
        from fabench.paths import languages_dir
        print(f"no datasets found under {languages_dir(repo)}", file=sys.stderr)
        return 1

    explicit: dict[str, str] = {}
    for item in args.root or []:
        if "=" not in item:
            print(f"--root expects <corpus>=<path>, got {item!r}", file=sys.stderr)
            return 1
        name, _, path = item.partition("=")
        if name not in corpora:
            print(f"unknown corpus {name!r}; known: {', '.join(corpora)}", file=sys.stderr)
            return 1
        explicit[name] = path

    # What this machine already says, which becomes the default at each prompt:
    # a re-run should be a series of confirmations, not an interrogation.
    current = parse_env_file(env_file) if env_file.is_file() else {}

    # Prompt only with a real terminal on both ends: a piped or captured stdin
    # (CI, an agent, a nohup sweep) must never block on an answer nobody is
    # there to give. --non-interactive forces the same path from a terminal.
    interactive = (not getattr(args, "non_interactive", False)
                   and sys.stdin.isatty() and sys.stdout.isatty())

    search = list(args.search) if args.search else list(DEFAULT_SEARCH)
    found: dict[str, Path | None] = {}
    for name, markers in corpora.items():
        # --root wins, then what the env file already says, then the search.
        given = explicit.get(name) or current.get(corpus_root_env(name))
        if given:
            root = Path(given).expanduser()
            found[name] = root.resolve()
            if not looks_staged(root, markers):
                print(f"  ! {name}: {root} does not look like a staged copy "
                      f"(no {', '.join(markers) or 'markers known'}) — keeping it anyway",
                      file=sys.stderr)
            else:
                print(f"  + {name}: {root}  ({'given' if name in explicit else 'configured'})")
            continue
        hit = find_corpus(name, markers, search)
        found[name] = hit
        if hit:
            print(f"  + {name}: {hit}  (found)")
        elif not interactive:
            print(f"  - {name}: not found — set {corpus_root_env(name)} in {env_file.name}")
        else:
            print(f"  - {name}: not found")

    # ---- ask ----------------------------------------------------------
    if interactive:
        print("\nSetting up this machine. Enter accepts the value in brackets.\n"
              "Leave a corpus blank if you have not staged it yet — re-run\n"
              "`fabench init` to add it later. GPUs: a count, `all`, or 0 for CPU.\n")
        for name in sorted(corpora):
            answer = ask(f"where did you download {name}?",
                         str(found[name]) if found.get(name) else "")
            if not answer:
                found[name] = None
                continue
            root = Path(answer).expanduser()
            if not looks_staged(root, corpora[name]):
                print(f"      ! no {' / '.join(corpora[name]) or 'known marker'} under {root} — "
                      "keeping it anyway, but check the path")
            found[name] = root.resolve()

        total = detect_gpus()
        # `or "all"` would turn an empty value -- CPU-only, deliberately set --
        # back into "all", so set-ness is tested rather than truthiness.
        cur = current.get("FABENCH_CUDA_DEVICES")
        answer = ask("how many GPUs may a sweep use?",
                     "cpu" if cur == "" else (cur or ("all" if total else "cpu")))
        devices = gpu_answer_to_devices(answer, total)
        set_env_value(env_file, "FABENCH_CUDA_DEVICES", devices, template)
        said = ("all GPUs (left unset)" if devices is None else
                "CPU only (no GPU exposed)" if devices == "" else
                f"FABENCH_CUDA_DEVICES={devices}")
        print(f"      -> {env_file.name}: {said}")

    # ---- write ---------------------------------------------------------
    # One file. Roots are machine-specific AND point at licensed corpora, so
    # they belong with the other machine settings rather than in a tracked
    # tree; everything a RUN is (which corpora, which subset, which systems)
    # already composes from datasets/languages/<lang>/ and evals/.
    wrote: list[str] = []
    for name in sorted(corpora):
        var, root = corpus_root_env(name), found.get(name)
        if root is None:
            # Never blank out a root the user did not just re-answer: a
            # re-run that fails to find a corpus must not un-configure it.
            continue
        if current.get(var) != str(root):
            wrote.append(f"{var}={root}")
        set_env_value(env_file, var, str(root), template)

    print()
    if wrote:
        print(f"{env_file}:")
        for line in wrote:
            print(f"  {line}")
    elif env_file.is_file():
        print(f"{env_file} unchanged.")

    staged = [n for n, r in found.items() if r]
    if not staged:
        print("  looked under: " + ", ".join(str(Path(s).expanduser()) for s in search))
        print(f"  (each up to {SEARCH_DEPTH} levels deep, for a directory named after the corpus)")
        print("  If a corpus is staged elsewhere, say so directly:")
        print("    fabench init --root timit=/path/to/TIMIT --root buckeye=/path/to/Buckeye")
        print("  or point the search at its parent:  fabench init --search /path/to/corpora")
        print("\n  next: stage a corpus, then re-run `fabench init` to add it.")
    else:
        print(f"\n  next: fabench ingest    # {', '.join(staged)} -> canonical gold")
        print("        fabench run        # align, score, report")
    print("  check: fabench config      # prints the fully resolved run")
    return 0
