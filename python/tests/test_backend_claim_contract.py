"""CONCURRENCY §2 claim/lease contract tests against PathBackend implementations.

Local: real filesystem. S3: moto (optional — skipped if moto/boto3 unavailable).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Protocol

import pytest

from stations.backends.claim import (
    acquire_lease,
    default_is_expired,
    try_create_lease,
    try_reclaim_lease,
)
from stations.backends.etag import content_etag
from stations.backends.local import LocalPathBackend


class _BackendFactory(Protocol):
    def __call__(self) -> Any: ...


def _lease_bytes(
    worker_id: str,
    *,
    expires_in_seconds: int,
    attempt: int = 1,
) -> bytes:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "worker_id": worker_id,
        "claimed_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=expires_in_seconds)).isoformat(),
        "attempt": attempt,
    }
    return json.dumps(payload).encode("utf-8")


@pytest.fixture
def local_backend(tmp_path: Any) -> LocalPathBackend:
    return LocalPathBackend(tmp_path)


def test_create_if_absent_contention(local_backend: LocalPathBackend) -> None:
    path = "pending/item1.lease"
    a = _lease_bytes("worker-a", expires_in_seconds=600)
    b = _lease_bytes("worker-b", expires_in_seconds=600)
    assert try_create_lease(local_backend, path, a) is True
    assert try_create_lease(local_backend, path, b) is False
    assert local_backend.read_bytes(path) == a


def test_replace_if_match_rejects_wrong_etag(local_backend: LocalPathBackend) -> None:
    path = "cell.json"
    assert local_backend.create_if_absent(path, b"v1") is True
    assert local_backend.replace_if_match(path, b"v2", etag="deadbeef") is False
    assert local_backend.read_bytes(path) == b"v1"
    good = content_etag(b"v1")
    assert local_backend.replace_if_match(path, b"v2", etag=good) is True
    assert local_backend.read_bytes(path) == b"v2"


def test_reclaim_expired_via_cas_not_delete_create(
    local_backend: LocalPathBackend,
) -> None:
    path = "pending/item.lease"
    dead = _lease_bytes("old-worker", expires_in_seconds=-60)
    assert try_create_lease(local_backend, path, dead) is True
    assert default_is_expired(dead) is True

    # Spy: ensure delete is not used for reclaim path by wrapping delete
    deleted: list[str] = []
    original_delete = local_backend.delete

    def tracking_delete(p: str) -> None:
        deleted.append(p)
        original_delete(p)

    local_backend.delete = tracking_delete  # type: ignore[method-assign]

    fresh = _lease_bytes("new-worker", expires_in_seconds=600, attempt=2)
    assert try_reclaim_lease(local_backend, path, fresh) is True
    assert deleted == [], "C3: reclaim must not delete-then-create"
    owned = json.loads(local_backend.read_bytes(path))
    assert owned["worker_id"] == "new-worker"
    assert owned["attempt"] == 2


def test_reclaim_active_lease_fails(local_backend: LocalPathBackend) -> None:
    path = "pending/held.lease"
    held = _lease_bytes("owner", expires_in_seconds=3600)
    assert try_create_lease(local_backend, path, held) is True
    thief = _lease_bytes("thief", expires_in_seconds=3600)
    assert try_reclaim_lease(local_backend, path, thief) is False
    assert json.loads(local_backend.read_bytes(path))["worker_id"] == "owner"


def test_acquire_lease_create_then_reclaim(local_backend: LocalPathBackend) -> None:
    path = "pending/x.lease"
    assert (
        acquire_lease(
            local_backend, path, _lease_bytes("w1", expires_in_seconds=-10)
        )
        is True
    )
    assert (
        acquire_lease(
            local_backend, path, _lease_bytes("w2", expires_in_seconds=600)
        )
        is True
    )
    assert json.loads(local_backend.read_bytes(path))["worker_id"] == "w2"


def test_write_atomic_no_partial_visibility(
    local_backend: LocalPathBackend, tmp_path: Any
) -> None:
    path = "data/out.json"
    local_backend.write_atomic(path, b'{"ok": true}')
    assert local_backend.read_bytes(path) == b'{"ok": true}'
    # no leftover tmp parts at root of station
    leftovers = [p for p in tmp_path.rglob("*.part") if p.is_file()]
    assert leftovers == []


# ── S3 (moto) ──────────────────────────────────────────────────────────


def _moto_s3_backend() -> Iterator[Any]:
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from stations.backends.s3 import S3PathBackend

    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="stations-test")
        yield S3PathBackend(bucket="stations-test", client=client)


@pytest.fixture
def s3_backend() -> Iterator[Any]:
    yield from _moto_s3_backend()


def test_s3_create_if_absent_contention(s3_backend: Any) -> None:
    path = "pending/item1.lease"
    a = _lease_bytes("worker-a", expires_in_seconds=600)
    b = _lease_bytes("worker-b", expires_in_seconds=600)
    assert try_create_lease(s3_backend, path, a) is True
    assert try_create_lease(s3_backend, path, b) is False
    assert s3_backend.read_bytes(path) == a


def test_s3_reclaim_expired_via_cas(s3_backend: Any) -> None:
    path = "pending/item.lease"
    dead = _lease_bytes("old", expires_in_seconds=-120)
    assert try_create_lease(s3_backend, path, dead) is True
    fresh = _lease_bytes("new", expires_in_seconds=600)
    assert try_reclaim_lease(s3_backend, path, fresh) is True
    assert json.loads(s3_backend.read_bytes(path))["worker_id"] == "new"


def test_s3_reclaim_active_fails(s3_backend: Any) -> None:
    path = "pending/held.lease"
    held = _lease_bytes("owner", expires_in_seconds=3600)
    assert try_create_lease(s3_backend, path, held) is True
    assert (
        try_reclaim_lease(
            s3_backend, path, _lease_bytes("thief", expires_in_seconds=3600)
        )
        is False
    )


def test_s3_replace_if_match_wrong_etag(s3_backend: Any) -> None:
    path = "obj.bin"
    assert s3_backend.create_if_absent(path, b"alpha") is True
    assert s3_backend.replace_if_match(path, b"beta", etag="not-the-etag") is False
    assert s3_backend.read_bytes(path) == b"alpha"
    tag = s3_backend.etag(path)
    assert tag is not None
    assert s3_backend.replace_if_match(path, b"beta", etag=tag) is True
    assert s3_backend.read_bytes(path) == b"beta"
