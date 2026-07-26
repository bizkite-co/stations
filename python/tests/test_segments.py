"""Declaration-time segment combinators (decision 0010)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from stations.segments import (
    phases,
    partition_by_day_of_month,
    shard_by_char_index,
    shard_by_hash,
    shard_by_prefix,
)
from stations.station import StationDecl


def test_phases_declaration_not_global_hardcode() -> None:
    mail = phases("tmp", "new", "cur")
    tasks = phases("draft", "pending", "active", "completed")
    assert mail.is_phase("tmp")
    assert not mail.is_phase("pending")
    assert tasks.is_phase("pending")
    assert mail.names != tasks.names
    with pytest.raises(ValueError, match="not in declared"):
        mail.require("draft")


def test_phases_rejects_empty_and_dupes() -> None:
    with pytest.raises(ValueError):
        phases()
    with pytest.raises(ValueError, match="duplicate"):
        phases("a", "a")


def test_shard_by_hash_width_is_declaration_param() -> None:
    s1 = shard_by_hash(1)
    s2 = shard_by_hash(2)
    key = "user@example.com"
    assert len(s1.shard_for(key)) == 1
    assert len(s2.shard_for(key)) == 2
    # stable
    assert s2.shard_for(key) == s2.shard_for(key)


def test_shard_by_prefix() -> None:
    s = shard_by_prefix(2)
    assert s.shard_for("ChIJHello") == "ch"
    assert s.path_suffix("AB") == "ab/"


def test_shard_by_char_index_place_id_sixth() -> None:
    """Matches cocli get_place_id_shard (index 5)."""
    s = shard_by_char_index(5)
    assert s.shard_for("ChIJ-5-rest") == "5"
    assert s.shard_for("ChIJ-5-rest.usv") == "5"
    assert s.shard_for("ab") == "b"  # short: last char


def test_partition_day_of_month_and_ttl() -> None:
    p = partition_by_day_of_month(ttl_days=7)
    d = date(2026, 7, 24)
    assert p.partition_for(d) == "24"
    # day 10 with now=24 is 14 days ago → expired if same month
    assert p.is_expired("10", now=datetime(2026, 7, 24, tzinfo=timezone.utc)) is True
    assert p.is_expired("24", now=datetime(2026, 7, 24, tzinfo=timezone.utc)) is False


def test_station_decl_holds_segments_at_declaration() -> None:
    class M:
        pass

    decl = StationDecl(
        name="enrichment",
        path_template="campaigns/{campaign}/queues/enrichment",
        model=M,
        segments=(
            phases("pending", "completed", "failed"),
            shard_by_hash(1),
        ),
    )
    assert len(decl.segments) == 2
    assert decl.segments[0].is_phase("pending")
    assert len(decl.segments[1].shard_for("x")) == 1
