"""Path helpers over StationDecl + segment combinators (decision 0010).

Compose declaration-time segment *types* with runtime *values*. Does not run
transforms (those are passed to engines / graph assembly separately).

Example::

    from stations.paths import phase_dir, item_dir
    from stations.segments import collect_phases

    ph = collect_phases(QUEUE.segments)
    assert ph is not None
    root = Path(QUEUE.resolve(campaign="roadmap"))
    pending = phase_dir(root, QUEUE, ph.pending)
    item = item_dir(root, QUEUE, ph.pending, key=task_id)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Union

from stations.segments import (
    PhaseRef,
    Phases,
    ShardByHash,
    ShardByPrefix,
    collect_phases,
    collect_shard,
)


def _station_segments(station: Any) -> Sequence[object]:
    segs = getattr(station, "segments", ()) or ()
    return segs


def require_phases(station: Any) -> Phases:
    """Return the Phases combinator declared on ``station``, or raise."""
    ph = collect_phases(_station_segments(station))
    if ph is None:
        raise ValueError(
            f"station {getattr(station, 'name', station)!r} has no phases(...) segment"
        )
    return ph


def phase_dir(
    root: Union[str, Path],
    station: Any,
    phase: Union[str, PhaseRef],
) -> Path:
    """``{root}/{phase}/`` validated against the station's declared phases."""
    ph = require_phases(station)
    ref = ph.require(phase)
    return Path(root) / ref.name


def shard_dir(
    root: Union[str, Path],
    station: Any,
    key: str,
    *,
    phase: Optional[Union[str, PhaseRef]] = None,
) -> Path:
    """``{root}/[{phase}/]{shard}/`` using the station's shard combinator."""
    base = Path(root)
    if phase is not None:
        base = phase_dir(base, station, phase)
    sh = collect_shard(_station_segments(station))
    if sh is None:
        raise ValueError(
            f"station {getattr(station, 'name', station)!r} has no shard combinator"
        )
    return base / sh.shard_for(key)


def item_dir(
    root: Union[str, Path],
    station: Any,
    phase: Union[str, PhaseRef],
    key: str,
    *,
    use_shard: bool = True,
) -> Path:
    """``{root}/{phase}/[{shard}/]{key}/`` — typical DFQ pending item layout.

    If the station declares a shard combinator and ``use_shard`` is True, the
    shard segment is inserted between phase and key.
    """
    base = phase_dir(root, station, phase)
    sh = collect_shard(_station_segments(station)) if use_shard else None
    if sh is not None:
        base = base / sh.shard_for(key)
    return base / key


def relative_phase_shard_key(
    station: Any,
    phase: Union[str, PhaseRef],
    key: str,
    *,
    use_shard: bool = True,
) -> str:
    """POSIX-relative path ``phase/[shard/]key`` (no leading root)."""
    ph = require_phases(station)
    ref = ph.require(phase)
    parts = [ref.name]
    sh = collect_shard(_station_segments(station)) if use_shard else None
    if sh is not None:
        parts.append(sh.shard_for(key))
    parts.append(key)
    return "/".join(parts)
