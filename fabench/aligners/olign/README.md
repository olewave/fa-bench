# Olign aligner

> **This adapter calls Olign's 0.9 endpoint, which needs a service token from
> Olewave.** Ask at <info@olewave.com>. For Olign's current API, register at
> <https://tycho.olewave.com/#signup> and run the `olign_v1` recipes with the API
> key from your account. Everything else in FA-Bench runs without Olign. It is
> one row in the tables, and nothing else depends on it.

Adapter for **Olign**, a proprietary commercial service, exposed to FA-Bench
as a forced aligner. It emits word and phone intervals, with a per-phone
score used as a confidence proxy. It is **not** one of the MFA-2026 paper
baselines.

- **Mode.** A (text-driven) only.
- **Granularity.** Word and phone.
- **Batch.** Yes. `align_corpus()` fans out over a thread pool
  (`params.concurrency`). The transport is I/O-bound REST, so threads (the
  GIL is released on socket I/O) scale to roughly the server's QPS budget.

## Requirements

The adapter is a thin REST client of the hosted endpoint, with no model to
download. It needs the credentials described below.

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

Do not confuse the API version with the **Olign** version. The published
results and the paper come from **Olign 0.9**, reached through API v0.9, and
both name it Olign 0.9. Every response reports the Olign version it ran, so
check it before comparing a run with the published numbers. Each hyp.jsonl
record keeps the `versions` object of the response that made it, for results
fetched since 2026-10-11. A later Olign release can sit behind the same API
path, and the `/olign/v1` path is a different API.

### Credentials

Every request needs a service token, sent as two headers. Olewave issues the tokens, so ask at
info@olewave.com. The adapter sends them when both variables are set. Put them in `.fabench.env`, which is untracked, and never in
a config.

```bash
# .fabench.env
OLIGN_BASE_URL=https://api.olewave.com/olign/v0.9
CF_ACCESS_CLIENT_ID=<id>.access
CF_ACCESS_CLIENT_SECRET=<secret>
```

A `params.base_url` in your run config wins over `OLIGN_BASE_URL`. Drop it, or
point it at the same URL, to use the hosted endpoint. Without the token, the
endpoint answers `403`.

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
    base_url: https://api.olewave.com/olign/v0.9
    core_type: en.phone.align
    accent: 2                              # 1 = UK, 2 = US
    timeout_s: 60
    concurrency: 8                         # parallel REST workers
```

| Param | Default | Meaning |
|---|---|---|
| `base_url` | `$OLIGN_BASE_URL`, else `https://api.olewave.com/olign/v0.9` | REST endpoint |
| `core_type` | `en.phone.align` | server pipeline selector |
| `accent` | `2` | 1 = UK, 2 = US |
| `timeout_s` | `60` | per-request timeout |
| `concurrency` | `1` | parallel REST workers (raise toward the server's QPS) |

## Units and normalization

The server returns boundary times in **milliseconds**. `parse_olign_result()`
converts them to seconds and drops zero-length intervals. See `adapter.py`
for the REST response shape.
