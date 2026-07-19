"""Read-only station inspector (Burr telemetry lesson).

Streams and aggregates over a PathBackend — never loads whole trees into
memory as models. Structure checks (layout recognition) are separate from
content checks (lease JSON parse, CURRENT parse). Schema lookups are cached
per directory when a datapackage.json is present.

Normative vocabulary: GLOSSARY, PHYSICAL-CONTRACT, CONCURRENCY.
Repair/GC are Compactor duties (CONCURRENCY §5) — not this module.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

from stations.protocols import PathBackend

logger = logging.getLogger(__name__)

# Queue subdirs from PHYSICAL-CONTRACT §4
QUEUE_BUCKETS = ("pending", "completed", "failed")
# Index markers from PHYSICAL-CONTRACT §6
INDEX_MARKERS = ("CURRENT", "inbox", "shards")
# Lease filename patterns (PHYSICAL-CONTRACT §4; cocli also uses lease.json)
LEASE_SUFFIXES = (".lease",)
LEASE_BASENAMES = frozenset({"lease.json"})


@runtime_checkable
class _MtimeBackend(Protocol):
    def mtime(self, path: str) -> Optional[float]: ...


@dataclass
class LeaseInfo:
    path: str
    worker_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    expired: Optional[bool] = None


@dataclass
class BucketStats:
    name: str
    count: int = 0
    oldest_mtime: Optional[float] = None
    active_leases: int = 0
    expired_leases: int = 0
    leases: List[LeaseInfo] = field(default_factory=list)

    @property
    def oldest_age_seconds(self) -> Optional[float]:
        if self.oldest_mtime is None:
            return None
        return max(0.0, datetime.now(tz=timezone.utc).timestamp() - self.oldest_mtime)


@dataclass
class StationSnapshot:
    """Aggregated, read-only view of one discovered station."""

    name: str
    path: str
    role: str  # "queue" | "index" | "wal" | "unknown"
    buckets: Dict[str, BucketStats] = field(default_factory=dict)
    item_count: int = 0
    oldest_mtime: Optional[float] = None
    active_leases: int = 0
    expired_leases: int = 0
    current: Optional[Dict[str, object]] = None  # parsed CURRENT for index stations
    watermark: Optional[object] = None
    datapackage: Optional[str] = None  # path of schema sidecar if found
    notes: List[str] = field(default_factory=list)

    @property
    def oldest_age_seconds(self) -> Optional[float]:
        if self.oldest_mtime is None:
            return None
        return max(0.0, datetime.now(tz=timezone.utc).timestamp() - self.oldest_mtime)


@dataclass
class RootSnapshot:
    root: str
    stations: List[StationSnapshot]
    scanned_paths: int = 0


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_iso(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_age(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    secs = int(seconds)
    if secs < 60:
        return f"{secs}s"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 48:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def _is_lease_path(path: str) -> bool:
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if name in LEASE_BASENAMES:
        return True
    return any(name.endswith(suf) for suf in LEASE_SUFFIXES)


def _is_item_path(path: str) -> bool:
    """Structure check: count as a work item (not lease, not dir, not tmp)."""
    if path.endswith("/"):
        return False
    name = path.rsplit("/", 1)[-1]
    if name.startswith("."):
        return False
    if name in ("datapackage.json", "CURRENT"):
        return False
    if _is_lease_path(path):
        return False
    if "/tmp/" in f"/{path}" or path.startswith("tmp/"):
        return False
    return True


def _bucket_for(rel: str, station_prefix: str) -> Optional[str]:
    """Map a path under a station to pending|completed|failed|inbox|shards|other."""
    if station_prefix and not (
        rel == station_prefix or rel.startswith(station_prefix.rstrip("/") + "/")
    ):
        return None
    rest = rel[len(station_prefix) :].lstrip("/") if station_prefix else rel
    if not rest:
        return None
    top = rest.split("/", 1)[0]
    if top in QUEUE_BUCKETS or top in ("inbox", "shards", "tmp"):
        return top
    return "root"


class SchemaCache:
    """Cache datapackage.json lookups per directory (FsAuditor lesson)."""

    def __init__(self, backend: PathBackend) -> None:
        self._backend = backend
        self._cache: Dict[str, Optional[str]] = {}

    def datapackage_for(self, dir_path: str) -> Optional[str]:
        key = dir_path.rstrip("/") or "."
        if key in self._cache:
            return self._cache[key]
        candidate = f"{key}/datapackage.json" if key != "." else "datapackage.json"
        found = candidate if self._backend.exists(candidate) else None
        self._cache[key] = found
        return found


def _mtime(backend: PathBackend, path: str) -> Optional[float]:
    mtime_fn = getattr(backend, "mtime", None)
    if mtime_fn is None:
        return None
    try:
        result = mtime_fn(path)
    except Exception:
        return None
    if result is None:
        return None
    return float(result)


def _read_lease(backend: PathBackend, path: str) -> LeaseInfo:
    """Content check: parse lease JSON when present."""
    info = LeaseInfo(path=path)
    try:
        raw = backend.read_bytes(path)
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        logger.debug("lease parse failed for %s: %s", path, exc)
        return info
    if not isinstance(data, dict):
        return info
    info.worker_id = data.get("worker_id") if isinstance(data.get("worker_id"), str) else None
    exp = _parse_iso(data.get("expires_at"))
    info.expires_at = exp
    if exp is not None:
        info.expired = exp <= _now()
    return info


def _read_current(backend: PathBackend, path: str) -> Optional[Dict[str, object]]:
    try:
        raw = backend.read_bytes(path)
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            return dict(data)
        return None
    except Exception as exc:
        logger.debug("CURRENT parse failed for %s: %s", path, exc)
        return None


def discover_station_dirs(backend: PathBackend, root: str = "") -> List[str]:
    """Structure pass: find station roots under ``root``.

    A path is a station if it has queue buckets (pending/completed/failed),
    an index CURRENT, or a datapackage.json. Parent roots that only group
    stations (e.g. ``queues/``) are not stations themselves when children are.
    """
    prefix = root.rstrip("/")
    # Collect immediate and nested candidates via streaming list
    has_children: Dict[str, set[str]] = {}
    markers: Dict[str, set[str]] = {}

    def note(station_dir: str, marker: str) -> None:
        markers.setdefault(station_dir, set()).add(marker)

    for path in backend.list(prefix or "."):
        rel = path
        if prefix:
            if not (rel == prefix or rel.startswith(prefix + "/")):
                # LocalPathBackend may already return root-relative paths
                pass
        parts = [p for p in rel.strip("/").split("/") if p]
        if not parts:
            continue
        # Track markers relative to any ancestor
        name = parts[-1].rstrip("/")
        parent = "/".join(parts[:-1]) if len(parts) > 1 else ""
        if path.endswith("/"):
            dirname = path.rstrip("/")
            top = dirname.rsplit("/", 1)[-1]
            parent_dir = dirname.rsplit("/", 1)[0] if "/" in dirname else ""
            if top in QUEUE_BUCKETS or top in ("inbox", "shards"):
                note(parent_dir if parent_dir else ".", top)
            # parent/child for multi-station detection
            if parent_dir:
                has_children.setdefault(parent_dir, set()).add(top)
            continue
        if name == "CURRENT":
            note(parent if parent else ".", "CURRENT")
        elif name == "datapackage.json":
            note(parent if parent else ".", "datapackage")

    stations: List[str] = []
    for d, marks in markers.items():
        is_queue = bool(marks & set(QUEUE_BUCKETS))
        is_index = "CURRENT" in marks or bool(marks & {"inbox", "shards"})
        is_wal = "datapackage" in marks and not is_queue and not is_index
        if is_queue or is_index or is_wal:
            stations.append(d if d != "." else (prefix or "."))

    # If nothing found but root itself looks like one station, use root
    if not stations and prefix:
        stations = [prefix]
    elif not stations:
        stations = ["."]

    # Prefer longer (deeper) stations; drop pure parents that only group queues
    stations = sorted(set(stations), key=lambda s: (s.count("/"), s))
    return stations


def inspect_station(
    backend: PathBackend,
    station_path: str,
    *,
    schema_cache: Optional[SchemaCache] = None,
    parse_leases: bool = True,
    max_lease_samples: int = 20,
) -> StationSnapshot:
    """Stream+aggregate one station. Structure pass then selective content pass."""
    cache = schema_cache or SchemaCache(backend)
    prefix = station_path.rstrip("/") if station_path not in ("", ".") else ""
    display = prefix or "."

    buckets: Dict[str, BucketStats] = {}
    role = "unknown"
    current: Optional[Dict[str, object]] = None
    scanned = 0
    item_count = 0
    oldest: Optional[float] = None
    active_leases = 0
    expired_leases = 0
    lease_samples: List[LeaseInfo] = []
    notes: List[str] = []

    list_root = prefix if prefix else "."
    seen_buckets: set[str] = set()

    for path in backend.list(list_root):
        scanned += 1
        # normalize: backend may return paths relative to its root
        rel = path
        bucket = _bucket_for(rel, prefix)
        if bucket is None and prefix:
            # path not under this station
            if not (rel == prefix or rel.startswith(prefix + "/")):
                continue
            bucket = _bucket_for(rel, prefix) or "root"
        if bucket is None:
            bucket = "root"

        if path.endswith("/"):
            top = path.rstrip("/").rsplit("/", 1)[-1]
            if top in QUEUE_BUCKETS:
                seen_buckets.add(top)
                buckets.setdefault(top, BucketStats(name=top))
            elif top in ("inbox", "shards"):
                seen_buckets.add(top)
                buckets.setdefault(top, BucketStats(name=top))
            continue

        name = rel.rsplit("/", 1)[-1]
        if name == "CURRENT" and (bucket in ("root", None) or rel == f"{prefix}/CURRENT" or rel == "CURRENT"):
            current = _read_current(backend, rel)
            role = "index"
            continue

        if _is_lease_path(rel):
            # content pass for leases (bounded samples)
            info = _read_lease(backend, rel) if parse_leases else LeaseInfo(path=rel)
            if info.expired is True:
                expired_leases += 1
            elif info.expired is False or info.expired is None:
                active_leases += 1
            if len(lease_samples) < max_lease_samples:
                lease_samples.append(info)
            bname = bucket or "pending"
            bs = buckets.setdefault(bname, BucketStats(name=bname))
            if info.expired is True:
                bs.expired_leases += 1
            else:
                bs.active_leases += 1
            if len(bs.leases) < max_lease_samples:
                bs.leases.append(info)
            continue

        if not _is_item_path(rel):
            continue

        item_count += 1
        bname = bucket or "root"
        bs = buckets.setdefault(bname, BucketStats(name=bname))
        bs.count += 1
        mt = _mtime(backend, rel)
        if mt is not None:
            if bs.oldest_mtime is None or mt < bs.oldest_mtime:
                bs.oldest_mtime = mt
            if oldest is None or mt < oldest:
                oldest = mt

    if seen_buckets & set(QUEUE_BUCKETS) or any(
        b in buckets for b in QUEUE_BUCKETS
    ):
        role = "queue"
    elif current is not None or any(b in buckets for b in ("inbox", "shards")):
        role = "index"
    elif cache.datapackage_for(prefix or ".") is not None:
        role = "wal" if role == "unknown" else role

    watermark = None
    if current is not None:
        watermark = current.get("folded", current.get("generation"))

    dp = cache.datapackage_for(prefix or ".")
    name = display.rsplit("/", 1)[-1] if display not in (".", "") else display

    snap = StationSnapshot(
        name=name,
        path=display,
        role=role,
        buckets=buckets,
        item_count=item_count,
        oldest_mtime=oldest,
        active_leases=active_leases,
        expired_leases=expired_leases,
        current=current,
        watermark=watermark,
        datapackage=dp,
        notes=notes,
    )
    # attach lease samples on pending bucket for CLI detail
    if lease_samples and "pending" in snap.buckets:
        snap.buckets["pending"].leases = lease_samples
    return snap


def inspect_root(
    backend: PathBackend,
    root: str = "",
    *,
    parse_leases: bool = True,
) -> RootSnapshot:
    """Discover stations under root and aggregate each (streaming)."""
    schema_cache = SchemaCache(backend)
    station_dirs = discover_station_dirs(backend, root)
    stations: List[StationSnapshot] = []
    scanned = 0
    for d in station_dirs:
        snap = inspect_station(
            backend, d, schema_cache=schema_cache, parse_leases=parse_leases
        )
        stations.append(snap)
    return RootSnapshot(root=root or ".", stations=stations, scanned_paths=scanned)


def render_text(snapshot: RootSnapshot) -> str:
    """Plain-text fallback renderer (no Rich)."""
    lines: List[str] = []
    lines.append(f"Stations root: {snapshot.root}")
    lines.append(
        f"{'Station':<24} {'Role':<8} {'Items':>7} {'Oldest':>8} "
        f"{'Leases':>7} {'Expired':>8} Extra"
    )
    lines.append("-" * 80)
    for s in snapshot.stations:
        extra = ""
        if s.current is not None:
            gen = s.current.get("generation", "?")
            extra = f"CURRENT gen={gen}"
            if s.watermark is not None:
                extra += f" watermark={s.watermark!r}"
        bucket_bits = []
        for bname in ("pending", "completed", "failed", "inbox", "shards"):
            if bname in s.buckets:
                bucket_bits.append(f"{bname}={s.buckets[bname].count}")
        if bucket_bits:
            extra = (extra + " " if extra else "") + " ".join(bucket_bits)
        lines.append(
            f"{s.name:<24} {s.role:<8} {s.item_count:>7} "
            f"{_format_age(s.oldest_age_seconds):>8} "
            f"{s.active_leases:>7} {s.expired_leases:>8} {extra}"
        )
    return "\n".join(lines)


def render_rich(snapshot: RootSnapshot) -> None:
    """Terminal renderer using Rich when available."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        print(render_text(snapshot))
        return

    console = Console()
    table = Table(
        title="Stations",
        show_header=True,
        header_style="on grey23",
        padding=(0, 2, 0, 0),
        box=None,
    )
    table.add_column("Station", style="cyan", no_wrap=True)
    table.add_column("Role", style="dim")
    table.add_column("Items", justify="right")
    table.add_column("Oldest", style="dim", justify="right")
    table.add_column("Leases", justify="right")
    table.add_column("Expired", justify="right")
    table.add_column("Buckets / CURRENT")

    total_items = 0
    total_leases = 0
    for s in snapshot.stations:
        total_items += s.item_count
        total_leases += s.active_leases
        bits: List[str] = []
        for bname in ("pending", "completed", "failed", "inbox", "shards", "root"):
            if bname in s.buckets and s.buckets[bname].count:
                bits.append(f"{bname}={s.buckets[bname].count}")
        if s.current is not None:
            gen = s.current.get("generation", "?")
            bits.append(f"CURRENT gen={gen}")
            if s.watermark is not None:
                bits.append(f"wm={s.watermark!r}")
        role_style = {
            "queue": "bold yellow",
            "index": "bold green",
            "wal": "bold blue",
        }.get(s.role, "dim")
        table.add_row(
            s.name,
            f"[{role_style}]{s.role}[/{role_style}]",
            str(s.item_count),
            _format_age(s.oldest_age_seconds),
            str(s.active_leases),
            str(s.expired_leases),
            " ".join(bits),
        )

    table.add_row("", "", "", "", "", "", "")
    table.add_row(
        "[bold]total[/bold]",
        "",
        f"[bold]{total_items}[/bold]",
        "",
        f"[bold]{total_leases}[/bold]",
        "",
        "",
    )

    console.print(
        Panel(
            table,
            title="[bold]stations inspect[/bold]",
            subtitle=f"[dim]{snapshot.root}[/dim]",
            expand=False,
        )
    )

    # Lease detail for stations with leases
    for s in snapshot.stations:
        pending = s.buckets.get("pending")
        if not pending or not pending.leases:
            continue
        lt = Table(
            title=f"Leases — {s.name}",
            header_style="on grey23",
            padding=(0, 2, 0, 0),
            box=None,
        )
        lt.add_column("Worker", style="cyan")
        lt.add_column("Expires")
        lt.add_column("Status")
        lt.add_column("Path", style="dim", overflow="fold")
        for lease in pending.leases[:15]:
            status = "expired" if lease.expired else "active"
            style = "red" if lease.expired else "green"
            exp = lease.expires_at.isoformat() if lease.expires_at else "—"
            lt.add_row(
                lease.worker_id or "—",
                exp,
                f"[{style}]{status}[/{style}]",
                lease.path,
            )
        console.print(lt)


def inspect_and_render(
    root: str,
    *,
    backend: Optional[PathBackend] = None,
    parse_leases: bool = True,
    plain: bool = False,
) -> RootSnapshot:
    """CLI helper: open a local root and render."""
    from pathlib import Path as _Path

    from stations.backends.local import LocalPathBackend

    be: PathBackend = backend if backend is not None else LocalPathBackend(root)
    # When using LocalPathBackend(root), list paths relative to root
    snap = inspect_root(be, "" if backend is None else root, parse_leases=parse_leases)
    # Fix display root and "." station names to the path basename
    snap.root = root
    root_name = _Path(root).name or root
    for s in snap.stations:
        if s.name in (".", "", root) or s.path in (".", ""):
            s.name = root_name
            if s.path in (".", ""):
                s.path = root
    if plain:
        print(render_text(snap))
    else:
        render_rich(snap)
    return snap
