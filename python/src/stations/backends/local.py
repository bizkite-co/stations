"""Local filesystem PathBackend with claim-grade CAS primitives (C1, P3).

create-if-absent: ``open(O_CREAT|O_EXCL)``.
write_atomic / replace: tmp → fsync → rename on the same filesystem (P3).
replace_if_match: read current bytes, compare etag, then atomic rename-over.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator, Optional

from stations.backends.etag import content_etag


class LocalPathBackend:
    """PathBackend over a local directory tree.

    Paths passed to methods are absolute or relative to ``root``. When
    ``root`` is set, relative paths are resolved under it; absolute paths
    must still resolve under root (safety).
    """

    def __init__(self, root: Optional[str | Path] = None) -> None:
        self.root: Optional[Path] = Path(root).resolve() if root is not None else None

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            resolved = p.resolve()
        elif self.root is not None:
            resolved = (self.root / p).resolve()
        else:
            resolved = p.resolve()
        if self.root is not None:
            try:
                resolved.relative_to(self.root)
            except ValueError as exc:
                raise PermissionError(
                    f"path {path!r} escapes backend root {self.root}"
                ) from exc
        return resolved

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def etag(self, path: str) -> Optional[str]:
        """Content etag (sha256) of the current file, or None if missing."""
        target = self._resolve(path)
        if not target.is_file():
            return None
        return content_etag(target.read_bytes())

    def write_atomic(self, path: str, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".tmp-", dir=str(target.parent), suffix=".part"
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def list(self, prefix: str) -> Iterator[str]:
        """Stream path strings under prefix. Directories end with ``/``."""
        base = (
            self._resolve(prefix)
            if prefix not in ("", ".")
            else (self.root if self.root is not None else Path("."))
        )
        if not base.exists():
            return
        if base.is_file():
            yield self._rel(base)
            return
        for dirpath, dirnames, filenames in os.walk(base, topdown=True):
            dpath = Path(dirpath)
            for name in sorted(dirnames):
                yield self._rel(dpath / name) + "/"
            for name in sorted(filenames):
                yield self._rel(dpath / name)

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_dir():
            target.rmdir()
        elif target.exists():
            target.unlink()

    def create_if_absent(self, path: str, data: bytes) -> bool:
        """Test-and-set via O_CREAT|O_EXCL (CONCURRENCY §1). True on create."""
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(target), flags, 0o644)
        except FileExistsError:
            return False
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        except Exception:
            try:
                target.unlink()
            except OSError:
                pass
            raise
        return True

    def replace_if_match(
        self, path: str, data: bytes, *, etag: Optional[str]
    ) -> bool:
        """CAS replace: succeed only if current content etag matches (C1, C3).

        Uses content sha256 as the etag. Atomic rename-over after the check.
        Missing path → False (use create_if_absent to create).
        ``etag=None`` is treated as unconditional replace of an existing file
        (still fails if missing).
        """
        target = self._resolve(path)
        if not target.is_file():
            return False
        if etag is not None:
            current = target.read_bytes()
            if content_etag(current) != etag:
                return False
        self.write_atomic(path, data)
        return True

    def mtime(self, path: str) -> Optional[float]:
        """Optional extension used by the inspector for oldest-item age."""
        target = self._resolve(path)
        try:
            return target.stat().st_mtime
        except OSError:
            return None

    def _rel(self, path: Path) -> str:
        if self.root is not None:
            try:
                return path.resolve().relative_to(self.root).as_posix()
            except ValueError:
                return path.resolve().as_posix()
        return path.resolve().as_posix()
