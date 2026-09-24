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

"""Per-request latency, for systems where a request is a unit of work.

WHY NOT JUST RTF. `rtf_mean` already exists and is the ASR convention, but it
answers a different question and it answers it badly for these rows.

* On the BATCH path the runner computes one `elapsed / total_audio` for the
  whole cell (fabench/aligners/runner.py), so every utterance carries the same
  number. At concurrency 8 that is throughput, and no amount of averaging turns
  it back into latency.
* RTF divides by audio duration, which assumes cost scales with audio. For a
  network endpoint most of a short request is fixed cost -- TLS, queueing,
  round trip -- so the same API scores RTF 0.31 on a 2.6 s utterance and 0.01
  on a 60 s file. Reported over FA-Bench's 2.57 s mean, RTF would mostly
  describe our utterance length.

So this reports the distribution and the decomposition instead.

**Percentiles, not a mean.** Latency is heavy-tailed: one retried call can
outweigh a hundred fast ones in a mean while changing p50 not at all. What
decides whether a 48,000-request sweep finishes overnight is p95 and p99.

**Fixed cost against marginal rate.** A least-squares fit of
`latency = fixed + per_audio x duration` separates the two, which is the thing
RTF conflates. `lat_fixed_s` is what a request costs before any audio is
processed and `lat_per_audio_s` is the rate once it is. FA-Bench's durations
span 0.35 to 23.6 s, so the fit is well conditioned. `lat_r2` says whether the
linear model holds at all; a low value means something other than duration
drives the time, which for a queued service it often does.

**Every system measured here is offline.** A synchronous request returns the
whole response at once, so there is no time to first word and the streaming
measures -- first partial, finalization lag, emission delay -- do not apply.
They are absent by construction, not by omission. A streaming recognizer emits
word times causally with limited lookahead, which makes them a different
measurement rather than a faster route to the same one.

**The network is inside the number, so it is reported too.** `lat_setup_s` is
the measured DNS + TCP + TLS floor to that endpoint from the machine that ran
the sweep, probed once per cell with no payload, and `lat_fixed_net_s` is
`lat_fixed_s` minus it. The first is a property of the network, the second of
the service, and only the second is worth comparing across vendors. Measured
from our scoring host the floor runs 38 ms to Google's us-central1 and 149 ms
to Deepgram, against observed calls of around 1.4 s, so it is a few percent
rather than the whole story -- but a few percent is the difference between
two vendors that look tied, and it is entirely an artefact of where the
sweep ran.

WHAT THESE NUMBERS ARE NOT. They are a DEPLOYMENT measurement, not a vendor
benchmark. They answer "what will a sweep cost in wall clock from here", which
is what they were added for, and they support a ranking among providers
measured from one machine at one time. They do not support an absolute claim
about a vendor's speed, they do not reproduce on another network, and they hold
only at the concurrency the cell ran at. Cached responses contribute nothing: a
cache hit is disk, and counting it would drive every percentile to zero on the
second run.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

#: Reported percentiles. p50 for the typical case, p95/p99 because the tail is
#: what a long sweep actually waits on, max because one wedged request is worth
#: seeing rather than smoothing away.
PERCENTILES = (50, 90, 95, 99)

#: Below this, the linear model is not describing the data and the split into a
#: fixed and a marginal cost is suppressed. Not a statistical convention, an
#: empirical one: the real endpoints come in at r2 ~ 0.00.
_MIN_R2 = 0.10

_EMPTY = {
    **{f"lat_p{p}_s": float("nan") for p in PERCENTILES},
    "lat_max_s": float("nan"),
    "lat_fixed_s": float("nan"),
    "lat_fixed_net_s": float("nan"),
    "lat_setup_s": float("nan"),
    "lat_per_audio_s": float("nan"),
    "lat_r2": float("nan"),
    "n_lat": 0,
}


def latency_metrics(
    latency_s: Sequence[float | None],
    audio_s: Sequence[float | None] | None = None,
    setup_s: Sequence[float | None] | None = None,
) -> dict:
    """Percentiles over `latency_s`, plus a fixed/marginal split against audio.

    `None` entries are dropped in step, which is how a cache hit or a local
    tool that reports no latency stays out of the statistics rather than
    entering as a zero.
    """
    lat: list[float] = []
    dur: list[float] = []
    aud = list(audio_s) if audio_s is not None else [None] * len(latency_s)
    for t, d in zip(latency_s, aud):
        if t is None:
            continue
        try:
            t = float(t)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(t) or t < 0:
            continue
        lat.append(t)
        try:
            dur.append(float(d) if d is not None else float("nan"))
        except (TypeError, ValueError):
            dur.append(float("nan"))

    if not lat:
        return dict(_EMPTY)

    a = np.asarray(lat, dtype=float)
    out = {f"lat_p{p}_s": float(np.percentile(a, p)) for p in PERCENTILES}
    out["lat_max_s"] = float(a.max())
    out["n_lat"] = len(a)
    out.update(_fit(a, np.asarray(dur, dtype=float)))

    # The network floor, and the fixed cost with it removed. One value per
    # cell in practice -- the probe runs once -- so the median is just that
    # value, taken robustly in case a cell mixes runs.
    su = [float(v) for v in (setup_s or []) if v is not None and np.isfinite(float(v))]
    out["lat_setup_s"] = float(np.median(su)) if su else float("nan")
    out["lat_fixed_net_s"] = (out["lat_fixed_s"] - out["lat_setup_s"]
                              if su and np.isfinite(out["lat_fixed_s"])
                              else float("nan"))
    return out


def _fit(lat: np.ndarray, dur: np.ndarray) -> dict:
    """Least squares `latency = fixed + per_audio x duration`.

    Needs at least three points and some spread in duration. Without spread the
    slope is unidentifiable and a fit would report an arbitrary split of a
    constant, which is worse than reporting nothing.
    """
    ok = np.isfinite(dur) & np.isfinite(lat)
    x, y = dur[ok], lat[ok]
    if x.size < 3 or float(np.ptp(x)) < 1e-6:
        return {"lat_fixed_s": float("nan"), "lat_per_audio_s": float("nan"),
                "lat_r2": float("nan")}
    slope, intercept = np.polyfit(x, y, 1)
    pred = intercept + slope * x
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    # REPORT THE FIT ONLY WHERE IT MEANS SOMETHING. Measured against the real
    # endpoints, duration explains essentially none of their latency -- r2 came
    # out 0.00 for both Deepgram over 40,924 calls and Google over 18,714, and
    # ElevenLabs produced a NEGATIVE fixed cost, which is not a quantity that
    # exists. These services are dominated by queueing, not by how much audio
    # they were sent, so "fixed plus rate" is the wrong model for them and
    # splitting a mean into two numbers invents a precision the data does not
    # have. r2 is always reported, so a suppressed fit says why it is absent.
    if not np.isfinite(r2) or r2 < _MIN_R2 or intercept < 0:
        return {"lat_fixed_s": float("nan"), "lat_per_audio_s": float("nan"),
                "lat_r2": r2}
    return {
        "lat_fixed_s": float(intercept),
        "lat_per_audio_s": float(slope),
        "lat_r2": r2,
    }
