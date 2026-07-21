"""Concrete edge roles over PathBackend (queue / log / index layouts).

These are the runtime companions to :mod:`stations.protocols` for the engines.
Layouts follow PHYSICAL-CONTRACT §4–§6 (pending/completed/failed; CURRENT).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from stations.backends.claim import acquire_lease
from stations.backends.etag import content_etag
from stations.protocols import PathBackend
from stations.station import StationDecl

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, default=str, sort_keys=True).encode("utf-8")


@dataclass
class SimpleLease:
    worker_id: str
    claimed_at: datetime
    expires_at: datetime
    attempt: int
    item_id: str


@dataclass
class PathQueueEdge(Generic[T]):
    """QueueEdge over ``{root}/pending|completed|failed`` (PHYSICAL-CONTRACT §4).

    Item files: ``pending/{item_id}.json`` (optionally sharded by caller using
    item_id that embeds ``shard/id``). Leases: ``pending/{item_id}.lease``.
    """

    station: StationDecl[T]
    backend: PathBackend
    root: str
    serialize: Callable[[T], bytes]
    deserialize: Callable[[bytes], T]
    default_ttl_seconds: int = 900

    def _pending_item(self, item_id: str) -> str:
        base = self.root.rstrip("/")
        return f"{base}/pending/{item_id}.json"

    def _lease_path(self, item_id: str) -> str:
        base = self.root.rstrip("/")
        return f"{base}/pending/{item_id}.lease"

    def _terminal_path(self, folder: str, item_id: str) -> str:
        base = self.root.rstrip("/")
        return f"{base}/{folder}/{item_id}.json"

    def enqueue(self, item: T) -> str:
        item_id = _identity(item)
        path = self._pending_item(item_id)
        data = self.serialize(item)
        # Idempotent place: create-if-absent wins; existing is fine (P2)
        if not self.backend.create_if_absent(path, data):
            if not self.backend.exists(path):
                self.backend.write_atomic(path, data)
        return item_id

    def claim(
        self, *, worker_id: str, ttl_seconds: int
    ) -> Optional[tuple[T, SimpleLease]]:
        prefix = f"{self.root.rstrip('/')}/pending"
        candidates: List[str] = []
        for path in self.backend.list(prefix):
            if path.endswith("/"):
                continue
            if path.endswith(".lease"):
                continue
            if not path.endswith(".json"):
                continue
            candidates.append(path)

        # Shuffle-ish: reverse by path hash for spread without importing random state
        candidates.sort(key=lambda p: content_etag(p.encode()), reverse=True)

        for item_path in candidates:
            name = item_path.rsplit("/", 1)[-1]
            if not name.endswith(".json"):
                continue
            item_id = name[: -len(".json")]
            # strip root-relative pending prefix forms like "shard/id"
            # item_id may include subdirs if list returns nested paths
            rel = item_path
            pending_marker = "/pending/"
            if pending_marker in rel:
                rel = rel.split(pending_marker, 1)[1]
            if rel.endswith(".json"):
                item_id = rel[: -len(".json")]

            now = _now()
            expires = now + timedelta(seconds=ttl_seconds)
            lease_body = _json_dumps(
                {
                    "worker_id": worker_id,
                    "claimed_at": now.isoformat(),
                    "expires_at": expires.isoformat(),
                    "attempt": 1,
                    "item_id": item_id,
                }
            )
            lease_path = self._lease_path(item_id)
            if not acquire_lease(self.backend, lease_path, lease_body):
                continue
            raw = self.backend.read_bytes(self._pending_item(item_id))
            item = self.deserialize(raw)
            lease = SimpleLease(
                worker_id=worker_id,
                claimed_at=now,
                expires_at=expires,
                attempt=1,
                item_id=item_id,
            )
            return item, lease
        return None

    def complete(
        self, item: T, lease: SimpleLease, result: Optional[object] = None
    ) -> None:
        item_id = lease.item_id
        item_bytes = self.serialize(item)
        if _looks_json(item_bytes):
            try:
                item_obj: Any = json.loads(item_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                item_obj = item_bytes.decode("utf-8", errors="replace")
        else:
            item_obj = item_bytes.decode("utf-8", errors="replace")
        payload: Dict[str, Any] = {
            "item": item_obj,
            "completed_at": _now().isoformat(),
            "worker_id": lease.worker_id,
        }
        if result is not None:
            if isinstance(result, (str, int, float, bool, type(None), dict, list)):
                payload["result"] = result
            else:
                payload["result"] = str(result)
        term = self._terminal_path("completed", item_id)
        self.backend.write_atomic(term, _json_dumps(payload))
        # P6: terminal first, then pending delete, then lease
        pending = self._pending_item(item_id)
        if self.backend.exists(pending):
            self.backend.delete(pending)
        lease_path = self._lease_path(item_id)
        if self.backend.exists(lease_path):
            self.backend.delete(lease_path)

    def fail(self, item: T, lease: SimpleLease, error: object) -> None:
        item_id = lease.item_id
        payload = {
            "item_id": item_id,
            "error": str(error),
            "failed_at": _now().isoformat(),
            "worker_id": lease.worker_id,
        }
        term = self._terminal_path("failed", item_id)
        self.backend.write_atomic(term, _json_dumps(payload))
        pending = self._pending_item(item_id)
        if self.backend.exists(pending):
            self.backend.delete(pending)
        lease_path = self._lease_path(item_id)
        if self.backend.exists(lease_path):
            self.backend.delete(lease_path)

    def renew(self, lease: SimpleLease, *, ttl_seconds: int) -> bool:
        lease_path = self._lease_path(lease.item_id)
        if not self.backend.exists(lease_path):
            return False
        current = self.backend.read_bytes(lease_path)
        etag = (
            self.backend.etag(lease_path)  # type: ignore[attr-defined]
            if hasattr(self.backend, "etag")
            else content_etag(current)
        )
        now = _now()
        new_exp = now + timedelta(seconds=ttl_seconds)
        body = _json_dumps(
            {
                "worker_id": lease.worker_id,
                "claimed_at": lease.claimed_at.isoformat(),
                "expires_at": new_exp.isoformat(),
                "attempt": lease.attempt,
                "item_id": lease.item_id,
            }
        )
        ok = self.backend.replace_if_match(lease_path, body, etag=etag)
        if ok:
            lease.expires_at = new_exp
        return ok


def _looks_json(data: bytes) -> bool:
    data = data.lstrip()
    return data[:1] in (b"{", b"[")


def _identity(item: Any) -> str:
    for attr in ("key", "id", "item_id", "task_id", "place_id"):
        if callable(getattr(item, "key", None)) and attr == "key":
            try:
                return str(item.key())
            except Exception:
                pass
        val = getattr(item, attr, None)
        if val is not None and not callable(val):
            return str(val)
    if isinstance(item, dict):
        for k in ("id", "item_id", "task_id", "key"):
            if k in item:
                return str(item[k])
    return uuid.uuid4().hex


@dataclass
class PathLogEdge(Generic[T]):
    """Append-only log as file-per-record under ``root`` (WAL shape B)."""

    station: StationDecl[T]
    backend: PathBackend
    root: str
    serialize: Callable[[T], bytes]
    deserialize: Callable[[bytes], T]

    def append(self, record: T) -> str:
        item_id = _identity(record)
        path = f"{self.root.rstrip('/')}/{item_id}.json"
        data = self.serialize(record)
        self.backend.write_atomic(path, data)
        return item_id

    def iter_beyond(self, watermark: Optional[object] = None) -> Iterator[T]:
        seen = set(watermark) if isinstance(watermark, (list, set, tuple)) else set()
        if isinstance(watermark, str):
            seen = {watermark}
        for path in self.backend.list(self.root):
            if path.endswith("/"):
                continue
            name = path.rsplit("/", 1)[-1]
            if name in seen or path in seen:
                continue
            if name == "datapackage.json":
                continue
            try:
                raw = self.backend.read_bytes(path)
                yield self.deserialize(raw)
            except Exception as exc:
                logger.warning("skip non-conforming log record %s: %s", path, exc)


@dataclass
class PathIndexEdge(Generic[T]):
    """IndexEdge over ``root`` with CURRENT commit pointer (PHYSICAL-CONTRACT §6)."""

    station: StationDecl[T]
    backend: PathBackend
    root: str
    serialize_record: Callable[[T], bytes] = field(
        default=lambda r: _json_dumps(r)  # type: ignore[misc, assignment]
    )
    deserialize_record: Callable[[bytes], T] = field(
        default=lambda b: json.loads(b.decode("utf-8"))  # type: ignore[misc, assignment]
    )
    serialize_many: Optional[Callable[[Sequence[T]], bytes]] = None
    deserialize_many: Optional[Callable[[bytes], List[T]]] = None

    def _current_path(self) -> str:
        return f"{self.root.rstrip('/')}/CURRENT"

    def read_current(self) -> Optional[T | Sequence[T]]:
        path = self._current_path()
        if not self.backend.exists(path):
            return None
        meta = json.loads(self.backend.read_bytes(path).decode("utf-8"))
        checkpoint = meta.get("checkpoint")
        if not checkpoint:
            return None
        cp_path = f"{self.root.rstrip('/')}/{checkpoint}"
        if not self.backend.exists(cp_path):
            return None
        raw = self.backend.read_bytes(cp_path)
        if self.deserialize_many:
            return self.deserialize_many(raw)
        # line-delimited JSON records
        items: List[T] = []
        for line in raw.splitlines():
            if line.strip():
                items.append(self.deserialize_record(line))
        return items

    def hybrid_read(self, sources: Sequence[Any]) -> Sequence[T]:
        base = self.read_current()
        out: List[T] = []
        if base is None:
            pass
        elif isinstance(base, list):
            out.extend(base)
        else:
            out.append(base)  # type: ignore[arg-type]
        for src in sources:
            for rec in src.iter_beyond(self.watermark()):
                out.append(rec)
        return out

    def watermark(self) -> Optional[object]:
        path = self._current_path()
        if not self.backend.exists(path):
            return None
        meta = json.loads(self.backend.read_bytes(path).decode("utf-8"))
        return meta.get("folded", meta.get("generation"))

    def read_current_meta(self) -> Optional[Dict[str, Any]]:
        path = self._current_path()
        if not self.backend.exists(path):
            return None
        return json.loads(self.backend.read_bytes(path).decode("utf-8"))

    def current_etag(self) -> Optional[str]:
        path = self._current_path()
        if not self.backend.exists(path):
            return None
        if hasattr(self.backend, "etag"):
            return self.backend.etag(path)  # type: ignore[no-any-return]
        return content_etag(self.backend.read_bytes(path))
