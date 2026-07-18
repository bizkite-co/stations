"""Stations — typed file-path queue/WAL/index substrate (reference package).

Phase 1 exposes :mod:`stations.protocols` only. Runtime engines land later;
see decisions/0005 in the repo root.
"""

from stations.protocols import (
    Compactor,
    Emission,
    Fold,
    Identity,
    IndexEdge,
    Lease,
    LogEdge,
    PathBackend,
    QueueEdge,
    Station,
    Transform,
    TransformEngine,
)

__all__ = [
    "Compactor",
    "Emission",
    "Fold",
    "Identity",
    "IndexEdge",
    "Lease",
    "LogEdge",
    "PathBackend",
    "QueueEdge",
    "Station",
    "Transform",
    "TransformEngine",
]

__version__ = "0.1.0"
