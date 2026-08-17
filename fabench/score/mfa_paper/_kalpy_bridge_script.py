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

"""Self-contained bridge script — runs under the ``mfa`` (3.4) micromamba env's
Python, which has a working ``kalpy.evaluation`` (``mfa30``'s does not — it ships
a stale ``kalpy-kaldi==0.0.0`` with no ``.evaluation`` submodule, verified). Stdlib
+ ``kalpy`` only: this process is a *different* interpreter from FA-Bench's own
venv, so it must not import anything from ``fabench``.

Protocol: read one JSON object from stdin, write one JSON object to stdout.

Input::

    {"silence_phones": ["sil"],
     "custom_mapping": {"B": ["b", "bcl", "bcl b"], ...},
     "utterances": [
       {"utt_id": "...",
        "ref":  [{"label": "sil", "begin": 0.0, "end": 0.24}, ...],
        "test": [{"label": "sil", "begin": 0.0, "end": 0.25}, ...]},
       ...
     ]}

Output, keyed by ``utt_id``::

    {"<utt_id>": {"boundary_errors": [...], "score": ..., "phone_error_rate": ...,
                  "num_insertions": ..., "num_deletions": ..., "num_matched_pairs": ...,
                  "alignment_path": [{"ref_label":..., "ref_begin":..., "ref_end":...,
                                       "test_label":..., "test_begin":..., "test_end":...}, ...]}}

``alignment_path`` is the *full* DP alignment (including insertion/deletion steps,
where the missing side's label is ``"-"`` and its begin/end are ``null``) — kalpy's
``boundary_errors`` already drops (a) any boundary right after an insertion or
deletion, and (b) the very first boundary of the utterance (its loop only appends
when ``i != 0``). ``alignment_path`` is returned so FA-Bench can optionally
*reconstruct* those excluded boundaries for ablation (see
``fabench/score/mfa_paper/cell.py::extract_boundary_errors``), rather than only
ever seeing kalpy's own always-excluded default.

A per-utterance failure is reported as ``{"<utt_id>": {"error": "..."}}`` rather
than aborting the whole batch (one bad utterance in a 6,300/22,458-utterance cell
should not lose everything else).
"""

from __future__ import annotations

import json
import sys

from kalpy.evaluation import align_phones
from kalpy.gmm.data import CtmInterval


def _to_ctm(intervals: list[dict]) -> list[CtmInterval]:
    return [CtmInterval(iv["begin"], iv["end"], iv["label"]) for iv in intervals]


def main() -> None:
    payload = json.load(sys.stdin)
    base_silence_phones = set(payload["silence_phones"])
    custom_mapping = {k: set(v) for k, v in payload.get("custom_mapping", {}).items()}

    out: dict[str, dict] = {}
    for utt in payload["utterances"]:
        utt_id = utt["utt_id"]
        try:
            ref = _to_ctm(utt["ref"])
            test = _to_ctm(utt["test"])
            # align_phones mutates its silence_phones set in place (adding any
            # custom_mapping keys/values that intersect it) — pass a fresh copy
            # per utterance so calls don't leak state into each other across the
            # batch depending on iteration order.
            score, per, _errors, alignment, boundary_errors = align_phones(
                ref, test,
                silence_phones=set(base_silence_phones),
                custom_mapping=custom_mapping,
            )
            n_ins = sum(1 for sa, sb in alignment.alignment if sa.label == "-")
            n_del = sum(1 for sa, sb in alignment.alignment if sb.label == "-")
            n_matched_pairs = sum(
                1 for sa, sb in alignment.alignment if sa.label != "-" and sb.label != "-"
            )
            alignment_path = [
                {
                    "ref_label": sa.label,
                    "ref_begin": None if sa.label == "-" else round(sa.begin, 3),
                    "ref_end": None if sa.label == "-" else round(sa.end, 3),
                    "test_label": sb.label,
                    "test_begin": None if sb.label == "-" else round(sb.begin, 3),
                    "test_end": None if sb.label == "-" else round(sb.end, 3),
                }
                for sa, sb in alignment.alignment
            ]
            out[utt_id] = {
                "boundary_errors": boundary_errors,
                "score": score,
                "phone_error_rate": per,
                "num_insertions": n_ins,
                "num_deletions": n_del,
                "num_matched_pairs": n_matched_pairs,
                "alignment_path": alignment_path,
            }
        except Exception as e:
            out[utt_id] = {"error": f"{type(e).__name__}: {e}"}

    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
