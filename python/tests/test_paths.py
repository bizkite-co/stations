"""Path helpers + PhaseRef (decision 0010)."""

from __future__ import annotations

from pathlib import Path

import pytest

from stations.paths import item_dir, phase_dir, relative_phase_shard_key, shard_dir
from stations.segments import phases, shard_by_hash
from stations.station import StationDecl


def _queue_decl() -> StationDecl[object]:
    return StationDecl(
        name="enrichment",
        path_template="campaigns/{campaign}/queues/enrichment",
        model=object,
        segments=(
            phases("pending", "completed", "failed"),
            shard_by_hash(2),
        ),
    )


def test_phase_ref_attribute_and_reject_foreign_token() -> None:
    ph = phases("pending", "completed")
    other = phases("pending", "done")
    assert ph.pending.name == "pending"
    assert ph["completed"].name == "completed"
    with pytest.raises(ValueError, match="not owned"):
        ph.require(other.pending)


def test_phase_dir_and_item_dir_compose_shard(tmp_path: Path) -> None:
    decl = _queue_decl()
    ph = decl.segments[0]
    assert ph.is_phase("pending")
    root = tmp_path / "enrichment"
    pending = phase_dir(root, decl, ph.pending)
    assert pending == root / "pending"
    key = "task-1"
    item = item_dir(root, decl, ph.pending, key)
    sh = decl.segments[1].shard_for(key)
    assert item == root / "pending" / sh / key
    rel = relative_phase_shard_key(decl, ph.pending, key)
    assert rel == f"pending/{sh}/{key}"


def test_magic_string_phase_still_validated() -> None:
    decl = _queue_decl()
    with pytest.raises(ValueError, match="not in declared"):
        phase_dir(Path("/tmp"), decl, "not-a-phase")
