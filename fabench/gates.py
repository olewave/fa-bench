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

"""`fabench gates` (Plan Section 7): run every data-independent sanity gate and
report pass/fail.

Gates needing restricted corpora (gold plausibility on TIMIT/Buckeye) are marked
DATA-GATED and run only via `fabench ingest` once the corpora are staged. The
rest are provable here and now.
"""

from __future__ import annotations

from pathlib import Path


def cmd_gates(args) -> int:
    out = Path(args.out)
    results: list[tuple[str, str, str]] = []  # (gate, status, detail)

    # 1,3,6-mix,8 + all metric/aggregate gates via the synthetic E2E
    from fabench.selftest import check, run_selftest

    lb, pt, mr = run_selftest(out / "selftest")
    for name, ok, detail in check(lb, pt, mr):
        results.append((name, "PASS" if ok else "FAIL", detail))

    # gate #4: metric unit tests (invoke a focused pytest subset)
    results.append(_run_pytest("fabench/score/test/test_scoring.py fabench/score/test/test_matched.py fabench/score/test/test_aggregate.py",
                               "gate#4 metric unit tests"))
    # gate #1/#3 mixing gates (unit)
    results.append(_run_pytest("fabench/noise/test/test_noise.py", "gate#1/#3 timing+SNR"))
    # gate #7: excluded-gold guard
    results.append(_run_pytest("fabench/dataprep/datasets/test/test_ingest.py::test_excluded_gold_root_aborts "
                               "fabench/dataprep/datasets/test/test_ingest.py::test_ingest_not_staged_fails_loud",
                               "gate#7 excluded-gold + fail-loud"))
    # gate #5: Mode B 1:1 / ARR==1 by construction
    results.append(_run_pytest("fabench/score/test/test_matched.py::test_identical_sequences_all_match",
                               "gate#5 Mode-B 1:1 ARR==1"))
    # gate #9: no noisy cell may reproduce its clean alignment. Inspects the
    # alignments actually on disk rather than a synthetic fixture, because the
    # failure it catches is a SWEEP failure -- everything upstream of the
    # numbers was correct, and only the numbers were wrong.
    results.append(_gate_noisy_differs_from_clean(Path(__file__).resolve().parents[1]))
    results.append(_gate_phone_tier_covers_reference(Path(__file__).resolve().parents[1]))

    print("\n=== fabench sanity gates (Plan 7) ===")
    allok = True
    for name, status, detail in results:
        allok &= status == "PASS"
        print(f"  [{status}] {name:42s} {detail}")
    print("  [DATA-GATED] gate#2 gold plausibility (TIMIT/Buckeye) — run via "
          "`fabench ingest` once staged")
    print(f"  {'ALL PASS' if allok else 'FAILURES PRESENT'}")
    return 0 if allok else 1


#: Utterances sampled per cell. The failure mode is TOTAL -- a corrupted cell
#: matches clean on every utterance -- so a sample separates it from a real
#: result immediately. Measured over the published sweep, genuine noisy cells
#: peak at 33% identical while corrupted ones sit at exactly 100%: the
#: threshold lives in an empty band, not near a real value.
_NOISY_SAMPLE = 200
_NOISY_MAX_IDENTICAL = 90



#: A hypothesis phone tier must cover most of the reference sequence.
#:
#: torchaudio_fa aligned 39% of it for the whole of v1 and nothing complained.
#: Its worker keeps only phones present in the phoneme model's vocabulary --
#: that model speaks eSpeak IPA, the reference arrives in ARPABET, so every
#: vowel was filtered out silently and the tier was scored on 17 consonants.
#: Measured on TIMIT dev the five healthy systems cover 84-91% of gold; the
#: threshold sits well below that band and well above the failure.
#:
#: This is a UNITS-MISMATCH gate, not a torchaudio gate. Any adapter handed
#: labels in an alphabet its model does not share will land here.
_COVERAGE_MIN_PCT = 65


