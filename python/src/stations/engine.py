"""TransformEngine: claim → pure transform → sink → complete (C4, C5, P6)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, TypeVar

logger = logging.getLogger(__name__)

T_in = TypeVar("T_in")
T_out = TypeVar("T_out")


class DefaultTransformEngine:
    """Reference TransformEngine. Owns the claim/lease cycle; transform stays pure."""

    def __init__(self, *, default_ttl_seconds: int = 900) -> None:
        self.default_ttl_seconds = default_ttl_seconds

    def run_once(
        self,
        *,
        source: Any,
        transform: Any,
        sink: Any,
        worker_id: str,
        emissions: Sequence[Any] = (),
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Claim one item, transform, write sink, complete. True if work done."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        claimed = source.claim(worker_id=worker_id, ttl_seconds=ttl)
        if claimed is None:
            return False
        item, lease = claimed
        trace_id = uuid.uuid4().hex
        logger.debug(
            "transform claim item_id=%s worker=%s trace=%s",
            getattr(lease, "item_id", "?"),
            worker_id,
            trace_id,
        )

        try:
            out = transform(item)
        except Exception as exc:
            logger.exception("transform failed trace=%s: %s", trace_id, exc)
            source.fail(item, lease, error=exc)
            return True

        # C4: past expiry → do not write terminal state (sink or complete)
        if _lease_expired(lease):
            logger.warning(
                "lease expired before terminal write item_id=%s trace=%s; skipping sink/complete",
                getattr(lease, "item_id", "?"),
                trace_id,
            )
            return True

        try:
            if hasattr(sink, "append"):
                sink.append(out)
            elif hasattr(sink, "enqueue"):
                sink.enqueue(out)
            else:
                raise TypeError("sink must be LogEdge (append) or QueueEdge (enqueue)")
        except Exception as exc:
            logger.exception("sink write failed trace=%s: %s", trace_id, exc)
            source.fail(item, lease, error=exc)
            return True

        if _lease_expired(lease):
            logger.warning(
                "lease expired after sink write item_id=%s trace=%s; not completing source",
                getattr(lease, "item_id", "?"),
                trace_id,
            )
            return True

        # Emissions: best-effort typed side outputs (decision 0001); non-fatal
        for em in emissions:
            try:
                _route_emission(em, out, trace_id=trace_id)
            except Exception as exc:
                logger.warning("emission failed trace=%s: %s", trace_id, exc)

        source.complete(item, lease, result=out)
        logger.debug("transform complete trace=%s", trace_id)
        return True


def _lease_expired(lease: Any) -> bool:
    expires = getattr(lease, "expires_at", None)
    if expires is None:
        return False
    now = datetime.now(tz=timezone.utc)
    if getattr(expires, "tzinfo", None) is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now > expires


def _route_emission(emission: Any, primary: Any, *, trace_id: str) -> None:
    """v1: log-only; full intake routing is product-side until multi-machine wiring."""
    logger.info(
        "emission declared type=%s to=%s file=%s trace=%s primary_type=%s",
        getattr(emission, "type", None),
        getattr(emission, "to", None),
        getattr(emission, "file", None),
        trace_id,
        type(primary).__name__,
    )
