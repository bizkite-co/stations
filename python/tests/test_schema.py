"""Schema sidecar write path (P1 / 0003 / 0007 §3)."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any, Dict

import pytest

from stations.schema import (
    SCHEMA_FILENAME,
    SchemaHoldingRuleError,
    check_holding_rule,
    is_schema_protected,
    write_schema_sidecar,
)


def _doc(fields: list[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "profile": "tabular-data-package",
        "name": "t",
        "resources": [
            {
                "name": "t",
                "path": "*.usv",
                "schema": {"fields": fields},
            }
        ],
    }


def test_write_schema_sidecar_atomic_and_protected(tmp_path: Path) -> None:
    fields = [{"name": "id", "type": "string"}, {"name": "n", "type": "integer"}]
    path = write_schema_sidecar(tmp_path, _doc(fields), protect=True)
    assert Path(path).name == SCHEMA_FILENAME
    on_disk = tmp_path / SCHEMA_FILENAME
    assert on_disk.exists()
    data = json.loads(on_disk.read_text(encoding="utf-8"))
    assert data["resources"][0]["schema"]["fields"][0]["name"] == "id"
    assert is_schema_protected(on_disk)
    mode = on_disk.stat().st_mode
    assert not (mode & stat.S_IWUSR)


def test_holding_rule_blocks_shrink(tmp_path: Path) -> None:
    write_schema_sidecar(
        tmp_path,
        _doc([{"name": "a", "type": "string"}, {"name": "b", "type": "string"}]),
    )
    with pytest.raises(SchemaHoldingRuleError):
        write_schema_sidecar(
            tmp_path,
            _doc([{"name": "a", "type": "string"}]),
            force=False,
        )


def test_holding_rule_allows_append(tmp_path: Path) -> None:
    write_schema_sidecar(
        tmp_path,
        _doc([{"name": "a", "type": "string"}]),
    )
    write_schema_sidecar(
        tmp_path,
        _doc(
            [
                {"name": "a", "type": "string"},
                {"name": "b", "type": "integer"},
            ]
        ),
        force=False,
    )
    data = json.loads((tmp_path / SCHEMA_FILENAME).read_text(encoding="utf-8"))
    assert len(data["resources"][0]["schema"]["fields"]) == 2


def test_force_bypasses_holding_rule(tmp_path: Path) -> None:
    write_schema_sidecar(
        tmp_path,
        _doc([{"name": "a", "type": "string"}, {"name": "b", "type": "string"}]),
    )
    write_schema_sidecar(
        tmp_path,
        _doc([{"name": "a", "type": "string"}]),
        force=True,
    )
    data = json.loads((tmp_path / SCHEMA_FILENAME).read_text(encoding="utf-8"))
    assert len(data["resources"][0]["schema"]["fields"]) == 1


def test_check_holding_rule_reorder() -> None:
    old = _doc([{"name": "a", "type": "string"}, {"name": "b", "type": "string"}])
    new = _doc([{"name": "b", "type": "string"}, {"name": "a", "type": "string"}])
    with pytest.raises(SchemaHoldingRuleError, match="rename/reorder"):
        check_holding_rule(old, new)
