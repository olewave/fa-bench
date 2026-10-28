# Copyright 2026 Olewave, LLC
# SPDX-License-Identifier: Apache-2.0
"""manifest.py reads the corpus splits' work dirs and nothing else."""
import json
import sys

from fabench.dataprep.noisemix import manifest


def test_the_noise_corpora_own_dirs_are_not_read_as_a_split(tmp_path, monkeypatch):
    work, out = tmp_path / "work", tmp_path / "out"
    cmd = ("wav-reverberate --additive-signals='a.wav' --start-times='0' "
           "--snrs='5' - - |")
    for d in ("timit_core_test_noise", "musan_noise"):
        (work / d).mkdir(parents=True)
        (work / d / "wav.scp").write_text(f"utt1 {cmd}\n")
    monkeypatch.setattr(sys, "argv", ["manifest.py", str(work), str(out)])
    assert manifest.main() == 0
    recs = [json.loads(x) for x in (out / "TIMIT" / "noisy" / "noise" / "manifest.jsonl")
            .read_text().splitlines()]
    assert [r["split"] for r in recs] == ["timit_core_test"]
    assert not (out / "Buckeye").exists()
