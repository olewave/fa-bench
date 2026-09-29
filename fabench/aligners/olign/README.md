# Olign aligner

> **Olign 1.0 is in beta, and access is by request.** The hosted endpoint at
> `api.olewave.com` is not open. You need credentials from Olewave before this
> adapter can reach it. Ask at <info@olewave.com>. Everything else in FA-Bench
> runs without it. Olign is one row in the tables rather than a dependency.

Adapter for **Olign**, a proprietary commercial service, exposed to FA-Bench
as a forced aligner. It emits word and phone intervals, with a per-phone
score used as a confidence proxy. It is **not** one of the MFA-2026 paper
baselines, so it scores only under `scoring.protocol: fabench`.

- **Mode.** A (text-driven) only.
- **Granularity.** Word and phone.
- **Batch.** Yes. `align_corpus()` fans out over a thread pool
  (`params.concurrency`). The transport is I/O-bound REST, so threads (the
  GIL is released on socket I/O) scale to roughly the server's QPS budget.

## Requirements

A running Olign server reachable on your network.

| Transport | Needs | Notes |
|---|---|---|
| `REST` (default) | `requests` (core dep) | The published door. Recommended. |

There is no model download. The adapter is a thin client. Point it at the
hosted endpoint or at your own server.

### API version

The version is **in the path**, `https://api.olewave.com/olign/v0.9`. A client
selects a version by choosing that URL. There is no version header or query
parameter to set, and no negotiation. This adapter speaks Olign's
**synchronous** contract. The audio is the raw request body, everything else
is a query parameter, and the answer comes back in the same call. Parse
responses leniently and ignore keys you do not recognise, because new ones
appear without the version moving.

Olign's `/olign/v1` is a different API. It takes a whole recording as a
multipart upload and answers through a job you poll, and this adapter does not
use it.

Do not confuse the API version with the **service** version (`olign vX.Y.Z`),
which tracks the build and moves on every release. Every response reports the
build it ran.

### Credentials

The hosted endpoint sits behind **Cloudflare Access**, so every request needs
a service token, sent as two headers. Olewave issues the tokens, so ask at
info@olewave.com. The adapter sends them when both variables are set. Put them in `.fabench.env`, which is untracked, and never in
a config.

```bash
# .fabench.env
OLIGN_BASE_URL=https://api.olewave.com/olign/v0.9
CF_ACCESS_CLIENT_ID=<id>.access
CF_ACCESS_CLIENT_SECRET=<secret>
```

A `params.base_url` in your run config wins over `OLIGN_BASE_URL`. Drop it, or
point it at the same URL, to use the hosted endpoint. Without the token,
Cloudflare answers `403` before the request reaches Olign. A LAN or
self-hosted server needs no token.

## Configuration

Enable it in your run config's `aligners` list.

```yaml
- name: olign
  adapter: olign
  enabled: true
  modes: [A]
  granularity: [word, phone]
  emits_confidence: true
  params:
    transport: rest                        # rest (default) | grpc
    base_url: https://api.olewave.com/olign/v0.9   # or your own host
    core_type: en.phone.align
    accent: 2                              # 1 = UK, 2 = US
    timeout_s: 60
    concurrency: 8                         # parallel REST workers
```

| Param | Default | Meaning |
|---|---|---|
| `transport` | `rest` | `rest` or `grpc` |
| `base_url` | `$OLIGN_BASE_URL`, else `https://api.olewave.com/olign/v0.9` | REST endpoint |
| `host` | (none) | `host:port` for the gRPC transport |
| `core_type` | `en.phone.align` | server pipeline selector |
| `accent` | `2` | 1 = UK, 2 = US |
| `timeout_s` | `60` | per-request timeout |
| `concurrency` | `1` | parallel REST workers (raise toward the server's QPS) |
| `vad_enable` | `0` | gRPC-path VAD toggle |
| `chunk_bytes` | `3200` | gRPC stream chunk (100 ms at 16 kHz mono int16) |

## Units and normalization

The server returns boundary times in **milliseconds**. `parse_olign_result()`
converts them to seconds and drops zero-length intervals. See `adapter.py`
for the REST response shape.
