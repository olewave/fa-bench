# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""The headline columns of the October 2026 snapshot, rebuilt from the frozen
October inputs to the last digit.

The inputs are the 1,052 hyp.jsonl behind the October snapshot, their cell
configs, the recipes that name them, and the four gold caches. The hyps carry
the licensed transcripts, so they stay on local disks and every test here skips
when they are absent, which is what public CI sees. To run it, point
FABENCH_REPRO_INPUTS at the frozen archive (.tar.zst) or at a directory it was
extracted into, from the root of this checkout:

    FABENCH_REPRO_INPUTS=/path/to/inputs_202610.tar.zst \\
        FABENCH_PUBLIC_NAMES=/path/to/public_names.json \\
        python -m pytest -m repro tests/repro -s

FABENCH_PUBLIC_NAMES is the map from the recipe names the frozen outputs carry
to the published ones (evals.systems.public_name). It is kept with the frozen
inputs, and the cell checks skip without it.

What it checks, in order.

1. Every input against inputs.json by sha256, the hyps, the cell configs, each
   cascade's upstream transcript and the gold caches. One mismatch fails the
   run and nothing is scored, so an overwritten input cannot hide behind a
   result.
2. The 40 cell units (two tracks, TIMIT dev and core test, Buckeye dev and
   test, five conditions) are rebuilt in a temporary tree with the October
   system list pinned per cell. Discovery would add every system run since.
   Each cell is scored with `fabench score` and `fabench report` from this
   checkout.
3. Each leaderboard.csv must hold exactly the columns of headline_sha256.json,
   in its order, and every row's sha256 must match. The file holds one digest
   per system and mode, of the row the October leaderboard.csv wrote for those
   columns, so the check is exact while the numbers stay off this repository.
   They are published on the leaderboard. The word timestamp columns (wts_*)
   are younger than October, so theirs is the text the 2.0.0 scorer wrote from
   the same inputs. Rows are matched by system and mode, each system under the
   public name evals/systems.py gives it.
4. Where FABENCH_TIMIT_ROOT and FABENCH_BUCKEYE_ROOT are set (in the
   environment or .fabench.env), each gold subset is ingested again and must
   equal its frozen cache in every field but audio_path. No audio is written.

A system whose recipe is withheld from the public tree, or published under
another name, is named in inputs.json by the sha256 of its name. FABENCH_REPRO_JOBS sets how many cells score at
once, 16 or the CPU count by default, whichever is smaller.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "202610"
HEADLINE = json.loads((DATA / "headline_sha256.json").read_text())
PINNED = json.loads((DATA / "inputs.json").read_text())
INPUTS = os.environ.get("FABENCH_REPRO_INPUTS", "")

pytestmark = [
    pytest.mark.repro,
    pytest.mark.skipif(not INPUTS, reason="FABENCH_REPRO_INPUTS unset (frozen October "
                                          "inputs, kept on local disks only)"),
]

#: Runs the CLI from THIS checkout. Another clone's editable install would
#: otherwise be the code under test, with nothing to say so.
BOOT = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
        "import fabench; assert Path(fabench.__file__).resolve().is_relative_to("
        "sys.argv[1]), fabench.__file__; "
        "from fabench.cli import main; sys.exit(main(sys.argv[2:]))")


def _jobs() -> int:
    return int(os.environ.get("FABENCH_REPRO_JOBS") or min(16, os.cpu_count() or 1))


