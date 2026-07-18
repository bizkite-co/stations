"""Python Protocol surface for the stations on-disk contract.

Transcribed from ``spec/PROTOCOLS.md``. Protocols only — no runtime engines.
The language-agnostic contract in ``spec/PHYSICAL-CONTRACT.md`` and
``spec/CONCURRENCY.md`` remains authoritative.
"""

from __future__ import annotations

from datetime import datetime
from typing import (
    Iterable,
    Iterator,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

T = TypeVar("T")
T_in = TypeVar("T_in")
T_out = TypeVar("T_out")


class Identity(Protocol):
    """Stable record identity (PHYSICAL-CONTRACT §2, P2).

    Never derived from mutable attributes (title, status, path).
    """

    def key(self) -> str: ...


class PathBackend(Protocol):
    """Portable storage substrate over local FS and S3-class stores.

    Read/write only — claim/lease is *not* here (fsspec is a candidate
    implementation for this Protocol alone).
    """

    def exists(self, path: str) -> bool: ...

    def read_bytes(self, path: str) -> bytes: ...

    def write_atomic(self, path: str, data: bytes) -> None:
        """P3: no partially visible final path."""
        ...

    def list(self, prefix: str) -> Iterator[str]: ...

    def delete(self, path: str) -> None: ...

    def create_if_absent(self, path: str, data: bytes) -> bool:
        """Test-and-set. True on create; False if already present (CONCURRENCY C1)."""
        ...

    def replace_if_match(
        self, path: str, data: bytes, *, etag: Optional[str]
    ) -> bool:
        """CAS replace (If-Match / rename-over). True on success (CONCURRENCY C1)."""
        ...


class Station(Protocol[T]):
    """Typed path binding: path template + model + schema version + codec.

    Noun only — consumption role is on the edge (GLOSSARY § Edge role).
    """

    name: str
    path_template: str
    model: Type[T]
    schema_version: str
    serialization: str  # "usv" | "json-file" | "md-frontmatter"
    datapackage_path: Optional[str]

    def resolve(self, **params: str) -> str:
        """Render path_template with parameters into a backend path/prefix."""
        ...


class Lease(Protocol):
    worker_id: str
    claimed_at: datetime
    expires_at: datetime
    attempt: int
    item_id: str


class QueueEdge(Protocol[T]):
    """Future-tense consumption: claim → process → terminal (CONCURRENCY §2)."""

    station: Station[T]
    backend: PathBackend

    def enqueue(self, item: T) -> str:
        """Atomic placement into pending/. Returns item identity."""
        ...

    def claim(
        self, *, worker_id: str, ttl_seconds: int
    ) -> Optional[Tuple[T, Lease]]:
        """Discover + create-if-absent lease. None if nothing available (C2)."""
        ...

    def complete(
        self, item: T, lease: Lease, result: Optional[object] = None
    ) -> None:
        """Terminal write then pending delete, that order (P6)."""
        ...

    def fail(self, item: T, lease: Lease, error: object) -> None: ...

    def renew(self, lease: Lease, *, ttl_seconds: int) -> bool: ...


class LogEdge(Protocol[T]):
    """Past-tense append: immutable facts (CONCURRENCY §3 source)."""

    station: Station[T]
    backend: PathBackend

    def append(self, record: T) -> str:
        """Append-only write. Returns segment/path id. Never rewrites prior bytes (P7)."""
        ...

    def iter_beyond(self, watermark: Optional[object] = None) -> Iterator[T]:
        """Enumerate records beyond a folded frontier (retained) or remaining segments."""
        ...


class IndexEdge(Protocol[T]):
    """Present-tense derived state: fold + watermark (PHYSICAL-CONTRACT §6)."""

    station: Station[T]
    backend: PathBackend

    def read_current(self) -> Optional[T | Sequence[T]]:
        """Load committed generation via CURRENT (P9). None if no CURRENT."""
        ...

    def hybrid_read(self, sources: Sequence[LogEdge[object]]) -> Sequence[T]:
        """Committed generation + not-yet-folded sources (P12)."""
        ...

    def watermark(self) -> Optional[object]:
        """Freshness marker; None means untrustworthy as 'current'."""
        ...


class Transform(Protocol[T_in, T_out]):
    """Pure 1:1 model-to-model function. No I/O. ADR-001 generalized."""

    def __call__(self, src: T_in, /) -> T_out: ...


class Fold(Protocol[T_in, T_out]):
    """Pure N:1 aggregation. Deterministic and idempotent (CONCURRENCY C7)."""

    def __call__(self, records: Iterable[T_in]) -> Iterable[T_out]: ...


class Emission(Protocol):
    """Secondary typed emission into another machine's intake station."""

    type: str
    kind: Optional[str]
    file: str
    to: str  # identity: repo-moniker#station-or-intake


class TransformEngine(Protocol):
    """Owns claim/lease, idempotent complete, retry/dead-letter, trace ids."""

    def run_once(
        self,
        *,
        source: QueueEdge[T_in],
        transform: Transform[T_in, T_out],
        sink: LogEdge[T_out] | QueueEdge[T_out],
        worker_id: str,
        emissions: Sequence[Emission] = (),
    ) -> bool:
        """Claim one item, transform, complete. True if work done; False if idle."""
        ...


class Compactor(Protocol):
    """Single-writer index maintenance (CONCURRENCY §3–§4)."""

    def compact_once(
        self,
        *,
        sources: Sequence[LogEdge[object]],
        index: IndexEdge[object],
        fold: Fold[object, object],
        compactor_id: str,
    ) -> bool:
        """One fold cycle. True if a new generation was committed."""
        ...
