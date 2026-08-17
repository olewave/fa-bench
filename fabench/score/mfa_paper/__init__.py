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

"""``mfa_paper`` scoring protocol: bridges to MFA's own real evaluation code
(``kalpy.evaluation.align_phones``) plus a Python port of the MFA-2026 paper's
benchmark-repo second-stage manner-category filter (``data_prep.R``), so FA-Bench
can reproduce Table 5 (arXiv:2606.18466) exactly rather than approximating the
paper's protocol from prose. Opt in via ``scoring.protocol: mfa_paper`` — the
default ``scoring.protocol: fabench`` is completely unaffected.

See the plan/session notes for the verified mechanics: insertion/deletion-adjacent
boundary drop, the 10x silence-substitution cost, and why ``custom_mapping``
(closure merging) is load-bearing for TIMIT/Buckeye stop closures.
"""

from __future__ import annotations

from fabench.score.mfa_paper.cell import score_cell

__all__ = ["score_cell"]
