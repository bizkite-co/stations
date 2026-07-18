# Protocol surface (Python reference interfaces)

Status: draft v0 (2026-07-17). Design-only — these are the **language-facing**
interfaces the reference implementation must satisfy. The on-disk contract
([PHYSICAL-CONTRACT.md](./PHYSICAL-CONTRACT.md), [CONCURRENCY.md](./CONCURRENCY.md))
is language-agnostic and is the source of truth; these Protocols are a
Python-shaped projection of that contract for the reference package.

Terms of art: [GLOSSARY.md](../GLOSSARY.md).

## Principles

1. **Models in, models out.** Transforms and folds receive typed records and
   return typed records. They never open files, claim leases, or know paths.
2. **I/O lives in engines.** Claim/lease, atomic placement, `CURRENT` swings,
   and WAL append are owned by backend engines that implement the Protocols
   below — never by application transforms.
3. **Edge roles are declared, not inferred.** A station path does not "know"
   whether it is a queue, WAL, or index; the consumer edge does.
4. **Generics over Pydantic (or equivalent).** `Station[T]` and friends are
   typed by the record model bound to the station schema.

## 1. Record identity and path backend

```python
from typing import Protocol, TypeVar, Optional, Iterator, Iterable, Sequence
from pathlib import Path
from datetime import datetime

T = TypeVar("T")
T_in = TypeVar("T_in")
T_out = TypeVar("T_out")

class Identity(Protocol):
    """Stable record identity (PHYSICAL-CONTRACT §2, P2). Never derived from
    mutable attributes (title, status, path)."""
    def key(self) -> str: ...

class PathBackend(Protocol):
    """Portable storage substrate over local FS and S3-class stores.
    Read/write only — claim/lease is *not* here (fsspec is a candidate
    implementation for this Protocol alone)."""

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
    def replace_if_match(self, path: str, data: bytes, *, etag: Optional[str]) -> bool:
        """CAS replace (If-Match / rename-over). True on success (CONCURRENCY C1)."""
        ...
```

## 2. Station declaration

```python
class Station(Protocol[T]):
    """A typed path binding: path template + model + schema version + codec.
    Noun only — consumption role is on the edge (GLOSSARY § Edge role)."""

    name: str
    path_template: str          # e.g. "campaigns/{campaign}/queues/gm-list/pending"
    model: type[T]              # Pydantic (or equivalent) record type
    schema_version: str
    serialization: str          # "usv" | "json-file" | "md-frontmatter"
    datapackage_path: Optional[str]  # required when serialization == "usv" (P1)

    def resolve(self, **params: str) -> str:
        """Render path_template with parameters into a backend path/prefix."""
        ...
```

## 3. Edge roles

```python
class QueueEdge(Protocol[T]):
    """Future-tense consumption: claim → process → terminal (CONCURRENCY §2)."""

    station: Station[T]
    backend: PathBackend

    def enqueue(self, item: T) -> str:
        """Atomic placement into pending/. Returns item identity."""
        ...
    def claim(self, *, worker_id: str, ttl_seconds: int) -> Optional[tuple[T, "Lease"]]:
        """Discover + create-if-absent lease. None if nothing available (C2)."""
        ...
    def complete(self, item: T, lease: "Lease", result: Optional[object] = None) -> None:
        """Terminal write then pending delete, that order (P6)."""
        ...
    def fail(self, item: T, lease: "Lease", error: object) -> None: ...
    def renew(self, lease: "Lease", *, ttl_seconds: int) -> bool: ...

class Lease(Protocol):
    worker_id: str
    claimed_at: datetime
    expires_at: datetime
    attempt: int
    item_id: str

class LogEdge(Protocol[T]):
    """Past-tense append: immutable facts (CONCURRENCY §3 source)."""

    station: Station[T]
    backend: PathBackend

    def append(self, record: T) -> str:
        """Append-only write. Returns segment/path id. Never rewrites prior bytes (P7)."""
        ...
    def iter_beyond(self, watermark: Optional[object] = None) -> Iterator[T]:
        """Enumerate records beyond a folded frontier (retained mode) or all
        remaining segments (consuming mode)."""
        ...

class IndexEdge(Protocol[T]):
    """Present-tense derived state: fold + watermark (PHYSICAL-CONTRACT §6)."""

    station: Station[T]
    backend: PathBackend

    def read_current(self) -> Optional[T | Sequence[T]]:
        """Load committed generation via CURRENT (P9). None if no CURRENT."""
        ...
    def hybrid_read(self, sources: Sequence[LogEdge[object]]) -> Sequence[T]:
        """Committed generation + not-yet-folded sources (P12). Over-reading is
        safe; under-reading is not."""
        ...
    def watermark(self) -> Optional[object]:
        """Freshness marker; None means untrustworthy as 'current'."""
        ...
```

## 4. Transforms and folds

```python
class Transform(Protocol[T_in, T_out]):
    """Pure 1:1 model-to-model function. No I/O. ADR-001 generalized.
    Decorator target: @transform(from_station=..., to_station=...)."""

    def __call__(self, src: T_in) -> T_out: ...

class Fold(Protocol[T_in, T_out]):
    """Pure N:1 aggregation. Deterministic and idempotent (CONCURRENCY C7).
    v1 default: last-write-wins by identity + version stamp."""

    def __call__(self, records: Iterable[T_in]) -> Iterable[T_out]: ...

class Emission(Protocol):
    """Secondary typed emission into another machine's intake station
    (GLOSSARY § Emission edge; decision 0001). Never into a ratified station."""

    type: str
    kind: Optional[str]
    file: str
    to: str   # identity: repo-moniker#station-or-intake
```

## 5. Engines (runtime, not pure functions)

```python
class TransformEngine(Protocol):
    """Owns claim/lease, idempotent complete, retry/dead-letter, trace ids.
    Runs a Transform over a QueueEdge → writes primary output (+ emissions)."""

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
    """Single-writer index maintenance (CONCURRENCY §3–§4). Advisory lock for
    liveness; CAS CURRENT for safety (C12)."""

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
```

## 6. Mapping from existing cocli surfaces

| cocli today | Stations Protocol |
| :--- | :--- |
| `CampaignQueueProtocol` (`push/poll/ack/nack`) | `QueueEdge` (`enqueue/claim/complete/fail`) |
| `CompactManager` / index compilers | `Compactor` + `Fold` |
| `FilesystemQueue` / S3 conditional PUT | `PathBackend` + `QueueEdge` |
| ADR-001 model-to-model functions | `Transform` |
| Frictionless `datapackage.json` | `Station.datapackage_path` + schema version |

The rename from `poll/ack` → `claim/complete` is intentional: cocli's names hide the
lease lifecycle that CONCURRENCY §2 makes explicit.

## 7. What these Protocols deliberately exclude

- **Query / analytics** — DuckDB (or any reader of the on-disk contract) is the read side.
- **Cluster sync / rsync / gossip** — product transport, not the stations substrate.
- **WASI runtime** — optional future enforcement of single-writer (decision 0007); not a
  Protocol dependency for v1.
- **Schema migration engine** — deferred (decision 0003); when it is implemented it is
  itself a `Transform` between versioned stations.

## 8. Implementation path

1. This document is the interface contract (now).
2. Reference package (`stations/python/`, decision 0005) starts with a pure
   `stations.protocols` module — Protocols only, no runtime — so cocli Phase 4/5
   services can type-hint against them without a full extraction.
3. Runtime engines are implemented behind the Protocols without changing the on-disk
   contract (falsifiability test from METHOD.md step 8).
