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

"""Vendored MFA-2026 benchmark-repo mapping YAMLs load to the expected shape
(mfa_paper protocol) — locks the vendored files + loader against silent drift."""

from fabench.score.mfa_paper.mapping import load_mapping, mapping_path


def test_mapping_path_defaults_to_vendored_dir():
    p = mapping_path("arpa", "timit")
    assert p.name == "arpa_timit_mapping.yaml"
    assert p.parent.name == "mapping_files"
    assert p.exists()


def test_mapping_path_honors_override_dir(tmp_path):
    p = mapping_path("arpa", "timit", mapping_dir=str(tmp_path))
    assert p == tmp_path / "arpa_timit_mapping.yaml"


def test_arpa_timit_mapping_list_values():
    m = load_mapping(mapping_path("arpa", "timit"))
    # closure-compound keys, needed for fix_many_to_one_alignments to merge
    # e.g. TIMIT's separate bcl+b into the single ARPABET "B".
    assert m["B"] == {"b", "bcl", "bcl b"}
    assert m["T"] == {"t", "q", "dx", "tcl", "tcl t", "tcl q"}
    # the ARPABET rhotic mapped against TIMIT's r/er/axr family
    assert m["R"] == {"er", "ern", "r"}


def test_arpa_timit_mapping_scalar_value_becomes_singleton_set():
    m = load_mapping(mapping_path("arpa", "timit"))
    # "TH: th" (a bare scalar in the YAML) must coerce to a singleton set, not a
    # length-2 set of characters {"t","h"} (a classic str-vs-iterable bug).
    assert m["TH"] == {"th"}
    assert m["DH"] == {"dh"}


def test_all_four_aligner_families_have_both_corpora():
    for family in ("arpa", "charsiu", "maps", "bournemouth"):
        for corpus in ("timit", "buckeye"):
            assert mapping_path(family, corpus).exists(), f"{family}_{corpus}_mapping.yaml missing"
