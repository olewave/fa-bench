# olign aligner

> **Olign 1.0 is in beta, and access is by request.** The hosted endpoint at
> `api.olewave.com` is not open: you need credentials from Olewave before this
> adapter can reach it. Ask at <info@olewave.com>. Everything else in FA-Bench
> runs without it — Olign is one row in the tables, not a dependency.

Adapter for **olign**, a proprietary commercial service, exposed to FA-Bench as
a forced aligner. It emits word + phone intervals, with a per-phone score used
as a confidence proxy. It is **not** one of the MFA-2026 paper baselines, so it
scores only under `scoring.protocol: fabench`.

- **Mode:** A (text-driven) only.
- **Granularity:** word + phone.
- **Batch:** yes — `align_corpus()` fans out over a thread pool (`params.concurrency`);
  the transport is I/O-bound REST, so threads (GIL released on socket I/O) scale
  to roughly the server's QPS budget.

## Requirements

A running olign server reachable on your network. Two transports:

| Transport | Needs | Notes |
|---|---|---|
| `REST` (default) | `requests` (core dep) | The published door. Recommended. |

No model download — the adapter is a thin client. Point it at the hosted
endpoint or at your own server.

### API version

The version is **in the path**: `https://api.olewave.com/olign/v1`. A client
selects a version by choosing that URL — there is no version header or query
parameter to set, and no negotiation. `v1` is a promise about the request and
response shape, so a client written against it keeps working without pinning
anything.

`v1` is a **major** version and only changes when a change would break an
existing caller — a field removed or renamed, a type changed, a default that
alters results. Additive changes ship inside `v1`: new optional request fields,
new response fields. So parse responses leniently and ignore keys you do not
recognise, because new ones will appear without the version moving.

Do not confuse it with the **service** version (`olign vX.Y.Z`), which tracks
the build and moves on every release. One is the contract, the other is the
implementation; `/v1` can be served by many service versions, and knowing which
one answered is a debugging question, not a compatibility one.

## Configuration

Enable it in your run config's `aligners:` list:

```yaml
- name: olign
  adapter: olign
  enabled: true
  modes: [A]
  granularity: [word, phone]
  emits_confidence: true
  params:
    transport: rest                        # rest (default) | grpc
    base_url: https://api.olewave.com/olign/v1   # or your own host
    core_type: en.phone.align
    accent: 2                              # 1 = UK, 2 = US
    timeout_s: 60
    concurrency: 8                         # parallel REST workers
```

| Param | Default | Meaning |
|---|---|---|
| `transport` | `rest` | `rest` or `grpc` |
| `base_url` | — | REST endpoint, `https://api.olewave.com/olign/v1` |
| `host` | — | `host:port` for gRPC transport |
| `core_type` | `en.phone.align` | server pipeline selector |
| `accent` | `2` | 1 = UK, 2 = US |
| `timeout_s` | `60` | per-request timeout |
| `concurrency` | `1` | parallel REST workers (raise toward server QPS) |
| `vad_enable` | `0` | gRPC-path VAD toggle |
| `chunk_bytes` | `3200` | gRPC stream chunk (100 ms @ 16 kHz mono int16) |

## Units & normalization

The server returns boundary times in **milliseconds**; `parse_olign_result()`
converts to seconds and drops zero-length intervals. See `adapter.py` for the
REST response shape.

