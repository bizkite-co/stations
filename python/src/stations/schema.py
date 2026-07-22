"""Schema sidecar (datapackage.json) writes — sole stations write path (P1, 0003, 0007 §3).

Consumers MUST route all schema-sidecar mutations through this module (or
Compactor commit paths that call it). Ad-hoc ``open(..., \"w\")`` of
``datapackage.json`` is non-conforming.

Holding rule (decision 0003): a writer MUST NOT shrink or reorder existing
field lists when live readers may exist, unless ``force=True``.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Union

from stations.backends.local import LocalPathBackend
from stations.protocols import PathBackend

logger = logging.getLogger(__name__)

SCHEMA_FILENAME = "datapackage.json"

# Mode after successful write: owner/group/other read-only (CONCURRENCY §5 note).
# Re-writes chmod u+w first, then restore.
_PROTECTED_MODE = 0o444
_WRITABLE_MODE = 0o644


class SchemaWriteError(ValueError):
    """Invalid or non-conforming schema sidecar write."""


class SchemaHoldingRuleError(SchemaWriteError):
    """Field-list change violates decision 0003 holding rule."""


def schema_path_for(station_dir: Union[str, Path]) -> str:
    """Return the datapackage path under a station directory (posix str)."""
    base = str(station_dir).rstrip("/")
    if base.endswith(SCHEMA_FILENAME):
        return base
    return f"{base}/{SCHEMA_FILENAME}" if base not in ("", ".") else SCHEMA_FILENAME


def _field_names(fields: Sequence[Mapping[str, Any]]) -> List[str]:
    return [str(f.get("name", "")) for f in fields]


def _resource_fields(doc: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    resources = doc.get("resources") or []
    if not resources:
        return []
    first = resources[0]
    if not isinstance(first, Mapping):
        return []
    schema = first.get("schema") or {}
    if not isinstance(schema, Mapping):
        return []
    fields = schema.get("fields") or []
    if not isinstance(fields, list):
        return []
    return [f for f in fields if isinstance(f, Mapping)]


def check_holding_rule(
    existing: Mapping[str, Any],
    new_doc: Mapping[str, Any],
) -> None:
    """Raise SchemaHoldingRuleError if new_doc shrinks/reorders/retypes fields (0003)."""
    old_fields = _resource_fields(existing)
    new_fields = _resource_fields(new_doc)
    if not old_fields:
        return
    if len(new_fields) < len(old_fields):
        raise SchemaHoldingRuleError(
            f"field count decreased ({len(old_fields)} -> {len(new_fields)}); "
            "schema evolution is a station transition, not an in-place shrink (0003)"
        )
    for i, old_f in enumerate(old_fields):
        new_f = new_fields[i]
        if old_f.get("name") != new_f.get("name"):
            raise SchemaHoldingRuleError(
                f"position {i}: field rename/reorder "
                f"{old_f.get('name')!r} -> {new_f.get('name')!r} (0003)"
            )
        if old_f.get("type") != new_f.get("type"):
            raise SchemaHoldingRuleError(
                f"position {i} ({old_f.get('name')!r}): type change "
                f"{old_f.get('type')!r} -> {new_f.get('type')!r} (0003)"
            )


def write_schema_sidecar(
    destination: Union[str, Path],
    document: Mapping[str, Any],
    *,
    backend: Optional[PathBackend] = None,
    force: bool = False,
    protect: bool = True,
) -> str:
    """Atomically write ``datapackage.json`` via PathBackend (P3).

    ``destination`` is either a station directory or a full path ending in
    ``datapackage.json``. Returns the path written (as used with the backend).

    When ``backend`` is None, uses :class:`LocalPathBackend` over the parent
    of the file (absolute local paths).

    If a sidecar already exists and ``force`` is False, enforces the 0003
    holding rule against the on-disk document.
    """
    dest = Path(destination)
    if dest.name == SCHEMA_FILENAME:
        directory = dest.parent
        file_name = SCHEMA_FILENAME
    else:
        directory = dest
        file_name = SCHEMA_FILENAME

    directory.mkdir(parents=True, exist_ok=True)
    abs_dir = directory.resolve()
    rel_or_abs = str(abs_dir / file_name)

    if backend is None:
        backend = LocalPathBackend()

    path_for_backend = rel_or_abs
    # Prefer path relative to a rooted backend when root is set
    root = getattr(backend, "root", None)
    if root is not None:
        try:
            path_for_backend = str((abs_dir / file_name).relative_to(Path(root).resolve()))
        except ValueError:
            path_for_backend = rel_or_abs

    if backend.exists(path_for_backend) and not force:
        try:
            existing_raw = backend.read_bytes(path_for_backend)
            existing = json.loads(existing_raw.decode("utf-8"))
            if isinstance(existing, dict):
                check_holding_rule(existing, document)
        except SchemaHoldingRuleError:
            raise
        except Exception as exc:
            logger.warning(
                "could not validate existing schema at %s (%s); proceeding",
                path_for_backend,
                exc,
            )

    payload = json.dumps(dict(document), indent=2, sort_keys=False).encode("utf-8")
    # Ensure we can overwrite a protected sidecar
    local_file = abs_dir / file_name
    if local_file.exists():
        try:
            os.chmod(local_file, _WRITABLE_MODE)
        except OSError:
            pass

    # Prefer create-if-absent only when missing; otherwise atomic replace
    if not backend.exists(path_for_backend):
        if not backend.create_if_absent(path_for_backend, payload):
            # raced: use write_atomic
            backend.write_atomic(path_for_backend, payload)
    else:
        backend.write_atomic(path_for_backend, payload)

    if protect:
        protect_schema_sidecar(local_file)

    logger.debug("wrote schema sidecar %s", path_for_backend)
    return path_for_backend


def protect_schema_sidecar(path: Union[str, Path]) -> None:
    """POSIX: make schema sidecar read-only (CONCURRENCY §5 mechanical note)."""
    p = Path(path)
    if not p.exists():
        return
    try:
        os.chmod(p, _PROTECTED_MODE)
    except OSError as exc:
        logger.warning("could not protect schema sidecar %s: %s", p, exc)


def is_schema_protected(path: Union[str, Path]) -> bool:
    """True if the file exists and has no write bits for owner/group/other."""
    p = Path(path)
    if not p.exists():
        return False
    mode = p.stat().st_mode
    return not bool(mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def read_schema_sidecar(
    destination: Union[str, Path],
    *,
    backend: Optional[PathBackend] = None,
) -> Optional[Dict[str, Any]]:
    """Read datapackage.json if present; None if missing."""
    dest = Path(destination)
    if dest.name != SCHEMA_FILENAME:
        dest = dest / SCHEMA_FILENAME
    path = str(dest.resolve())
    be = backend or LocalPathBackend()
    if not be.exists(path):
        # try relative
        if backend is not None and backend.exists(SCHEMA_FILENAME):
            path = SCHEMA_FILENAME
        elif not Path(path).exists():
            return None
    try:
        raw = be.read_bytes(path) if be.exists(path) else Path(path).read_bytes()
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None
