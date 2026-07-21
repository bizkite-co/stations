"""Content-addressed etag helper shared by local CAS and claim reclaim."""

from __future__ import annotations

import hashlib


def content_etag(data: bytes) -> str:
    """Stable etag for local (and tests): sha256 hex of file bytes.

    S3 uses server-assigned ETags (often MD5 of body for single-part PUTs);
    :class:`~stations.backends.s3.S3PathBackend.etag` returns those instead.
    """
    return hashlib.sha256(data).hexdigest()
