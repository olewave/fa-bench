#!/usr/bin/env python3
# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""What a commercial ASR sweep will cost, measured rather than guessed.

    evals/timestamp_asrs/cloud_cost.py
    evals/timestamp_asrs/cloud_cost.py --conditions origin
    evals/timestamp_asrs/cloud_cost.py --corpus timit

THE THING THAT DECIDES THE BILL IS NOT THE AUDIO. FA-Bench sends one request
per utterance and its utterances are short -- 2.6 s on average, 2.1 s median on
Buckeye. A vendor that bills per second charges for what it heard; a vendor
that rounds each request up to a 15-second increment charges for 5.8x that.
Same audio, same work, six times the invoice. So this reads the real durations
out of the mix manifests and applies each vendor's ROUNDING as well as its
rate.

PRICES GO STALE. The table below is list, pay-as-you-go, checked 2026-09-16,
and every vendor discounts at volume and on annual plans. Treat it as the shape
of the bill, not a quote, and re-check before committing to a sweep. The
rounding column is the part that rarely changes and matters most.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

#: tool -> (usd per audio hour, billing increment in seconds, note)
#: increment 1 means "per second"; 15 means each request rounds up to 15 s.
PRICES = {
    "deepgram":   (0.312, 1,  "Nova-3 pay-as-you-go $0.0052/min; $0.0043 on Growth"),
    "assemblyai": (0.270, 1,  "Universal $0.27/hr"),
    "elevenlabs": (0.400, 1,  "Scribe ~$0.40/hr; tier-dependent, verify"),
    # v2 CONFIRMED by measurement, not by the pricing page: a 2.15 s request
    # came back with "totalBilledDuration": "3s", so it rounds up to the
    # second, not to a 15 s increment. That is the difference between $39 and
    # $287 for this benchmark, and it is why v2 is the one to run.
    # UNVERIFIED RATE. Speechmatics publishes a volume-tiered rate and the
    # enhanced operating point is the dearer one; this is the low-volume list
    # figure and the dashboard should be checked before it is quoted anywhere.
    #
    # Their job response does carry an integer `job.duration`, and over all
    # 47,805 receipts it sums to 27.85 h against 34.44 h of true audio, a
    # factor of 0.808. That is very close to flooring each request to the
    # second (27.78 h) but not equal to it, and Speechmatics never calls the
    # field a billing quantity. So it is recorded as a reported duration, not
    # a receipt, and the estimate below still bills the audio we sent. If they
    # do bill on it the true line is nearer $28.96 than $35.82.
    "speechmatics": (1.040, 1, "enhanced, ~$1.04/hr list at low volume -- VERIFY"),
    # UNVERIFIED RATE, and the weakest number in this table. IBM prices by
    # plan rather than by model, the response carries no billing field of any
    # kind, and the public pricing pages would not resolve when this was
    # written. $0.02/min is the commonly quoted Plus-plan list rate. Read the
    # real figure off the IBM Cloud dashboard before quoting it.
    "ibm": (1.200, 1, "en-US Large, Plus plan ~$0.02/min list -- VERIFY"),
    # CONFIRMED on the pricing page 2026-09-17, and the confirmation that
    # matters is the second half: "billed in one-second increments, with no
    # minimum applied" for standard batch. Several AWS speech features do carry
    # a 15 s per-request minimum, and at 47,805 utterances averaging 2.6 s that
    # single rule is the difference between about $12 and about $287. It is the
    # same trap that made Google v2 the right call over v1.
    "aws": (0.360, 1, "Transcribe batch $0.006/min, per second, NO "
                      "per-request minimum. Re-verified 2026-09-20 against "
                      "the price list API: USW1-TranscribeAudio $0.0001/s, "
                      "single dimension, no volume tiering"),
    # UNVERIFIED RATE. $1 per audio hour is the long-standing standard
    # speech-to-text figure; whether fast transcription is priced the same is
    # not established here, and the response carries no billing field. Read the
    # real number off the Azure portal before quoting it. The per-request
    # rounding is also unconfirmed, and that is the part that decides whether
    # 47,805 short utterances cost $41 or several times that.
    "azure": (1.000, 1, "AI Speech ~$1.00/audio hour standard -- VERIFY, and "
                        "confirm the rounding before a sweep"),
    "google_stt": (0.960, 1,  "v2 chirp_2 $0.016/min, billed to the second "
                              "(measured); v1 is $0.024/min in 15 s increments"),
}

