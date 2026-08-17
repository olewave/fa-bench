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

"""gate#9: a noisy alignment must not reproduce its clean counterpart.

The bug this gate exists for produced no error of any kind -- exit 0, hyp files
written, reports generated -- and showed up only as a published row whose MAE
was identical under clean and all four noise conditions. So the gate itself is
worth testing: a check that silently passes is exactly the failure it guards
against.
"""
from __future__ import annotations

import json

from fabench.gates import _gate_noisy_differs_from_clean, _gate_phone_tier_covers_reference

CONDS = ("reverb", "noise", "music", "babble")


def _cell(root, tool, corpus, subset, cond, shift=0.0, n=250):
    """Write a hyp.jsonl. shift=0 reproduces the clean alignment exactly."""
    d = root / "evals" / "aligners" / tool / "en" / corpus / subset / cond
    d.mkdir(parents=True, exist_ok=True)
    with (d / "hyp.jsonl").open("w") as f:
        for i in range(n):
            rec = {"item_id": f"u{i}", "aligner": tool,
                   "phones": [{"label": "a", "start": i + shift,
                               "end": i + 0.5 + shift}]}
            f.write(json.dumps(rec) + "\n")
    return d


def test_passes_when_every_condition_differs(tmp_path):
    _cell(tmp_path, "t", "buckeye", "dev", "origin")
    for k, c in enumerate(CONDS, start=1):
        _cell(tmp_path, "t", "buckeye", "dev", c, shift=0.01 * k)
    _name, status, detail = _gate_noisy_differs_from_clean(tmp_path)
    assert status == "PASS", detail
    assert "4 noisy cells" in detail


def test_fails_when_a_condition_reproduces_clean(tmp_path):
    _cell(tmp_path, "t", "buckeye", "dev", "origin")
    _cell(tmp_path, "t", "buckeye", "dev", "reverb", shift=0.01)
    _cell(tmp_path, "t", "buckeye", "dev", "babble", shift=0.0)   # the bug
    _name, status, detail = _gate_noisy_differs_from_clean(tmp_path)
    assert status == "FAIL", detail
    assert "babble" in detail and "100%" in detail
    assert "reverb" not in detail          # the healthy cell is not implicated


def test_fails_when_two_conditions_share_one_alignment(tmp_path):
    """The subtler corruption: both cells differ from clean, so the clean check
    passes them both, while one condition's numbers appear under two headings.
    An unkeyed mix manifest let concurrent runs race exactly this way."""
    _cell(tmp_path, "t", "buckeye", "dev", "origin")
    _cell(tmp_path, "t", "buckeye", "dev", "reverb", shift=0.4)
    _cell(tmp_path, "t", "buckeye", "dev", "noise", shift=0.4)   # same as reverb
    _cell(tmp_path, "t", "buckeye", "dev", "music", shift=0.9)
    _name, status, detail = _gate_noisy_differs_from_clean(tmp_path)
    assert status == "FAIL", detail
    assert "share one alignment" in detail
    assert "music" not in detail.split("share one alignment")[1]


def test_passes_on_a_tree_with_no_noisy_cells(tmp_path):
    """A fresh clone has nothing to contradict -- that must not read as FAIL."""
    _cell(tmp_path, "t", "buckeye", "dev", "origin")
    _name, status, detail = _gate_noisy_differs_from_clean(tmp_path)
    assert status == "PASS"
    assert "no noisy cells" in detail


def test_partial_overlap_below_threshold_passes(tmp_path):
    """Real cells share some utterances -- silence-heavy ones align the same
    under noise. Measured, genuine cells peak near 33%; only total identity is
    the failure. A cell that matches on a third of its utterances must pass."""
    origin = _cell(tmp_path, "t", "buckeye", "dev", "origin", n=300)
    d = tmp_path / "evals" / "aligners" / "t" / "en" / "buckeye" / "dev" / "noise"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "hyp.jsonl").open("w") as f:
        for i in range(300):
            shift = 0.0 if i % 3 == 0 else 0.7        # a third identical
            rec = {"item_id": f"u{i}", "aligner": "t",
                   "phones": [{"label": "a", "start": i + shift,
                               "end": i + 0.5 + shift}]}
            f.write(json.dumps(rec) + "\n")
    assert origin.exists()
    _name, status, detail = _gate_noisy_differs_from_clean(tmp_path)
    assert status == "PASS", detail


# --- gate#10: a phone tier must cover most of the reference sequence --------
#
# torchaudio_fa aligned 39% of it for all of v1 without complaint: its worker
# keeps only phones present in the phoneme model's vocabulary, that model speaks
# eSpeak IPA, the reference arrives in ARPABET, and every vowel was dropped
# before alignment. Nothing raised. The tier scored on 17 consonants and looked
# competitive, because MAE only ever sees what survived.

def _gold(root, corpus, n=250, phones=10):
    d = root / "data" / "work" / "canonical"
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{corpus}__dev__rtest.jsonl").open("w") as f:
        for i in range(n):
            f.write(json.dumps({
                "utt_id": f"u{i}",
                "phones": [{"label": "a", "start": j, "end": j + 1}
                           for j in range(phones)]}) + "\n")


def _hyp_phones(root, tool, corpus, phones, n=250):
    d = root / "evals" / "aligners" / tool / "en" / corpus / "dev" / "origin"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "hyp.jsonl").open("w") as f:
        for i in range(n):
            f.write(json.dumps({
                "item_id": f"u{i}__clean", "utt_id": f"u{i}", "aligner": tool,
                "phones": [{"label": "a", "start": j, "end": j + 1}
                           for j in range(phones)]}) + "\n")


def test_phone_coverage_passes_at_realistic_shortfall(tmp_path):
    # the healthy systems sit at 84-91% of gold: aligners do not reproduce
    # TIMIT's closures, and folding merges a few units. That must not fail.
    _gold(tmp_path, "timit", phones=10)
    _hyp_phones(tmp_path, "healthy", "timit", phones=9)   # 90%
    _name, status, detail = _gate_phone_tier_covers_reference(tmp_path)
    assert status == "PASS", detail


def test_phone_coverage_fails_when_vowels_are_dropped(tmp_path):
    # the observed failure: 39% of the reference, vowels filtered out upstream
    _gold(tmp_path, "timit", phones=10)
    _hyp_phones(tmp_path, "mismatched", "timit", phones=4)   # 40%
    _name, status, detail = _gate_phone_tier_covers_reference(tmp_path)
    assert status == "FAIL"
    assert "mismatched" in detail


def test_phone_coverage_ignores_word_only_systems(tmp_path):
    # a system with no phone tier is legitimate and must not be flagged;
    # only a PARTIAL tier is the defect.
    _gold(tmp_path, "timit", phones=10)
    d = tmp_path / "evals/aligners/wordonly/en/timit/dev/origin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "hyp.jsonl").write_text(json.dumps(
        {"item_id": "u0__clean", "utt_id": "u0", "aligner": "wordonly",
         "phones": [], "words": [{"label": "hi", "start": 0, "end": 1}]}) + "\n")
    _name, status, detail = _gate_phone_tier_covers_reference(tmp_path)
    assert status == "PASS", detail
