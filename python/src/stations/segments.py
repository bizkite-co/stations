"""Segment combinators (decision 0010 §3) — declaration-time path grammar.

These are **types** of dynamic path segments, constructed when a station is
declared. The *values* (e.g. ``pending/``, shard ``a7``, day ``23``) exist only
on disk at runtime.

Closed set (few leaves): phases, hash-shard, prefix-shard, day-of-month
partition. No plugin registry — add a fifth combinator only when a third
consumer hand-rolls the same shape.

Example (declaration time)::

    from stations.segments import phases, shard_by_hash

    QUEUE = StationDecl(
        name="enrichment",
        path_template="campaigns/{campaign}/queues/enrichment",
        model=Task,
        segments=(
            phases("pending", "completed", "failed", "sideline"),
            shard_by_hash(1),  # place-id style 1-char shard under pending/
        ),
    )

Runtime::

    QUEUE.segments[0].is_phase("pending")  # True
    QUEUE.segments[1].shard_for(place_id)  # e.g. "X"
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class PhaseRef:
    """Declaration-scoped phase token — not a free-floating magic string.

    Bound to the ``Phases`` instance that created it (by identity). Path helpers
    and engines should take ``PhaseRef`` (or resolve via ``Phases.ref`` /
    ``Phases.require``) so call sites do not invent phase spellings.
    """

    name: str
    _owner_id: int  # id(Phases) — avoid cross-station token mix-ups

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Phases:
    """Named phase directories for a station (queue states, maildir, tasks, …).

    Phase *names* are fixed at declaration; which directories exist on disk is a
    runtime value question. Access tokens via attribute or mapping::

        ph = phases("pending", "completed")
        ph.pending          # PhaseRef
        ph["completed"]     # PhaseRef
    """

    names: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError("phases(...) requires at least one phase name")
        if len(set(self.names)) != len(self.names):
            raise ValueError(f"duplicate phase names: {self.names!r}")
        for n in self.names:
            if not n or "/" in n or n in (".", ".."):
                raise ValueError(f"invalid phase name: {n!r}")
        # Safe Python identifiers become attributes (pending, completed, …)
        refs: Dict[str, PhaseRef] = {
            n: PhaseRef(name=n, _owner_id=id(self)) for n in self.names
        }
        object.__setattr__(self, "_refs", refs)

    @property
    def refs(self) -> Dict[str, PhaseRef]:
        return getattr(self, "_refs")  # type: ignore[no-any-return]

    def __getattr__(self, name: str) -> PhaseRef:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            refs: Dict[str, PhaseRef] = object.__getattribute__(self, "_refs")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        if name in refs:
            return refs[name]
        raise AttributeError(
            f"{type(self).__name__!r} object has no phase {name!r}; "
            f"declared {self.names!r}"
        )

    def __getitem__(self, name: str) -> PhaseRef:
        return self.ref(name)

    def ref(self, name: str) -> PhaseRef:
        """Return the PhaseRef for a declared name (or raise)."""
        try:
            refs: Dict[str, PhaseRef] = object.__getattribute__(self, "_refs")
        except AttributeError as exc:
            raise ValueError("Phases not initialized") from exc
        if name not in refs:
            raise ValueError(
                f"phase {name!r} not in declared phases {self.names!r}"
            )
        return refs[name]

    def is_phase(self, phase: Union[str, PhaseRef]) -> bool:
        name = phase.name if isinstance(phase, PhaseRef) else phase
        return name in self.names

    def require(self, phase: Union[str, PhaseRef]) -> PhaseRef:
        """Validate and return a PhaseRef belonging to this Phases instance."""
        if isinstance(phase, PhaseRef):
            if phase._owner_id != id(self) or phase.name not in self.names:
                raise ValueError(
                    f"PhaseRef {phase.name!r} is not owned by this Phases "
                    f"(declared {self.names!r})"
                )
            return phase
        return self.ref(phase)

    def path_suffix(self, phase: Union[str, PhaseRef]) -> str:
        """Relative segment ``{phase}/`` for a declared phase."""
        return f"{self.require(phase).name}/"


def phases(*names: str) -> Phases:
    """Declare phase directories for this station (declaration-time)."""
    return Phases(names=tuple(names))


@dataclass(frozen=True)
class ShardByHash:
    """Route a key to a hex shard of width ``n`` (e.g. n=2 → ``00``..``ff``).

    ``n`` is fixed at declaration; the shard id for a given record is runtime.
    """

    n: int

    def __post_init__(self) -> None:
        if self.n < 1 or self.n > 8:
            raise ValueError(f"shard_by_hash n out of range 1..8: {self.n}")

    def shard_for(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return digest[: self.n]

    def path_suffix(self, key: str) -> str:
        return f"{self.shard_for(key)}/"


def shard_by_hash(n: int = 2) -> ShardByHash:
    """Declare hash-hex sharding of width ``n`` (declaration-time)."""
    return ShardByHash(n=n)


@dataclass(frozen=True)
class ShardByPrefix:
    """Route a key by its first ``k`` characters (after optional strip)."""

    k: int
    lower: bool = True

    def __post_init__(self) -> None:
        if self.k < 1 or self.k > 64:
            raise ValueError(f"shard_by_prefix k out of range 1..64: {self.k}")

    def shard_for(self, key: str) -> str:
        s = key.strip()
        if self.lower:
            s = s.lower()
        if len(s) < self.k:
            return s.ljust(self.k, "_")
        return s[: self.k]

    def path_suffix(self, key: str) -> str:
        return f"{self.shard_for(key)}/"


def shard_by_prefix(k: int, *, lower: bool = True) -> ShardByPrefix:
    """Declare prefix sharding of length ``k`` (declaration-time)."""
    return ShardByPrefix(k=k, lower=lower)


@dataclass(frozen=True)
class ShardByCharIndex:
    """Route by a single character at a fixed index (e.g. Place ID 6th char).

    Matches cocli historical ``get_place_id_shard`` when ``index=5``:
    - empty → ``fallback``
    - ``len < index+1`` → last character (even if non-alnum for short keys)
    - otherwise character at ``index`` if alnum else ``fallback``
    """

    index: int = 5
    fallback: str = "_"

    def __post_init__(self) -> None:
        if self.index < 0 or self.index > 256:
            raise ValueError(f"shard_by_char_index index out of range: {self.index}")

    def shard_for(self, key: str) -> str:
        base = key.replace("\\", "/").split("/")[-1]
        for ext in (".usv", ".csv", ".json"):
            if base.endswith(ext):
                base = base[: -len(ext)]
                break
        # Match cocli get_place_id_shard: short keys → fallback (not last char)
        if not base or len(base) < self.index + 1:
            return self.fallback
        char = base[self.index]
        return char if char.isalnum() else self.fallback

    def path_suffix(self, key: str) -> str:
        return f"{self.shard_for(key)}/"


def shard_by_char_index(index: int = 5, *, fallback: str = "_") -> ShardByCharIndex:
    """Declare fixed-index character sharding (declaration-time)."""
    return ShardByCharIndex(index=index, fallback=fallback)


@dataclass(frozen=True)
class PartitionByDayOfMonth:
    """Day-of-month partition (01–31) with optional TTL for GC/watermark.

    Partition *format* and ``ttl_days`` are declaration-time; which day folder
    a write uses is runtime.
    """

    ttl_days: int

    def __post_init__(self) -> None:
        if self.ttl_days < 1:
            raise ValueError("ttl_days must be >= 1")

    def partition_for(self, when: Optional[Union[datetime, date]] = None) -> str:
        if when is None:
            when = datetime.now(tz=timezone.utc)
        if isinstance(when, datetime):
            d = when.date()
        else:
            d = when
        return f"{d.day:02d}"

    def path_suffix(self, when: Optional[Union[datetime, date]] = None) -> str:
        return f"{self.partition_for(when)}/"

    def is_expired(
        self,
        partition_name: str,
        *,
        now: Optional[datetime] = None,
        reference_month: Optional[date] = None,
    ) -> bool:
        """Heuristic expiry: partition day is more than ``ttl_days`` behind *now*.

        Day-of-month alone is ambiguous across months; this uses the latest
        calendar day ``<= now`` matching ``partition_name`` in the current or
        previous month (enough for TTL-7 style GC, not a full calendar DB).
        """
        now = now or datetime.now(tz=timezone.utc)
        try:
            day = int(partition_name)
        except ValueError:
            return False
        if day < 1 or day > 31:
            return False
        ref = reference_month or now.date()
        # candidate: this month or previous month
        for month_delta in (0, -1):
            y, m = ref.year, ref.month + month_delta
            if m < 1:
                y -= 1
                m += 12
            try:
                part_date = date(y, m, day)
            except ValueError:
                continue
            if part_date <= ref:
                age = (ref - part_date).days
                return age > self.ttl_days
        return False


def partition_by_day_of_month(*, ttl_days: int = 7) -> PartitionByDayOfMonth:
    """Declare day-of-month partitions with TTL (declaration-time)."""
    return PartitionByDayOfMonth(ttl_days=ttl_days)


# Type alias for StationDecl.segments
SegmentCombinator = Union[
    Phases,
    ShardByHash,
    ShardByPrefix,
    ShardByCharIndex,
    PartitionByDayOfMonth,
]


def collect_phases(segments: Sequence[object]) -> Optional[Phases]:
    for s in segments:
        if isinstance(s, Phases):
            return s
    return None


def collect_shard(
    segments: Sequence[object],
) -> Optional[Union[ShardByHash, ShardByPrefix, ShardByCharIndex]]:
    for s in segments:
        if isinstance(s, (ShardByHash, ShardByPrefix, ShardByCharIndex)):
            return s
    return None