CELLS = {
    "timit/dev":       "timit__dev__r237a487b.jsonl",
    "timit/core_test": "timit__core_test__r237a487b.jsonl",
    "buckeye/dev":     "buckeye__paper__dev__r02ca44ae.jsonl",
    "buckeye/test":    "buckeye__paper__test__r02ca44ae.jsonl",
}
N_CONDITIONS = 5          # origin + reverb + noise + music + babble


def _durations(manifest: Path) -> list[float]:
    out = []
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        try:
            with wave.open(json.loads(line)["mixed_audio_path"]) as w:
                out.append(w.getnframes() / float(w.getframerate() or 1))
        except Exception:
            continue
    return out


def _actual() -> int:
    """What the sweep has actually cost, from the vendors' own receipts.

    Not an estimate. Google returns totalBilledDuration in every response and
    the cache keeps the raw body, so the invoice is re-derivable at any time
    and stays right as the sweep grows. A provider that sends no receipt is
    reported by audio instead, which is the best available and is labelled.
    """
    import glob
    import json
    import wave

    rows = []
    for tool_dir in sorted(glob.glob(str(ROOT / "evals/timestamp_asrs/**/cache"),
                                     recursive=True)):
        tool = Path(tool_dir).parent.name
        billed = audio = 0.0
        n = n_receipt = 0
        # The PROVIDER, not the directory name: a nested recipe is named for
        # what varies (chirp2), which is not a key in the price table.
        provider = ""
        for f in glob.glob(f"{tool_dir}/**/*.json", recursive=True):
            try:
                d = json.loads(Path(f).read_text())
            except (OSError, ValueError):
                continue
            n += 1
            provider = provider or str(d.get("provider") or "")
            b = (d.get("raw", {}).get("metadata") or {}).get("totalBilledDuration", "")
            if isinstance(b, str) and b.endswith("s"):
                billed += float(b[:-1]); n_receipt += 1
            sec = d.get("audio_s")
            if sec is None:
                try:
                    with wave.open(d.get("audio", "")) as w:
                        sec = w.getnframes() / float(w.getframerate() or 1)
                except Exception:
                    sec = 0.0
            audio += float(sec or 0)
        if n:
            rows.append((tool, provider, n, n_receipt, audio, billed))

    if not rows:
        print("no cached responses yet -- nothing has been spent")
        return 0

    print(f"{'tool':22s} {'calls':>7s} {'receipts':>9s} {'audio h':>8s} "
          f"{'billed h':>9s} {'USD':>8s}")
    total = 0.0
    for tool, provider, n, nr, audio, billed in rows:
        rate = PRICES.get(provider, (0.0, 1, ""))[0]
        # No receipt means billing by audio is the best available figure.
        hours = (billed if nr else audio) / 3600
        usd = hours * rate
        total += usd
        mark = "" if nr == n else f"  ({n - nr} by audio, no receipt)"
        print(f"{tool:22s} {n:7d} {nr:9d} {audio/3600:8.2f} {hours:9.2f} "
              f"{usd:8.2f}{mark}")
        if not rate:
            print(f"{'':22s} no price for provider {provider!r}; add it to PRICES")
    print(f"\nspent so far: ${total:,.2f}")
    return 0


