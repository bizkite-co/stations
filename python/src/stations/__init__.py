"""Stations — typed file-path queue/WAL/index substrate (reference package).

Exposes Protocols, PathBackends (local + S3) with claim CAS helpers,
@transform + ApplicationBuilder, and a read-only inspector CLI. Engines
(TransformEngine / Compactor) arrive in a later strangler phase.
"""

from stations.backends import (
    LocalPathBackend,
    S3PathBackend,
    acquire_lease,
    content_etag,
    default_is_expired,
    try_create_lease,
    try_reclaim_lease,
)
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
    # backends / claim
    "LocalPathBackend",
    "S3PathBackend",
    "acquire_lease",
    "content_etag",
    "default_is_expired",
    "try_create_lease",
    "try_reclaim_lease",
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

__version__ = "0.3.0"