def _gate_phone_tier_covers_reference(root: Path) -> tuple[str, str, str]:
    """gate#10: a phone tier scored on a fraction of the reference is not a
    coarser measurement, it is a different one -- and it flatters whoever drops
    the hard units, because MAE only ever sees what survived."""
    import json

    label = "gate#10 phone tier covers the reference"
    gold_dir = root / "data" / "work" / "canonical"
    if not gold_dir.is_dir():
        return (label, "PASS", "no canonical gold staged — nothing to compare")

    gold: dict[str, dict[str, int]] = {}
    for f in sorted(gold_dir.glob("*.jsonl")):
        corpus = f.name.split("__")[0]
        per = gold.setdefault(corpus, {})
        for i, line in enumerate(f.open()):
            if i >= 400:
                break
            r = json.loads(line)
            n = len(r.get("phones") or [])
            if n:
                per[r["utt_id"]] = n

    bad, checked = [], 0
    for hyp in sorted(root.glob("evals/aligners/*/en/*/*/origin/hyp.jsonl")):
        tool = hyp.parents[4].name
        corpus = hyp.parents[2].name
        ref = gold.get(corpus)
        if not ref:
            continue
        hn = rn = 0
        for i, line in enumerate(hyp.open()):
            if i >= 400:
                break
            r = json.loads(line)
            ph = r.get("phones") or []
            if not ph:
                continue
            hn += len(ph)
            rn += ref.get(r["utt_id"], 0)
        if not hn or not rn:
            continue          # no phone tier at all is legitimate; partial is not
        checked += 1
        pct = hn * 100 // rn
        if pct < _COVERAGE_MIN_PCT:
            bad.append(f"{tool} {corpus} ({pct}% of reference)")

    if not checked:
        return (label, "PASS", "no phone tiers on disk")
    if bad:
        return (label, "FAIL",
                f"{len(bad)}/{checked} cover <{_COVERAGE_MIN_PCT}% of the "
                "reference phone sequence: " + "; ".join(bad[:4])
                + (" …" if len(bad) > 4 else ""))
    return (label, "PASS",
            f"{checked} phone tiers each cover >={_COVERAGE_MIN_PCT}% of gold")

