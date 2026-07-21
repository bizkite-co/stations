"""Lease claim helpers built only from PathBackend primitives (C1–C3).

The only claim is successful create-if-absent of the lease path (C2).
Expired leases are taken over by replace_if_match (CAS), never
delete-then-create (C3).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol, runtime_checkable

from stations.backends.etag import content_etag
from stations.protocols import PathBackend

logger = logging.getLogger(__name__)


@runtime_checkable
class _EtagBackend(Protocol):
    def etag(self, path: str) -> Optional[str]: ...


def _backend_etag(backend: PathBackend, path: str, current: bytes) -> str:
    etag_fn = getattr(backend, "etag", None)
    if etag_fn is not None:
        tag = etag_fn(path)
        if tag is not None:
            return str(tag)
    return content_etag(current)


def parse_expires_at(lease_bytes: bytes) -> Optional[datetime]:
    """Extract expires_at from a JSON lease record, if present."""
    try:
        data = json.loads(lease_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("expires_at")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def default_is_expired(
    lease_bytes: bytes, *, now: Optional[datetime] = None
) -> bool:
    """True if lease JSON expires_at is in the past (or unparseable → not expired)."""
    exp = parse_expires_at(lease_bytes)
    if exp is None:
        return False
    clock = now if now is not None else datetime.now(tz=timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    return clock > exp


def try_create_lease(backend: PathBackend, lease_path: str, lease_bytes: bytes) -> bool:
    """Claim via create-if-absent only (C2). True iff this worker owns the lease."""
    return backend.create_if_absent(lease_path, lease_bytes)


def try_reclaim_lease(
    backend: PathBackend,
    lease_path: str,
    new_lease_bytes: bytes,
    *,
    is_expired: Optional[Callable[[bytes], bool]] = None,
) -> bool:
    """CAS-replace an expired lease (C3). Never delete-then-create.

    ``is_expired`` defaults to :func:`default_is_expired` (JSON ``expires_at``).
    """
    predicate = is_expired or default_is_expired
    if not backend.exists(lease_path):
        # Race: lease vanished between failed create and reclaim — try create again
        return backend.create_if_absent(lease_path, new_lease_bytes)
    try:
        current = backend.read_bytes(lease_path)
    except FileNotFoundError:
        return backend.create_if_absent(lease_path, new_lease_bytes)
    except Exception:
        # S3 missing object may surface as ClientError
        if not backend.exists(lease_path):
            return backend.create_if_absent(lease_path, new_lease_bytes)
        raise

    if not predicate(current):
        return False

    etag = _backend_etag(backend, lease_path, current)
    return backend.replace_if_match(lease_path, new_lease_bytes, etag=etag)


def acquire_lease(
    backend: PathBackend,
    lease_path: str,
    lease_bytes: bytes,
    *,
    is_expired: Optional[Callable[[bytes], bool]] = None,
) -> bool:
    """Create-if-absent, else CAS-reclaim if expired. Single entry for workers."""
    if try_create_lease(backend, lease_path, lease_bytes):
        return True
    return try_reclaim_lease(
        backend, lease_path, lease_bytes, is_expired=is_expired
    )
