# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""FALCON batch worker -- runs in evals/aligners/falcon/venv's interpreter.

argv: jobs.jsonl  ckpt  repo_path  mode

MODE B, PHONE TIER. FALCON's "english" path is reached only with
(lang=english, mode=phoneme, annotation=phn); anything else, word-level or
plain text included, falls through to a Dutch panphon G2P. So the job carries
the phone sequence and FALCON places the boundaries -- see the adapter
docstring for why there is no word tier here.

Two things its own driver does that matter:
  * `main_predict` reloads a 347MB checkpoint per call. Cached here, or a
    Buckeye cell would be checkpoint I/O rather than inference.
  * the transcript is read from a file BESIDE the wav, and the times in that
    file are never used -- only the labels. Each item therefore gets a scratch
    directory with a symlink to the audio and a .phn holding the phones.

`pred_bound` comes back as a leading 0.0 followed by one boundary per phone
transition, so K phones give K predictions and the last interval closes at the
audio duration.
"""
import functools
import json
import os
import sys
import tempfile

REPO = sys.argv[3]
# The audio paths in jobs.jsonl are repo-relative and the chdir below would
# silently reinterpret them against FALCON's own directory, leaving a dangling
# symlink and "No such file or directory" on every item.
CWD0 = os.getcwd()
sys.path.insert(0, REPO)
os.chdir(REPO)                     # its conf/ and assets/ resolve relatively

import predict as falcon
import torch
import torchaudio

falcon._load_model = functools.lru_cache(maxsize=1)(falcon._load_model)

# Only this triple reaches the English model; assert rather than trust it, so a
# future refactor upstream fails loudly instead of scoring Dutch G2P output.
_LANG = falcon.resolve_internal_language("english", "phoneme", "phn")
assert _LANG == "english", f"FALCON resolved language {_LANG!r}, not 'english'"


def _align(wav_path: str, phones: list, ckpt: str, td: str):
    stem = "utt"
    wav = os.path.join(td, stem + ".wav")
    if os.path.lexists(wav):
        os.remove(wav)
    src = wav_path if os.path.isabs(wav_path) else os.path.join(CWD0, wav_path)
    os.symlink(os.path.abspath(src), wav)

    audio, sr = torchaudio.load(wav)
    n = audio.shape[1]
    step = n / len(phones)
    with open(os.path.join(td, stem + ".phn"), "w") as f:
        f.writelines(f"0 {int((i + 1) * step)} {p}\n" for i, p in enumerate(phones))

    pred, _truth, _mapped = falcon.main_predict(
        wav, ckpt, w_phi=0.5, language="english", annotation="phn", no_plots=True)
    pred = pred.detach().cpu().tolist() if isinstance(pred, torch.Tensor) else list(pred)
    bounds = pred + [n / sr]
    return [[phones[i], float(bounds[i]), float(bounds[i + 1])]
            for i in range(min(len(phones), len(bounds) - 1))]


def main() -> int:
    jobs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    ckpt = sys.argv[2]
    if not os.path.isabs(ckpt):
        ckpt = os.path.join(REPO, ckpt)
    with tempfile.TemporaryDirectory() as td:
        for j in jobs:
            try:
                phones = j.get("phone_seq") or []
                if not phones:
                    raise ValueError("mode B needs a phone sequence; none supplied")
                spans = _align(j["audio_path"], phones, ckpt, td)
                print(json.dumps({"item_id": j["item_id"],
                                  "words": [], "phones": spans}), flush=True)
            except Exception as e:
                print(json.dumps({"item_id": j["item_id"],
                                  "error": f"{type(e).__name__}: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
