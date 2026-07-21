"""Compactor: six-step fold + CAS CURRENT (CONCURRENCY §3–§4, C6–C13)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from stations.backends.claim import acquire_lease
from stations.backends.etag import content_etag

logger = logging.getLogger(__name__)


class DefaultCompactor:
    """Reference Compactor for PathIndexEdge + LogEdge sources.

    Requires ``index`` to expose ``backend``, ``root``, and CURRENT helpers
    (see :class:`stations.edges.PathIndexEdge`). Fold is pure (C7, C14).
    """

    def __init__(
        self,
        *,
        lock_ttl_seconds: int = 600,
        consuming: bool = True,
    ) -> None:
        self.lock_ttl_seconds = lock_ttl_seconds
        self.consuming = consuming

    def compact_once(
        self,
        *,
        sources: Sequence[Any],
        index: Any,
        fold: Any,
        compactor_id: str,
    ) -> bool:
        backend = getattr(index, "backend", None)
        root = getattr(index, "root", None)
        if backend is None or root is None:
            raise TypeError(
                "DefaultCompactor requires index with .backend and .root "
                "(PathIndexEdge)"
            )

        lock_path = f"{str(root).rstrip('/')}/compactor.lock"
        now = datetime.now(tz=timezone.utc)
        lock_body = json.dumps(
            {
                "worker_id": compactor_id,
                "claimed_at": now.isoformat(),
                "expires_at": (
                    now + timedelta(seconds=self.lock_ttl_seconds)
                ).isoformat(),
                "attempt": 1,
            }
        ).encode("utf-8")

        # C12: advisory lock for liveness only
        if not acquire_lease(backend, lock_path, lock_body):
            logger.info("compactor lock held; skipping cycle id=%s", compactor_id)
            return False

        try:
            return self._compact_body(
                sources=sources,
                index=index,
                fold=fold,
                compactor_id=compactor_id,
                backend=backend,
                root=str(root).rstrip("/"),
            )
        finally:
            # Best-effort lock release (expiry also reclaims)
            try:
                if backend.exists(lock_path):
                    raw = backend.read_bytes(lock_path)
                    data = json.loads(raw.decode("utf-8"))
                    if data.get("worker_id") == compactor_id:
                        backend.delete(lock_path)
            except Exception as exc:
                logger.debug("lock release skipped: %s", exc)

    def _compact_body(
        self,
        *,
        sources: Sequence[Any],
        index: Any,
        fold: Any,
        compactor_id: str,
        backend: Any,
        root: str,
    ) -> bool:
        # 1. Read CURRENT
        meta = None
        if hasattr(index, "read_current_meta"):
            meta = index.read_current_meta()
        current_path = f"{root}/CURRENT"
        generation = 0
        if meta and isinstance(meta, dict):
            generation = int(meta.get("generation") or 0)

        # 2. Enumerate sources beyond watermark
        watermark = index.watermark() if hasattr(index, "watermark") else None
        source_records: List[Any] = []
        source_paths: List[str] = []
        for src in sources:
            # Prefer path enumeration when available for post-commit delete
            src_root = getattr(src, "root", None)
            if src_root is not None and backend is getattr(src, "backend", backend):
                for path in backend.list(str(src_root)):
                    if path.endswith("/") or path.endswith("datapackage.json"):
                        continue
                    name = path.rsplit("/", 1)[-1]
                    if _past_watermark(name, path, watermark):
                        try:
                            raw = backend.read_bytes(path)
                            rec = src.deserialize(raw) if hasattr(src, "deserialize") else raw
                            source_records.append(rec)
                            source_paths.append(path)
                        except Exception as exc:
                            # C6: skip non-conforming, never fold/delete
                            logger.warning("C6 skip %s: %s", path, exc)
            else:
                for rec in src.iter_beyond(watermark):
                    source_records.append(rec)

        if not source_records and generation > 0:
            # Nothing new; still ok to short-circuit
            logger.debug("no source records beyond watermark; idle")
            return False

        # Include committed generation in fold input (hybrid base)
        base = index.read_current() if hasattr(index, "read_current") else None
        fold_input: List[Any] = []
        if base is None:
            pass
        elif isinstance(base, (list, tuple)):
            fold_input.extend(base)
        else:
            fold_input.append(base)
        fold_input.extend(source_records)

        # 3. Fold (pure)
        folded = list(fold(fold_input))
        new_gen = generation + 1
        checkpoint_name = f"checkpoint.{new_gen:06d}.jsonl"
        checkpoint_path = f"{root}/{checkpoint_name}"
        body = b"".join(
            (
                (
                    index.serialize_record(r)
                    if hasattr(index, "serialize_record")
                    else json.dumps(r, default=str).encode("utf-8")
                )
                + b"\n"
            )
            for r in folded
        )
        backend.write_atomic(checkpoint_path, body)

        # 4. COMMIT: CAS CURRENT
        new_meta: Dict[str, Any] = {
            "generation": new_gen,
            "checkpoint": checkpoint_name,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "compactor_id": compactor_id,
            "mode": "consuming" if self.consuming else "retained",
            "folded": list(source_paths) if not self.consuming else None,
            "content_hash": content_etag(body),
        }
        new_bytes = json.dumps(new_meta, sort_keys=True).encode("utf-8")
        if backend.exists(current_path):
            etag = None
            if hasattr(index, "current_etag"):
                etag = index.current_etag()
            elif hasattr(backend, "etag"):
                etag = backend.etag(current_path)
            else:
                etag = content_etag(backend.read_bytes(current_path))
            ok = backend.replace_if_match(current_path, new_bytes, etag=etag)
            if not ok:
                # C10: abandon — delete our unreferenced generation
                logger.warning("CURRENT CAS lost; abandoning gen=%s", new_gen)
                try:
                    backend.delete(checkpoint_path)
                except Exception:
                    pass
                return False
        else:
            if not backend.create_if_absent(current_path, new_bytes):
                # Race on first CURRENT
                try:
                    backend.delete(checkpoint_path)
                except Exception:
                    pass
                return False

        # 5. Delete folded sources (consuming mode only; C9, C13)
        if self.consuming:
            for path in source_paths:
                try:
                    backend.delete(path)
                except Exception as exc:
                    logger.warning("post-commit source delete %s: %s", path, exc)

        # 6. GC old generations (lazy): drop unreferenced checkpoints
        self._gc_old_checkpoints(backend, root, keep=checkpoint_name)

        logger.info(
            "compacted gen=%s records_in=%s records_out=%s id=%s",
            new_gen,
            len(fold_input),
            len(folded),
            compactor_id,
        )
        return True

    def _gc_old_checkpoints(self, backend: Any, root: str, *, keep: str) -> None:
        for path in list(backend.list(root)):
            name = path.rsplit("/", 1)[-1]
            if name.startswith("checkpoint.") and name != keep:
                # Only delete if not referenced — we only keep current
                try:
                    backend.delete(path)
                except Exception:
                    pass


def _past_watermark(name: str, path: str, watermark: Optional[object]) -> bool:
    if watermark is None:
        return True
    if isinstance(watermark, (list, set, tuple)):
        return name not in watermark and path not in watermark
    if isinstance(watermark, str):
        return name != watermark and path != watermark
    if isinstance(watermark, int):
        # generation watermark: all present sources are beyond committed fold
        return True
    return True


def last_write_wins_fold(
    records: Any,
    *,
    key_fn: Any = None,
    version_fn: Any = None,
) -> Any:
    """Default C7 fold: last-write-wins by identity + version stamp.

    Returns a callable suitable as ``Fold``.
    """

    def _key(r: Any) -> str:
        if key_fn:
            return str(key_fn(r))
        if isinstance(r, dict):
            for k in ("id", "email", "domain", "key", "place_id"):
                if k in r:
                    return str(r[k])
        for attr in ("key", "id", "email", "domain", "place_id"):
            if callable(getattr(r, "key", None)) and attr == "key":
                try:
                    return str(r.key())
                except Exception:
                    pass
            val = getattr(r, attr, None)
            if val is not None and not callable(val):
                return str(val)
        return content_etag(json.dumps(r, default=str, sort_keys=True).encode())

    def _ver(r: Any) -> str:
        if version_fn:
            return str(version_fn(r))
        if isinstance(r, dict):
            for k in ("updated_at", "last_seen", "version", "found_at"):
                if k in r and r[k] is not None:
                    return str(r[k])
        for attr in ("updated_at", "last_seen", "version"):
            val = getattr(r, attr, None)
            if val is not None:
                return str(val)
        return ""

    def fold(records_in: Any) -> Any:
        best: Dict[str, Any] = {}
        for r in records_in:
            k = _key(r)
            if k not in best or _ver(r) >= _ver(best[k]):
                # ties: lexicographic on content for determinism (C7)
                if k in best and _ver(r) == _ver(best[k]):
                    a = json.dumps(r, default=str, sort_keys=True)
                    b = json.dumps(best[k], default=str, sort_keys=True)
                    if a < b:
                        continue
                best[k] = r
        return [best[k] for k in sorted(best.keys())]

    return fold
