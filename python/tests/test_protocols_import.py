"""Smoke tests: protocols package imports and exposes expected names."""

from __future__ import annotations

from typing import get_type_hints

import stations
from stations import protocols


def test_package_version() -> None:
    assert stations.__version__ == "0.1.0"


def test_protocol_names_exported() -> None:
    expected = {
        "Identity",
        "PathBackend",
        "Station",
        "Lease",
        "QueueEdge",
        "LogEdge",
        "IndexEdge",
        "Transform",
        "Fold",
        "Emission",
        "TransformEngine",
        "Compactor",
    }
    for name in expected:
        assert hasattr(protocols, name), name
        assert name in stations.__all__


def test_transform_is_callable_protocol() -> None:
    """A plain function is a structural Transform."""

    def double(x: int) -> int:
        return x * 2

    transform: protocols.Transform[int, int] = double
    assert transform(3) == 6


def test_queue_edge_protocol_has_claim_not_poll() -> None:
    """Stations vocabulary uses claim/complete (not poll/ack)."""
    hints = getattr(protocols.QueueEdge, "__annotations__", {})
    # Protocol methods live on the class dict
    assert "claim" in protocols.QueueEdge.__dict__
    assert "enqueue" in protocols.QueueEdge.__dict__
    assert "complete" in protocols.QueueEdge.__dict__
    assert "poll" not in protocols.QueueEdge.__dict__
