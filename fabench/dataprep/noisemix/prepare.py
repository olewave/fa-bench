# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""``fabench prepare``: a staged corpus -> the published noise conditions.

Builds into one new directory, for each requested corpus and subset::

    work/                          1. ingest, as ``fabench ingest`` does
    ref/data/golden/<split>/       2. the Kaldi data dirs (``datadirs.py``)
    noisy/<CORPUS>/noisy/<cond>/   3. the conditions (``make_noisy.py``), padded
    shadow/<corpus>_<cond>/        4. the shadow roots (``shadow_root.py``)
    manifest.json                  5. sha256 of every output audio file and input

The draws are seeded and the data dirs are written in the published order, so
the same inputs give the same bytes, and ``cmp`` on two manifests compares two
builds. The output directory must be new or empty, so nothing stale is reused.
Point ``FABENCH_SHADOW`` at ``<out>/shadow`` to evaluate on the result.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fabench.dataprep.noisemix import datadirs, shadow_root

HERE = Path(__file__).resolve().parent
TYPES = shadow_root.TYPES
CORPUS_DIR = {"timit": "TIMIT", "buckeye": "Buckeye"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _digests(files: list[Path], base: Path, jobs: int) -> dict[str, str]:
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        return dict(zip((str(f.relative_to(base)) for f in files), ex.map(_sha256, files)))


def _tree(root: Path, jobs: int, files: list[Path] | None = None) -> dict:
    """One sha256 over the ``<sha256>  <path>`` lines of every file under ``root``."""
    files = sorted(files if files is not None else
                   (p for p in root.rglob("*") if p.is_file()))
    lines = "".join(f"{h}  {p}\n" for p, h in _digests(files, root, jobs).items())
    return {"path": str(root), "files": len(files),
            "sha256": hashlib.sha256(lines.encode()).hexdigest()}


def _binary(exe: Path) -> dict:
    """The executable and every library it loads, since the BLAS changes the bytes."""
    try:
        ldd = subprocess.run(["ldd", str(exe)], capture_output=True, text=True,
                             check=False).stdout
    except FileNotFoundError:
        ldd = ""
    libs = {}
    for line in ldd.splitlines():
        lib = line.partition("=>")[2].split("(")[0].strip()
        if lib.startswith("/"):
            libs[Path(lib).name] = _sha256(Path(lib))
    return {"path": str(exe), "sha256": _sha256(exe), "libs": libs}


def _version(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return (r.stdout or r.stderr).strip().splitlines()[0]


def _plan(cfg, corpora: list[str], subsets: list[str] | None) -> list[tuple[str, str]]:
    """``(corpus, subset)`` pairs. Each corpus takes the named subsets it has."""
    plan = []
    for c in corpora:
        have = datadirs.subsets(c)
        mine = [s for s in subsets if s in have] if subsets else [cfg.datasets["gold"][c]["subset"]]
        if not mine:
            raise SystemExit(f"prepare: {c} has none of {', '.join(subsets)} "
                             f"(it has {', '.join(have)})")
        plan += [(c, s) for s in mine]
    stray = set(subsets or ()) - {s for _, s in plan}
    if stray:
        raise SystemExit(f"prepare: no requested corpus has subset {', '.join(sorted(stray))}")
    return plan


def _kaldi(args) -> tuple[Path, Path, Path]:
    """wav-reverberate, wav-to-duration and Kaldi's wsj ``utils/``."""
    exe = args.wav_reverberate or os.environ.get("FABENCH_WAV_REVERBERATE") \
        or shutil.which("wav-reverberate")
    if not exe or not os.access(exe, os.X_OK):
        raise SystemExit("prepare: no wav-reverberate. Build it with "
                         "tools/build_wav_reverberate.sh, then pass --wav-reverberate "
                         "or set FABENCH_WAV_REVERBERATE")
    exe = Path(exe).resolve()
    # make_musan.sh measures MUSAN with it; Kaldi builds it beside wav-reverberate
    dur = exe.with_name("wav-to-duration")
    if not os.access(dur, os.X_OK):
        dur = Path(shutil.which("wav-to-duration") or "")
    if not dur.name:
        raise SystemExit(f"prepare: no wav-to-duration beside {exe} or on PATH. "
                         "tools/build_wav_reverberate.sh builds both")
    # the utils of the Kaldi tree the binary came from, else the submodule's
    for utils in (exe.parents[2] / "egs" / "wsj" / "s5" / "utils",
                  HERE.parents[2] / "tools" / "kaldi" / "egs" / "wsj" / "s5" / "utils"):
        if (utils / "fix_data_dir.sh").is_file():
            return exe, dur.resolve(), utils
    raise SystemExit("prepare: no Kaldi egs/wsj/s5/utils. Run "
                     "`git submodule update --init tools/kaldi`")


def _dir(flag: str | None, env: str, must: str, what: str) -> Path:
    d = flag or os.environ.get(env)
    if not d or not (Path(d) / must).exists():
        raise SystemExit(f"prepare: {what} not found at {d!r}. Pass --{env.lower()} "
                         f"or set {env} to the directory holding {must}")
    return Path(d).absolute()


def cmd_prepare(args) -> int:
    from fabench.config import load_config
    from fabench.dataprep.datasets import ingest_corpus

    cfg = load_config(args.config)
    out = Path(args.out).absolute()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"prepare: {out} is not empty. Build into a new or empty "
                         "directory, so no stale output is reused")
    conditions = args.conditions.split(",")
    if set(conditions) - set(TYPES):
        raise SystemExit(f"prepare: unknown condition in {args.conditions!r} "
                         f"(choose from {', '.join(TYPES)})")
    corpora = args.corpus.split(",")
    if set(corpora) - set(CORPUS_DIR):
        raise SystemExit(f"prepare: unknown corpus in {args.corpus!r} (timit, buckeye)")
    plan = _plan(cfg, corpora, args.subset.split(",") if args.subset else None)
    roots = {}
    for c in corpora:
        roots[c] = cfg.datasets["gold"][c].get("root")
        if not roots[c] or not Path(roots[c]).is_dir():
            raise SystemExit(f"prepare: no {c} root ({roots[c]!r}). Set "
                             f"FABENCH_{c.upper()}_ROOT (see .fabench.env.example)")
        roots[c] = Path(roots[c]).absolute()
    musan = _dir(args.musan, "MUSAN", "noise", "MUSAN")
    rirs = _dir(args.rirs, "RIRS", "simulated_rirs/smallroom/rir_list", "RIRS_NOISES")
    exe, dur, utils = _kaldi(args)
    for tool in ("ffmpeg", "sox"):
        if not shutil.which(tool):
            raise SystemExit(f"prepare: {tool} is not on PATH")

    out.mkdir(parents=True, exist_ok=True)
    cfg.raw.setdefault("paths", {})["work_dir"] = str(out / "work")
    ref, noisy = out / "ref", out / "noisy"
    ids: dict[str, set[str]] = {c: set() for c in corpora}
    sources: dict[str, list[Path]] = {c: [] for c in corpora}
    for c, s in plan:
        cfg.datasets["gold"][c].update(root=str(roots[c]), subset=s)
        # the canonical gold as `fabench ingest` writes it, whose report of the
        # gold's validation this skips; a corpus that does not parse stops here
        try:
            n = len(ingest_corpus(c, cfg, use_cache=False))
            lines = datadirs.write(ref, c, s, roots[c])
        except (FileNotFoundError, ValueError) as e:
            raise SystemExit(f"prepare: {c} {s}: {e}") from e
        ids[c].update(lines)
        sources[c].extend(lines.values())
        print(f"== {c} {s}: {n} utterances ingested, {len(lines)} wav.scp lines")

    log = out / "make_noisy.log"
    print(f"== building {', '.join(conditions)} (log: {log})")
    env = dict(os.environ, LC_ALL="C", PATH=os.pathsep.join(
        [str(utils), str(exe.parent), str(dur.parent), os.environ.get("PATH", "")]))
    with open(log, "w") as f:
        r = subprocess.run(
            [sys.executable, str(HERE / "make_noisy.py"), "--ref", str(ref),
             "--utils", str(utils), "--musan", str(musan), "--rirs", str(rirs),
             "--out", str(noisy), "--work", str(out / "noisy_work"),
             "--nj", str(args.jobs), "--splits", " ".join(f"{c}_{s}" for c, s in plan),
             "--types", " ".join(conditions)],
            stdout=f, stderr=subprocess.STDOUT, env=env, check=False)
    if r.returncode:
        raise SystemExit(f"prepare: make_noisy.py failed, see {log}")
    for c in corpora:
        for cond in conditions:
            d = noisy / CORPUS_DIR[c] / "noisy" / cond
            gone = sorted(i for i in ids[c] if not (d / f"{i}.wav").is_file())
            if gone:
                raise SystemExit(f"prepare: {c} {cond} is missing {len(gone)} of "
                                 f"{len(ids[c])} files, e.g. {gone[0]}. See {log}")
            print(f"== {c} {cond}: shadow root")
            shadow = out / "shadow" / f"{c}_{cond}"
            (shadow_root.timit if c == "timit" else shadow_root.buckeye)(
                roots[c], d, shadow, only=ids[c], nj=args.jobs)
            cut = sum(1 for _ in shadow.rglob("*.wav"))
            if cut != len(ids[c]):
                raise SystemExit(f"prepare: shadow root {shadow} holds {cut} of "
                                 f"{len(ids[c])} files")

    print("== manifest")
    wavs = sorted(p for sub in ("noisy", "shadow", "work")
                  for p in (out / sub).rglob("*.wav") if not p.is_symlink())
    manifest = {
        "plan": {"corpora": {c: [s for c2, s in plan if c2 == c] for c in corpora},
                 "conditions": conditions},
        "inputs": {
            **{f"{c}_audio": _tree(roots[c], args.jobs, sources[c]) for c in corpora},
            "musan": _tree(musan, args.jobs),
            "rirs": _tree(rirs, args.jobs),
            "kaldi_utils": _tree(utils, args.jobs),
            # this package and the Kaldi steps it vendors, which make the draws
            "noisemix": _tree(HERE, args.jobs, [p for p in HERE.rglob("*")
                                                if p.suffix in (".py", ".sh")
                                                and "test" not in p.parts]),
            "wav-reverberate": _binary(exe),
            "wav-to-duration": _binary(dur),
            "ffmpeg": {"version": _version(["ffmpeg", "-version"]),
                       "sha256": _sha256(Path(shutil.which("ffmpeg")))},
            "sox": {"version": _version(["sox", "--version"]),
                    "sha256": _sha256(Path(shutil.which("sox")))},
            "python": sys.version.split()[0],
        },
        "outputs": _digests(wavs, out, args.jobs),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"prepared {len(wavs)} audio files under {out}\n"
          f"  manifest: {out / 'manifest.json'}\n"
          f"  evaluate: FABENCH_SHADOW={out / 'shadow'} evals/gen_noisy_configs.py ...")
    return 0
