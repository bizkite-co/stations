"""POSIX mechanical protect for ratified artifacts (CONCURRENCY §5).

This is a *speed bump* against accidental local overwrites (ad-hoc scripts,
open(..., \"w\")), not a distributed lock. Multi-node safety remains CAS /
single-writer on the commit path.

Use for any ratified path: datapackage.json, CURRENT, checkpoints, index USVs.
Schema-specific names in :mod:`stations.schema` are thin aliases for
datapackage.json only.
"""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# Owner/group/other read-only after successful write (CONCURRENCY §5 note).
PROTECTED_MODE = 0o444
# Mode used so the same principal can rewrite (tmp+rename or open w).
WRITABLE_MODE = 0o644


def protect_path(path: Union[str, Path]) -> None:
    """Make an existing file read-only (0o444). No-op if missing."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return
    try:
        os.chmod(p, PROTECTED_MODE)
    except OSError as exc:
        logger.warning("could not protect path %s: %s", p, exc)


def unprotect_for_write(path: Union[str, Path]) -> None:
    """Ensure the file is owner-writable before replace/rewrite. No-op if missing."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return
    try:
        os.chmod(p, WRITABLE_MODE)
    except OSError as exc:
        logger.warning("could not unprotect path for write %s: %s", p, exc)


def is_protected(path: Union[str, Path]) -> bool:
    """True if the file exists and has no write bits for owner/group/other."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False
    mode = p.stat().st_mode
    return not bool(mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
