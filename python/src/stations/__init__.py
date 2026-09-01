"""Stations — typed file-path queue/WAL/index substrate (reference package).

Exposes Protocols, PathBackends (local + S3) with claim CAS helpers,
queue/log/index edges, DefaultTransformEngine / DefaultCompactor,
@transform + ApplicationBuilder, and a read-only inspector CLI.
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
from stations.compactor import DefaultCompactor, last_write_wins_fold
from stations.edges import PathIndexEdge, PathLogEdge, PathQueueEdge, SimpleLease
from stations.engine import DefaultTransformEngine
from stations.protect import (
    PROTECTED_MODE,
    WRITABLE_MODE,
    is_protected,
    protect_path,
    unprotect_for_write,
)
from stations.schema import (
    SCHEMA_FILENAME,
    SchemaHoldingRuleError,
    SchemaWriteError,
    check_holding_rule,
    is_schema_protected,
    protect_schema_sidecar,
    read_schema_sidecar,
    write_schema_sidecar,
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
from stations.paths import (
    item_dir,
    phase_dir,
    relative_phase_shard_key,
    require_phases,
    shard_dir,
)
from stations.segments import (
    PartitionByDayOfMonth,
    PhaseRef,
    Phases,
    ShardByCharIndex,
    ShardByHash,
    ShardByPrefix,
    collect_phases,
    collect_shard,
    partition_by_day_of_month,
    phases,
    shard_by_char_index,
    shard_by_hash,
    shard_by_prefix,
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
    # engines / edges
    "DefaultTransformEngine",
    "DefaultCompactor",
    "last_write_wins_fold",
    "PathQueueEdge",
    "PathLogEdge",
    "PathIndexEdge",
    "SimpleLease",
    # ratified-artifact POSIX protect (CONCURRENCY §5)
    "PROTECTED_MODE",
    "WRITABLE_MODE",
    "is_protected",
    "protect_path",
    "unprotect_for_write",
    # schema sidecars
    "SCHEMA_FILENAME",
    "SchemaHoldingRuleError",
    "SchemaWriteError",
    "check_holding_rule",
    "is_schema_protected",
    "protect_schema_sidecar",
    "read_schema_sidecar",
    "write_schema_sidecar",
    # segment combinators (0010)
    "PhaseRef",
    "Phases",
    "ShardByHash",
    "ShardByPrefix",
    "ShardByCharIndex",
    "PartitionByDayOfMonth",
    "phases",
    "shard_by_hash",
    "shard_by_prefix",
    "shard_by_char_index",
    "partition_by_day_of_month",
    "collect_phases",
    "collect_shard",
    # path helpers (0010)
    "require_phases",
    "phase_dir",
    "shard_dir",
    "item_dir",
    "relative_phase_shard_key",
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

__version__ = "0.5.5"
