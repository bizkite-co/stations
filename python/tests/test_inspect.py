"""Read-only inspector: streaming counts, leases, CURRENT."""

from __future__ import annotations

import json
import time
from pathlib import Path

from stations.backends.local import LocalPathBackend
from stations.inspect import (
    inspect_root,
    inspect_station,
    render_text,
)


def _write(p: Path, text: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_inspect_queue_counts_and_oldest(tmp_path: Path) -> None:
    root = tmp_path / "queues" / "demo"
    _write(root / "pending" / "a.json", '{"id":"a"}')
    _write(root / "pending" / "b.json", '{"id":"b"}')
    _write(root / "completed" / "c.json", '{"id":"c"}')
    # make one file older
    old = root / "pending" / "a.json"
    past = time.time() - 3600
    import os

    os.utime(old, (past, past))

    backend = LocalPathBackend(root)
    snap = inspect_station(backend, "")
    assert snap.role == "queue"
    assert snap.item_count == 3
    assert snap.buckets["pending"].count == 2
    assert snap.buckets["completed"].count == 1
    assert snap.oldest_age_seconds is not None
    assert snap.oldest_age_seconds >= 3500


def test_inspect_leases_active_and_expired(tmp_path: Path) -> None:
    root = tmp_path / "q"
    item = root / "pending" / "shard" / "item1"
    _write(item / "task.json", "{}")
    expired = {
        "worker_id": "w1",
        "expires_at": "2020-01-01T00:00:00+00:00",
    }
    active = {
        "worker_id": "w2",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    _write(item / "lease.json", json.dumps(expired))
    item2 = root / "pending" / "shard" / "item2"
    _write(item2 / "task.json", "{}")
    _write(item2 / "lease.json", json.dumps(active))

    backend = LocalPathBackend(root)
    snap = inspect_station(backend, "")
    assert snap.active_leases == 1
    assert snap.expired_leases == 1
    assert snap.item_count == 2


def test_inspect_index_current(tmp_path: Path) -> None:
    root = tmp_path / "idx"
    current = {
        "generation": 7,
        "checkpoint": "checkpoint.000007.usv",
        "mode": "consuming",
        "folded": None,
    }
    _write(root / "CURRENT", json.dumps(current))
    _write(root / "inbox" / "x.usv", "row\n")
    _write(root / "shards" / "0.usv", "row\n")

    backend = LocalPathBackend(root)
    snap = inspect_station(backend, "")
    assert snap.role == "index"
    assert snap.current is not None
    assert snap.current["generation"] == 7
    assert snap.buckets["inbox"].count == 1
    assert snap.buckets["shards"].count == 1


def test_inspect_root_discovers_multiple_queues(tmp_path: Path) -> None:
    q1 = tmp_path / "queues" / "gm-list"
    q2 = tmp_path / "queues" / "enrichment"
    _write(q1 / "pending" / "a.json")
    _write(q2 / "pending" / "b.json")
    _write(q2 / "failed" / "c.json")

    backend = LocalPathBackend(tmp_path)
    root_snap = inspect_root(backend, "queues")
    names = {s.name for s in root_snap.stations}
    assert "gm-list" in names
    assert "enrichment" in names
    text = render_text(root_snap)
    assert "gm-list" in text
    assert "queue" in text


def test_local_backend_create_if_absent(tmp_path: Path) -> None:
    backend = LocalPathBackend(tmp_path)
    assert backend.create_if_absent("cell.json", b"one") is True
    assert backend.create_if_absent("cell.json", b"two") is False
    assert backend.read_bytes("cell.json") == b"one"


def test_local_backend_replace_if_match_requires_etag(tmp_path: Path) -> None:
    from stations.backends.etag import content_etag

    backend = LocalPathBackend(tmp_path)
    assert backend.create_if_absent("cell.json", b"one") is True
    assert backend.replace_if_match("cell.json", b"two", etag="wrong") is False
    assert backend.replace_if_match(
        "cell.json", b"two", etag=content_etag(b"one")
    ) is True
    assert backend.read_bytes("cell.json") == b"two"


def test_leases_not_counted_as_items(tmp_path: Path) -> None:
    root = tmp_path / "q"
    _write(root / "pending" / "x.json", "{}")
    _write(root / "pending" / "x.lease", "{}")
    backend = LocalPathBackend(root)
    snap = inspect_station(backend, "")
    assert snap.item_count == 1
