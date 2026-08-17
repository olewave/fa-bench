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

"""S6 end-to-end: synthetic oracle-corpus selftest checks run in CI."""

from fabench.selftest import check, run_selftest


def test_selftest_all_checks_pass(tmp_path):
    lb, pt, mr = run_selftest(tmp_path / "st", seed=20240607)
    results = check(lb, pt, mr)
    failed = [(n, d) for (n, ok, d) in results if not ok]
    assert not failed, f"selftest checks failed: {failed}"


def test_selftest_deterministic(tmp_path):
    from fabench.selftest import _identical_metrics

    lb1, _, _ = run_selftest(tmp_path / "a", seed=42)
    lb2, _, _ = run_selftest(tmp_path / "b", seed=42)
    assert _identical_metrics(lb1, lb2)


def test_report_renders(tmp_path):
    from fabench.report.runner import build_report

    lb, pt, _ = run_selftest(tmp_path / "st", seed=1)
    md = build_report(lb, pt, cfg=None)
    assert "Leaderboard" in md and "Degradation" in md
    assert "oracle_const10" in md