def _fabench() -> None:
    """Import this checkout's fabench in-process, or fail saying why not."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import fabench
    if not Path(fabench.__file__).resolve().is_relative_to(REPO):
        pytest.fail(f"fabench imports from {fabench.__file__}; run "
                    f"`python -m pytest` from {REPO}")


def _sha256(p: Path) -> str:
    if not p.is_file():
        return "missing"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _transcript_hyp(cell_config: Path) -> str | None:
    """The upstream hyp a cascade cell names, read the way the scorer reads it."""
    aligners = (yaml.safe_load(cell_config.read_text()) or {}).get("aligners") or [{}]
    return (aligners[0].get("params") or {}).get("transcript_hyp")


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    src = Path(INPUTS).expanduser()
    if src.is_dir():
        yield src
        return
    if not src.is_file():
        pytest.fail(f"FABENCH_REPRO_INPUTS names nothing on disk: {src}")
    dest = tmp_path_factory.mktemp("inputs")
    subprocess.run(["tar", "--zstd", "-xf", str(src), "-C", str(dest)], check=True)
    yield dest
    shutil.rmtree(dest, ignore_errors=True)       # licensed: never left behind


@pytest.fixture(scope="module")
def checked(inputs):
    """Hash every input against inputs.json and resolve each cell's systems."""
    _fabench()
    from fabench.paths import tool_index

    idx = tool_index(inputs)
    alias = {"sha256:" + hashlib.sha256(n.encode()).hexdigest(): n for n in idx}
    want: dict[Path, str] = {}
    names: dict[str, list[str]] = {}
    bad: list[str] = []

    def expect(p: Path, h: str) -> None:
        if want.setdefault(p, h) != h:
            bad.append(f"{p.relative_to(inputs)}: two different expected hashes")

    for cell, tools in PINNED["cells"].items():
        kind, corpus, subset, cond = cell.split("/")
        for key, w in tools.items():
            name = alias.get(key, key)
            hit = idx.get(name)
            if hit is None or hit[0] != kind:
                bad.append(f"{cell}: no {kind} recipe for {key}")
                continue
            names.setdefault(cell, []).append(name)
            d = hit[1] / "en" / corpus / subset / cond
            expect(d / "hyp.jsonl", w["hyp_sha256"])
            expect(d / "config.yaml", w["cellcfg_sha256"])
            if "upstream_sha256" not in w:
                continue
            up = _transcript_hyp(d / "config.yaml") if (d / "config.yaml").is_file() else None
            if not up or Path(up).is_absolute():
                # an absolute path would be read outside the frozen tree
                bad.append(f"{cell}: {key} transcript_hyp is {up or 'absent'}")
            else:
                expect(inputs / up, w["upstream_sha256"])

    canon = sorted((inputs / "data" / "work" / "canonical").glob("*.jsonl"))
    files = [*want, *canon]
    with ThreadPoolExecutor(_jobs()) as ex:
        got = dict(zip(files, ex.map(_sha256, files)))
    bad += [f"{p.relative_to(inputs)}: sha256 {got[p][:12]}, want {h[:12]}"
            for p, h in want.items() if got[p] != h]
    by_sha = {got[p]: p for p in canon}
    gold = {}
    for split, h in PINNED["gold"].items():
        if h in by_sha:
            gold[split] = by_sha[h]
        else:
            bad.append(f"gold {split}: no cache with sha256 {h[:12]}")
    return {"bad": bad, "idx": idx, "names": names, "gold": gold}


def _compare(cell: str, out: Path) -> list[str]:
    """What differs from headline_sha256.json in one rebuilt cell; empty when it
    reproduces."""
    if not (out / "leaderboard.csv").is_file():
        return ["no leaderboard.csv"]
    rows = list(csv.reader((out / "leaderboard.csv").open(newline="")))
    if not rows:
        return ["empty leaderboard.csv"]
    if rows[0] != HEADLINE["columns"]:
        extra = [c for c in rows[0] if c not in HEADLINE["columns"]]
        return [(f"columns differ from headline_sha256.json, {len(extra)} extra, "
                 f"e.g. {extra[:3]}")]
    from evals.systems import public_name

    # The frozen hyps carry the recipe names they were scored under, and a
    # published row goes by its public one.
    a, m = rows[0].index("aligner"), rows[0].index("mode")
    got = {}
    for r in rows[1:]:
        r[a] = public_name(r[a])
        got[f"{r[a]}/{r[m]}"] = hashlib.sha256(
            json.dumps(r, ensure_ascii=False).encode()).hexdigest()
    want = HEADLINE["cells"][cell]
    if set(got) != set(want):
        return [(f"systems differ from headline_sha256.json, "
                 f"{sorted(set(got) ^ set(want))[:3]}")]
    bad = sorted(k for k in want if got[k] != want[k])
    return [f"{len(bad)} rows differ from headline_sha256.json, e.g. {bad[:3]}"] if bad else []


def _score(tree: Path, cell: str, env: dict) -> dict:
    kind, corpus, subset, cond = cell.split("/")
    cfg = tree / "configs" / f"{kind}_{corpus}_{subset}_{cond}.yaml"
    t0 = time.monotonic()
    errors = []
    try:        # one cell's surprise is that cell's failure, not the whole pool's
        for cmd in ("score", "report"):
            r = subprocess.run([sys.executable, "-I", "-c", BOOT, str(REPO), cmd,
                                "--config", str(cfg)],
                               cwd=tree, env=env, capture_output=True, text=True, check=False)
            if r.returncode:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                errors.append(f"fabench {cmd} exited {r.returncode}: " + " | ".join(tail))
                break
        if not errors:
            errors = _compare(cell, tree / "summary" / kind / "en" / corpus / subset / cond)
    except Exception as e:
        errors.append(f"{type(e).__name__}: {e}")
    secs = time.monotonic() - t0
    print(f"  {cell:36s} {secs:7.1f} s  {'ok' if not errors else 'FAIL'}", flush=True)
    return {"seconds": secs, "errors": errors}


