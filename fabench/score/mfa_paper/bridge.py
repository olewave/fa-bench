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

"""Subprocess bridge to ``kalpy.evaluation.align_phones``, running in the ``mfa``
(3.4) micromamba env — the only one with a working ``kalpy.evaluation`` (``mfa30``
ships a stale ``kalpy-kaldi==0.0.0`` lacking the ``.evaluation`` submodule entirely,
verified directly). Mirrors :mod:`fabench.aligners.mfa`'s micromamba-invocation
pattern (``_DEFAULT_MM``/``_DEFAULT_ROOT``, ``MAMBA_ROOT_PREFIX`` env var).

``kalpy-kaldi`` ships no prebuilt wheel on PyPI (sdist only, confirmed via the
PyPI JSON API) — installing it in-process into FA-Bench's own uv venv would mean
compiling a Kaldi-derived C++ extension from source. Bridging to the already-
working ``mfa`` env avoids that risk entirely.

Batches **one subprocess per (corpus, aligner) cell**, not per utterance:
``align_phones`` has no model-loading cost (unlike ``mfa align``'s ~40-60s Kaldi
startup), so per-utterance subprocesses would be pure overhead across TIMIT's
6,300 / paper-segmented Buckeye's 22,458 utterances.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from fabench.schema import Interval

# Machine-specific; override via env (same convention as the MFA adapter).
_DEFAULT_MM = os.environ.get(
    "FABENCH_MICROMAMBA", str(Path.home() / "micromamba" / "bin" / "micromamba"))
_DEFAULT_ROOT = os.environ.get("FABENCH_MAMBA_ROOT", str(Path.home() / "micromamba"))
_BRIDGE_SCRIPT = Path(__file__).with_name("_kalpy_bridge_script.py")


class BridgeError(RuntimeError):
    """Raised when the kalpy subprocess bridge fails to run or returns garbage."""


def batch_align_phones(
    utterances: Sequence[tuple[str, list[Interval], list[Interval]]],
    *,
    silence_phones: set[str],
    custom_mapping: dict[str, set[str]],
    micromamba: str = _DEFAULT_MM,
    mamba_root: str = _DEFAULT_ROOT,
    env: str = "mfa",
    timeout: float = 1800,
) -> dict[str, dict]:
    """Batch-invoke ``kalpy.evaluation.align_phones`` for a whole (corpus, aligner)
    cell in one subprocess call.

    ``utterances`` is ``(utt_id, ref_intervals, test_intervals)`` triples using
    FA-Bench's own :class:`~fabench.schema.Interval` (**raw**, pre-canonicalization
    labels — the form ``custom_mapping`` expects).

    Returns ``{utt_id: {"boundary_errors": [...], "score": ..., "phone_error_rate":
    ..., "num_insertions": ..., "num_deletions": ..., "num_matched_pairs": ...}}``,
    or ``{utt_id: {"error": "..."}}`` for a per-utterance failure inside kalpy —
    callers should check for the ``"error"`` key per utterance rather than assume
    every requested ``utt_id`` scored cleanly.
    """
    payload = {
        "silence_phones": sorted(silence_phones),
        "custom_mapping": {k: sorted(v) for k, v in custom_mapping.items()},
        "utterances": [
            {
                "utt_id": utt_id,
                "ref": [{"label": iv.label, "begin": iv.start, "end": iv.end} for iv in ref_ivs],
                "test": [{"label": iv.label, "begin": iv.start, "end": iv.end} for iv in test_ivs],
            }
            for utt_id, ref_ivs, test_ivs in utterances
        ],
    }
    if Path(micromamba).exists():
        cmd = [micromamba, "run", "-n", env, "python", str(_BRIDGE_SCRIPT)]
    else:
        # Fallback: assume a suitable interpreter is already active on PATH
        # (e.g. tests running inside the mfa env directly).
        cmd = ["python", str(_BRIDGE_SCRIPT)]
    run_env = dict(os.environ, MAMBA_ROOT_PREFIX=mamba_root)
    try:
        r = subprocess.run(
            cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=run_env,
            timeout=timeout,
        check=False)
    except subprocess.TimeoutExpired as e:
        raise BridgeError(f"mfa_paper kalpy bridge timed out after {timeout}s: {e}") from e
    if r.returncode != 0:
        raise BridgeError(
            f"mfa_paper kalpy bridge failed (rc={r.returncode}): {r.stderr[-2000:]}"
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise BridgeError(
            f"mfa_paper kalpy bridge returned non-JSON stdout: {e}\n"
            f"stderr: {r.stderr[-2000:]}"
        ) from e


def bridge_available(micromamba: str = _DEFAULT_MM, env: str = "mfa") -> bool:
    """True if the bridge's micromamba/env/kalpy.evaluation combo looks usable.

    Used to gate live-bridge tests and to give ``score_cell`` a fast, cheap
    pre-flight check before spending a subprocess round-trip on real data.
    """
    if not Path(micromamba).exists():
        return False
    try:
        r = subprocess.run(
            [micromamba, "run", "-n", env, "python", "-c", "import kalpy.evaluation"],
            capture_output=True, text=True, timeout=30,
        check=False)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0
