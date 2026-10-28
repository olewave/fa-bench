# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0

"""S6 end-to-end: synthetic oracle-corpus selftest checks run in CI."""

from fabench.selftest import check, run_selftest


def test_selftest_all_checks_pass(tmp_path):
    lb, mr = run_selftest(tmp_path / "st", seed=20240607)
    results = check(lb, mr)
    failed = [(n, d) for (n, ok, d) in results if not ok]
    assert not failed, f"selftest checks failed: {failed}"


def test_selftest_deterministic(tmp_path):
    from fabench.selftest import _identical_metrics

    lb1, _ = run_selftest(tmp_path / "a", seed=42)
    lb2, _ = run_selftest(tmp_path / "b", seed=42)
    assert _identical_metrics(lb1, lb2)


def test_report_renders(tmp_path):
    from fabench.report.runner import build_report

    lb, _ = run_selftest(tmp_path / "st", seed=1)
    md = build_report(lb)
    assert md.startswith("# FA-Bench report") and "## synthetic, clean" in md
    assert "| oracle_const10 | B | 1.000 | 10.0 |" in md