def _gate_noisy_differs_from_clean(root: Path) -> tuple[str, str, str]:
    """gate#9: a noisy alignment must not reproduce its clean counterpart.

    WHY THIS EXISTS. Between 2026-08-11 and 08-12, ten buckeye/dev cells were
    aligned against clean audio and written under noise labels. Config, shadow
    root and audio were all correct; the aligner simply never saw the noisy
    files. Nothing failed: exit codes were 0, hyp files were written, reports
    were generated, and the published noise tables showed BFA and Charsiu with
    the SAME MAE under clean and all four conditions for four days. The number
    that gave it away -- a row flat across five columns -- is exactly what this
    gate checks, and it is cheap enough to check every time.

    Data-independent in the sense that matters here: it needs no corpus, only
    whatever alignments happen to be on disk. A fresh clone has none and the
    gate passes trivially, which is honest -- there is nothing to contradict.
    """
    import json

    def sample(f: Path) -> dict:
        d = {}
        try:
            with f.open() as fh:
                for i, line in enumerate(fh):
                    if i >= _NOISY_SAMPLE:
                        break
                    r = json.loads(line)
                    k = "phones" if r.get("phones") else "words"
                    d[r["item_id"]] = tuple((s.get("start"), s.get("end"))
                                            for s in (r.get(k) or []))
        except (OSError, ValueError):
            return {}
        return d

    bad, checked = [], 0
    dupes: list[str] = []
    for origin in sorted((root / "evals").glob("*/*/en/*/*/origin/hyp.jsonl")):
        clean = sample(origin)
        if not clean:
            continue
        # Two CONDITIONS holding one alignment. Distinct from the clean check
        # above and invisible to it: both cells differ from clean, so both
        # pass, while one condition's numbers appear under two headings. That
        # is not hypothetical -- an unkeyed mix manifest let concurrent runs
        # race, and seven cells ended up sharing three alignments.
        # Compared by THRESHOLD, not equality. A byte-exact test misses the
        # real thing: crisperwhisper_fa held music and noise agreeing on 399 of
        # 400 utterances, and the single differing utterance was enough to make
        # them look distinct. Corruption need not be byte-perfect.
        by_cond: dict[str, dict] = {}
        for cond in sorted(p.name for p in origin.parent.parent.iterdir() if p.is_dir()):
            if cond == origin.parent.name:
                continue
            f = origin.parent.parent / cond / "hyp.jsonl"
            if f.is_file():
                s = sample(f)
                if s:
                    by_cond[cond] = s
        conds = sorted(by_cond)
        for i, a in enumerate(conds):
            for b in conds[i + 1:]:
                A, B = by_cond[a], by_cond[b]
                same = sum(1 for k in A if B.get(k) == A[k])
                pct = same * 100 // max(len(A), 1)
                if pct >= _NOISY_MAX_IDENTICAL:
                    sub = origin.parent.parent
                    dupes.append(f"{sub.parent.name}/{sub.name}: {a}=={b} ({pct}%)")
        tool = str(origin).split("/en/")[0].rsplit("/", 1)[-1]
        # origin/hyp.jsonl -> .../<corpus>/<subset>/origin/hyp.jsonl, so the
        # SUBSET directory is two up, and the conditions are its children.
        subset_dir = origin.parent.parent
        for cond in sorted(p.name for p in subset_dir.iterdir() if p.is_dir()):
            if cond == origin.parent.name:
                continue
            f = subset_dir / cond / "hyp.jsonl"
            if not f.is_file():
                continue
            noisy = sample(f)
            if not noisy:
                continue
            checked += 1
            same = sum(1 for k in clean if noisy.get(k) == clean[k])
            pct = same * 100 // max(len(clean), 1)
            if pct >= _NOISY_MAX_IDENTICAL:
                bad.append(f"{tool} {subset_dir.parent.name}/{subset_dir.name}"
                           f"/{cond} ({pct}%)")
    label = "gate#9 noisy alignments distinct"
    if not checked:
        return (label, "PASS", "no noisy cells on disk — nothing to contradict")
    if bad:
        return (label, "FAIL",
                f"{len(bad)}/{checked} reproduce the clean alignment: "
                + "; ".join(bad[:4]) + (" …" if len(bad) > 4 else ""))
    if dupes:
        return (label, "FAIL",
                f"{len(dupes)} condition pair(s) share one alignment: "
                + "; ".join(dupes[:4]) + (" …" if len(dupes) > 4 else ""))
    return (label, "PASS",
            f"{checked} noisy cells differ from clean and from each other")


def _run_pytest(target: str, label: str) -> tuple[str, str, str]:
    import subprocess
    import sys

    # sys.executable, not a bare "python": the gates must run under the same
    # interpreter fabench itself is running in. Resolving "python" off PATH picks
    # up whatever system Python happens to come first, whose pytest may be
    # missing or (as on this host) broken by an unrelated dependency clash — the
    # gates then report FAIL for environment reasons while `pytest -q` in the
    # project venv is entirely green, which is a badly misleading signal.
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", *target.split()],
        capture_output=True, text=True,
    check=False)
    if "No module named pytest" in r.stderr:
        # A fresh core-only install: four gates need it. Say what to run, not
        # just which import failed.
        return (label, "FAIL", 'pytest not installed — uv pip install -e ".[test]"')
    ok = r.returncode == 0
    last = [ln for ln in r.stdout.splitlines() if ln.strip()]
    detail = last[-1] if last else ""
    if not ok and not detail:
        detail = (r.stderr.strip().splitlines() or ["(no output)"])[-1]
    return (label, "PASS" if ok else "FAIL", detail)
