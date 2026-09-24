# Copyright 2026  Olewave, LLC
#
# Licensed under the PolyForm Noncommercial License 1.0.0; see LICENSE at the
# repository root for the full terms.

"""AWS Signature Version 4, in the standard library.

WHY THIS EXISTS. Every other endpoint in this package authenticates with a
bearer token or an API key in a header, so `http.request` could stay ignorant
of who was calling. AWS signs the whole request, so the credential is a
function of the method, the path, the query, the headers and the body, and it
has to be computed here rather than pasted into a dict.

The alternative is botocore, which is the usual answer and the wrong one for
this repo. It pulls in a dependency tree the sweep machine cannot reach (see
the offline-host notes in evals/README.md) and the signing itself is sixty
lines of HMAC. This is those sixty lines, and it makes the wire format
auditable in the same way the other providers are.

Scope. Only what Transcribe and S3 need, which is header-based signing over a
payload we already hold in memory. No chunked signing, no presigned URLs, no
STS credential resolution. Credentials come from the environment the way the
other providers' keys do.

References. The canonical request and string-to-sign formats are the public
SigV4 specification, and the two places where S3 differs from everything else
are marked below because they are the only parts that ever go wrong.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import urllib.parse

ALGORITHM = "AWS4-HMAC-SHA256"

#: RFC 3986 unreserved. Everything else in a path segment gets percent-encoded.
_UNRESERVED = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
)

#: The payload hash of an empty body, which comes up often enough to name.
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class AWSCredentialError(Exception):
    """No usable credentials, or a required piece of them is missing."""


def _quote(s: str) -> str:
    return "".join(c if c in _UNRESERVED
                   else "".join(f"%{b:02X}" for b in c.encode("utf-8"))
                   for c in s)


def canonical_uri(path: str, *, service: str) -> str:
    """The path as SigV4 wants to see it.

    THE S3 EXCEPTION. Every service but S3 expects the path URI-encoded
    TWICE, because its canonical form is the already-encoded request target
    encoded again. S3 expects it once. Getting this backwards produces a
    signature mismatch that reads like a bad secret key, which is why it is a
    named argument here rather than a guess at the call site.
    """
    if not path:
        return "/"
    once = "/".join(_quote(seg) for seg in path.split("/"))
    return once if service == "s3" else "/".join(
        _quote(seg) for seg in once.split("/"))


def canonical_query(query: dict[str, str] | None) -> str:
    if not query:
        return ""
    # Sorted by encoded key, then encoded value, as the specification requires.
    items = sorted((_quote(str(k)), _quote(str(v))) for k, v in query.items())
    return "&".join(f"{k}={v}" for k, v in items)


def sign_headers(
    *,
    method: str,
    url: str,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
    session_token: str | None = None,
    payload: bytes = b"",
    headers: dict[str, str] | None = None,
    content_sha256_header: bool | None = None,
    now: datetime.datetime | None = None,
) -> dict[str, str]:
    """Return the headers `url` needs to be accepted, including Authorization.

    `headers` are any extra headers that must be covered by the signature.
    Content-Type belongs there whenever the request has a body, because the
    services reject a signature that does not cover a header they read.
    """
    if not access_key or not secret_key:
        raise AWSCredentialError(
            "AWS needs both an access key id and a secret access key")

    parts = urllib.parse.urlsplit(url)
    host = parts.netloc
    amz_date = (now or datetime.datetime.now(datetime.timezone.utc)).strftime(
        "%Y%m%dT%H%M%SZ")
    datestamp = amz_date[:8]
    payload_hash = hashlib.sha256(payload).hexdigest()

    h = {k.lower(): str(v).strip() for k, v in (headers or {}).items()}
    h["host"] = host
    h["x-amz-date"] = amz_date
    # S3 READS THIS HEADER and refuses the request without it. Nothing else
    # needs it, and adding it everywhere would change SignedHeaders on every
    # request, which is the difference between matching AWS's published test
    # vectors and only believing this code is right. See test_awssig.py.
    want_sha_header = (service == "s3") if content_sha256_header is None \
        else bool(content_sha256_header)
    if want_sha_header:
        h["x-amz-content-sha256"] = payload_hash
    if session_token:
        h["x-amz-security-token"] = session_token

    signed = ";".join(sorted(h))
    canonical_headers = "".join(f"{k}:{h[k]}\n" for k in sorted(h))
    canonical_request = "\n".join([
        method.upper(),
        canonical_uri(parts.path, service=service),
        canonical_query(dict(urllib.parse.parse_qsl(parts.query))),
        canonical_headers,
        signed,
        payload_hash,
    ])

    scope = f"{datestamp}/{region}/{service}/aws4_request"
    to_sign = "\n".join([
        ALGORITHM, amz_date, scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k = _hmac(f"AWS4{secret_key}".encode("utf-8"), datestamp)
    for piece in (region, service, "aws4_request"):
        k = _hmac(k, piece)
    signature = hmac.new(k, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    out = dict(headers or {})
    out["Host"] = host
    out["X-Amz-Date"] = amz_date
    if want_sha_header:
        out["X-Amz-Content-Sha256"] = payload_hash
    if session_token:
        out["X-Amz-Security-Token"] = session_token
    out["Authorization"] = (
        f"{ALGORITHM} Credential={access_key}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}")
    return out
