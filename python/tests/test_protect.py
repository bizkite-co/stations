"""General POSIX protect for ratified artifacts (CONCURRENCY §5)."""

from __future__ import annotations

import stat
from pathlib import Path

from stations.protect import (
    PROTECTED_MODE,
    is_protected,
    protect_path,
    unprotect_for_write,
)
from stations.schema import is_schema_protected, protect_schema_sidecar


def test_protect_and_unprotect_roundtrip(tmp_path: Path) -> None:
    f = tmp_path / "prospects.usv"
    f.write_text("a\x1fb\n", encoding="utf-8")
    assert not is_protected(f)

    protect_path(f)
    assert is_protected(f)
    mode = f.stat().st_mode
    assert not (mode & stat.S_IWUSR)
    assert stat.S_IMODE(mode) == PROTECTED_MODE

    unprotect_for_write(f)
    assert not is_protected(f)
    assert f.stat().st_mode & stat.S_IWUSR

    f.write_text("rewritten\n", encoding="utf-8")
    protect_path(f)
    assert is_protected(f)
    assert f.read_text(encoding="utf-8") == "rewritten\n"


def test_schema_aliases_delegate_to_protect(tmp_path: Path) -> None:
    f = tmp_path / "datapackage.json"
    f.write_text("{}", encoding="utf-8")
    protect_schema_sidecar(f)
    assert is_schema_protected(f)
    assert is_protected(f)


def test_protect_missing_is_noop(tmp_path: Path) -> None:
    missing = tmp_path / "nope.usv"
    protect_path(missing)
    unprotect_for_write(missing)
    assert is_protected(missing) is False