@pytest.fixture(scope="module")
def rebuilt(inputs, checked, tmp_path_factory):
    """Score all 40 cells into <tmp>/summary, from the pinned systems only."""
    if checked["bad"]:
        pytest.fail("inputs differ from inputs.json, so nothing was scored "
                    "(see test_inputs_match_inputs_json)")
    from fabench.config import load_config
    from fabench.dataprep.datasets import _gold_spec, _variant_tag, canonical_path
    from fabench.paths import languages_dir

    idx, gold = checked["idx"], checked["gold"]
    tree = tmp_path_factory.mktemp("tree")
    # repo_root() is the first directory holding fabench/ and evals/. This
    # fabench/ stays empty, so the code can only come from REPO (see BOOT).
    (tree / "fabench").mkdir()
    shutil.copytree(inputs / "evals", tree / "evals", copy_function=os.symlink)
    (tree / "configs").mkdir()
    (tree / "empty.env").write_text("")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FABENCH_")}
    env.update(FABENCH_ENV_FILE=str(tree / "empty.env"), OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")

    # One corpus per cell, every other one stated disabled, as gen_config.py
    # does. The gold root is a placeholder: the scorer reads the frozen cache,
    # which is placed under the name this checkout derives for that root.
    corpora = sorted({p.parent.name for p in languages_dir(REPO).glob("*/*/config.yaml")})
    size = {}
    for cell, names in checked["names"].items():
        kind, corpus, subset, cond = cell.split("/")
        cfg = {
            "datasets": {"gold": {c: ({"enabled": True, "root": str(tree / "gold" / corpus),
                                       "subset": subset} if c == corpus
                                      else {"enabled": False}) for c in corpora}},
            "conditions": {"noise_types": [], "snr_db": [], "include_clean": True},
            "aligners": [dict(yaml.safe_load((idx[n][1] / "config.yaml").read_text()),
                              enabled=True) for n in sorted(names)],
            "paths": {"results_dir": str(tree / "summary" / kind / "en" / corpus
                                         / subset / cond),
                      "work_dir": str(tree / "work")},
        }
        if cond != "origin":
            cfg["condition_tag"] = cond
        path = tree / "configs" / f"{kind}_{corpus}_{subset}_{cond}.yaml"
        path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        c = load_config(path)
        cache = canonical_path(c, corpus, _variant_tag(corpus, _gold_spec(c, corpus)))
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.symlink_to(gold[f"{corpus}/{subset}"])
        size[cell] = sum((idx[n][1] / "en" / corpus / subset / cond / "hyp.jsonl")
                         .stat().st_size for n in names)

    order = sorted(size, key=size.get, reverse=True)      # longest first
    t0 = time.monotonic()
    print(f"\n  scoring {len(order)} cells, {_jobs()} at a time", flush=True)
    with ThreadPoolExecutor(_jobs()) as ex:
        cells = dict(zip(order, ex.map(lambda c: _score(tree, c, env), order)))
    print(f"  all cells scored in {time.monotonic() - t0:.1f} s", flush=True)
    yield {"tree": tree, "env": env, "cells": cells}
    shutil.rmtree(tree, ignore_errors=True)


def test_inputs_match_inputs_json(checked):
    bad = checked["bad"]
    assert not bad, f"{len(bad)} inputs differ from inputs.json:\n" + "\n".join(bad[:40])


@pytest.mark.skipif(not os.environ.get("FABENCH_PUBLIC_NAMES"),
                    reason="FABENCH_PUBLIC_NAMES unset (kept with the frozen inputs)")
@pytest.mark.parametrize("cell", sorted(HEADLINE["cells"]))
def test_cell_reproduces_october(cell, rebuilt):
    errors = rebuilt["cells"][cell]["errors"]
    assert not errors, f"{cell}: " + "; ".join(errors)


@pytest.mark.parametrize("split", sorted(PINNED["gold"]))
def test_gold_reingests_to_its_frozen_cache(split, checked, tmp_path, monkeypatch):
    corpus, subset = split.split("/")
    _fabench()
    import fabench.audio
    from fabench.config import corpus_root_env, load_config
    from fabench.dataprep.datasets import _gold_spec, _variant_tag, canonical_path, ingest_corpus
    from fabench.envfile import find_env_file, parse_env_file

    var = corpus_root_env(corpus)
    envf = find_env_file()
    root = os.environ.get(var) or (parse_env_file(envf).get(var) if envf else None)
    if not root:
        pytest.skip(f"{var} unset, so {corpus} cannot be ingested again")
    if split not in checked["gold"]:
        pytest.fail(f"no frozen gold for {split} (see test_inputs_match_inputs_json)")
    monkeypatch.setattr(fabench.audio, "write_audio", lambda *a, **k: None)
    path = tmp_path / "ingest.yaml"
    path.write_text(yaml.safe_dump({
        "datasets": {"gold": {corpus: {"enabled": True, "root": root, "subset": subset}}},
        "paths": {"work_dir": str(tmp_path / "work")}}))
    cfg = load_config(path)
    try:
        ingest_corpus(corpus, cfg, use_cache=False)       # writes the cache, same dumper
        new = canonical_path(cfg, corpus, _variant_tag(corpus, _gold_spec(cfg, corpus)))
        fresh = [json.loads(line) for line in new.open()]
    finally:
        shutil.rmtree(tmp_path / "work", ignore_errors=True)
    frozen = [json.loads(line) for line in checked["gold"][split].open()]
    assert [u["utt_id"] for u in fresh] == [u["utt_id"] for u in frozen], \
        f"{split}: {len(fresh)} utterances ingested, {len(frozen)} frozen, or another order"
    differ = [a["utt_id"] for a, b in zip(fresh, frozen)
              if {**a, "audio_path": None} != {**b, "audio_path": None}]
    assert not differ, (f"{split}: {len(differ)} of {len(frozen)} utterances differ "
                        f"beyond audio_path, first {differ[:3]}")
