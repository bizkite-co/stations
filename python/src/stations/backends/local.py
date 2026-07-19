"""Local filesystem PathBackend (decision 0005 step 2, inspect-minimal subset).

Implements the full PathBackend protocol so engines can use it later; the
inspector only needs list / exists / read_bytes / mtime.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator, Optional


class LocalPathBackend:
    """PathBackend over a local directory tree.

    Paths passed to methods are absolute or relative to ``root``. When
    ``root`` is set, relative paths are resolved under it; absolute paths
    are used as-is (must still be under root when root is set, for safety).
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
        """Stream path strings under prefix (files and directories, relative to root).

        Yields paths as posix strings. Directories end with ``/``. Streaming —
        does not materialize the full tree.
        """
        base = self._resolve(prefix) if prefix not in ("", ".") else (
            self.root if self.root is not None else Path(".")
        )
        if not base.exists():
            return
        if base.is_file():
            yield self._rel(base)
            return
        # os.walk is generator-based; we yield one path at a time
        for dirpath, dirnames, filenames in os.walk(base, topdown=True):
            dpath = Path(dirpath)
            # yield directory entries under prefix (skip the root itself when empty walk)
            for name in sorted(dirnames):
                child = dpath / name
                yield self._rel(child) + "/"
            for name in sorted(filenames):
                child = dpath / name
                yield self._rel(child)

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_dir():
            target.rmdir()
        elif target.exists():
            target.unlink()

    def create_if_absent(self, path: str, data: bytes) -> bool:
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
        """Local CAS: etag is ignored for v0 local (always replace if exists or create).

        True always after atomic write. Full mtime/inode etag matching is a
        later refinement; local rename-over is already atomic.
        """
        del etag  # reserved for S3 / future local etag
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