def _aws_orphans(delete: bool = False) -> int:
    """What is still sitting in the Transcribe staging bucket.

    The adapter deletes each object in a finally, so the only way one survives
    is the process being killed outright between the upload and the cleanup.
    Over a sweep of 47,805 utterances that is worth being able to check rather
    than assume, and the check is free.

    Storage is not where the money is. The whole corpus is 4 GB, which is nine
    cents a month, against roughly $15 for the Transcribe minutes. This exists
    so nothing is left behind, not because it would be expensive if it were.
    """
    import re as _re

    from fabench.envfile import load_env_file
    from fabench.timestamp_asrs.cloud.awssig import sign_headers
    from fabench.timestamp_asrs.cloud.http import request

    load_env_file()
    try:
        ak = os.environ["AWS_ACCESS_KEY_ID"]
        sk = os.environ["AWS_SECRET_ACCESS_KEY"]
        bucket = os.environ["AWS_S3_BUCKET"]
    except KeyError as e:
        print(f"set {e.args[0]} first")
        return 1
    tok = os.environ.get("AWS_SESSION_TOKEN")
    region = os.environ.get("AWS_REGION", "us-east-1")
    base = f"https://{bucket}.s3.{region}.amazonaws.com/"

    def call(method, url, payload=b""):
        h = sign_headers(method=method, url=url, region=region, service="s3",
                         access_key=ak, secret_key=sk, session_token=tok,
                         payload=payload)
        return request(url, method=method, data=payload or None, headers=h,
                       timeout_s=60, retries=2)

    keys, token, total = [], None, 0
    while True:
        u = base + "?list-type=2" + (f"&continuation-token={token}" if token else "")
        body = call("GET", u).decode("utf-8", "replace")
        keys += _re.findall(r"<Key>([^<]+)</Key>", body)
        total += sum(int(x) for x in _re.findall(r"<Size>(\d+)</Size>", body))
        nxt = _re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not nxt:
            break
        token = nxt.group(1)

    if not keys:
        print(f"{bucket}: empty, nothing left behind")
        return 0
    print(f"{bucket}: {len(keys)} object(s), {total / 1e6:.1f} MB, "
          f"about ${total / 1e9 * 0.023:.4f} a month")
    for k in keys[:10]:
        print(f"  {k}")
    if len(keys) > 10:
        print(f"  ... and {len(keys) - 10} more")
    if not delete:
        print("re-run with --delete to remove them")
        return 0
    for k in keys:
        call("DELETE", base + k)
    print(f"deleted {len(keys)} object(s)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    work = (os.environ.get("FABENCH_WORK_DIR")
            or str(Path(__file__).resolve().parents[2] / "data" / "work"))
    ap.add_argument("--manifests", default=f"{work}/manifests")
    ap.add_argument("--corpus", choices=["timit", "buckeye"], help="limit to one")
    ap.add_argument("--conditions", type=int, default=N_CONDITIONS,
                    help=f"how many of the {N_CONDITIONS} conditions to price")
    ap.add_argument("--actual", action="store_true",
                    help="what has ALREADY been spent, from the cached receipts")
    ap.add_argument("--aws-orphans", action="store_true",
                    help="list audio left in the Transcribe staging bucket")
    ap.add_argument("--delete", action="store_true",
                    help="with --aws-orphans, delete what it finds")
    a = ap.parse_args(argv)

    if a.aws_orphans:
        return _aws_orphans(delete=a.delete)
    if a.actual:
        return _actual()

    m = Path(a.manifests)
    durs: list[float] = []
    print(f"{'cell':18s} {'utts':>7s} {'hours':>8s} {'mean s':>7s} {'med s':>7s}")
    for cell, man in CELLS.items():
        if a.corpus and not cell.startswith(a.corpus):
            continue
        p = m / man
        if not p.exists():
            print(f"{cell:18s}  no manifest at {p}")
            continue
        d = sorted(_durations(p))
        durs += d
        print(f"{cell:18s} {len(d):7d} {sum(d)/3600:8.2f} {sum(d)/len(d):7.2f} "
              f"{d[len(d)//2]:7.2f}")
    if not durs:
        print("nothing measured; pass --manifests", file=sys.stderr)
        return 1

    k = a.conditions
    calls = len(durs) * k
    audio_h = sum(durs) * k / 3600
    print(f"\n{calls:,} requests, {audio_h:.1f} audio hours "
          f"({len(durs):,} utterances x {k} conditions)\n")

    def billed_h(inc):
        return sum(max(inc, math.ceil(d / inc) * inc) for d in durs) * k / 3600

    print(f"{'provider':12s} {'billed h':>9s} {'vs audio':>9s} {'USD':>9s}   note")
    per_second = 0.0
    for tool, (rate, inc, note) in PRICES.items():
        b_h = billed_h(inc)
        usd = b_h * rate
        if inc == 1:
            per_second += usd
        print(f"{tool:12s} {b_h:9.1f} {billed/audio_h if (billed:=b_h) else 0:8.2f}x "
              f"{usd:9.2f}   {note}")

    print(f"\nall four together: ${per_second:,.0f}, paid once. Every response is "
          f"cached, so rescores\nand restarts are free. --conditions 1 prices "
          f"clean only, a fifth of this.")
    print(f"\nfor reference, Google v1 instead of v2 would be "
          f"${billed_h(15) * 1.44:,.0f} for the same work\n"
          f"({billed_h(15):.0f} billed hours against {billed_h(1):.0f}), because "
          f"it rounds each request up to 15 s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
