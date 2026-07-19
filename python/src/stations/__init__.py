"""Stations — typed file-path queue/WAL/index substrate (reference package).

Exposes Protocols (Phase 1), a minimal LocalPathBackend, @transform +
ApplicationBuilder, and a read-only inspector CLI. Engines
(TransformEngine / Compactor) land in a later strangler phase.
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
from stations.station import StationDecl
from stations.transform import (
    Application,
    ApplicationBuilder,
    GraphValidationError,
    TransformRegistrationError,
    TransformSpec,
    get_transform,
    registered_transforms,
    transform,
)

__all__ = [
    # protocols
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
    # concrete / ergonomics
    "StationDecl",
    "Application",
    "ApplicationBuilder",
    "GraphValidationError",
    "TransformRegistrationError",
    "TransformSpec",
    "get_transform",
    "registered_transforms",
    "transform",
]

__version__ = "0.2.0"
