---
status: proposed
date: 2026-07-17
---

# 0007: Disposition of overlapping cocli tasks (protocols, WASI)

## Context

Three cocli tasks predate the `stations` extraction and substantially overlap this
design-spec. The design-spec completion criteria require an explicit disposition so
they are not implemented as competing mechanisms.

| cocli task | Original intent |
| :--- | :--- |
| `build-protocols-for-data-access-readwrite-abstractions` | `USVReaderProto`, `WALWriterProto`, `IndexOpProto`, `ClusterSyncProto` in `cocli/core/protocols.py` |
| `design-and-implement-wasi-based-data-access-service` | WASI worker hash-bound exclusive writers via datapackage |
| `implement-wasi-compaction-service-with-read-only-schema-protection` | WASI compactor with exclusive schema write rights |

All three currently declare `blocked_by` this design-spec task.

## Decision

### 1. `build-protocols-for-data-access-…` → **re-scope, do not duplicate**

- **Superseded as a cocli-local design.** The Protocol surface is
  [spec/PROTOCOLS.md](../spec/PROTOCOLS.md) / `stations.protocols`.
- **Re-scope the cocli task** to: *adapt cocli implementations to satisfy
  `stations.protocols`* (strangler Phase 1, decision 0006). Drop
  `ClusterSyncProto` from the stations substrate — rsync/gossip are product
  transport, not station primitives.
- Deliverable becomes: cocli modules annotated/verified against stations
  Protocols; optional thin shims in `cocli/core/` if structural mismatch
  remains. **No parallel `cocli/core/protocols.py` protocol zoo.**

### 2. `design-and-implement-wasi-based-data-access-service` → **defer; optional enforcement**

- Single-writer is already specified without WASI: advisory lock + CAS on
  `CURRENT` ([CONCURRENCY.md](../spec/CONCURRENCY.md) §4, C12). Safety does not
  depend on a process sandbox.
- WASI hash-pinned writers (datapackage `wasmer: sha256:…`) are a **future
  hardened deployment option** for multi-tenant or untrusted-worker settings —
  not a v1 requirement and not on the critical path for extraction.
- **Disposition:** demote to a research / v2 spike in the *stations* queue (or
  leave pending in cocli with explicit `blocked_by: stations-v2-wasi-enforcement`
  once such a task exists). Do not implement as a cocli-only service that
  redefines single-writer.

### 3. `implement-wasi-compaction-service-with-read-only-schema-protection` → **absorb intent, drop WASI**

- The real defect (schema drift via non-canonical writes) is addressed by:
  - P1 / decision 0003 holding rule (no in-place field-list change with live readers)
  - Single-writer on index commit (CONCURRENCY §4)
  - Schema sidecars written only through station declaration / compactor paths
- **Disposition:** close or rewrite as *enforce schema writes through stations
  Compactor / Station declaration APIs in cocli* once strangler Phase 3 covers
  the relevant index. WASI filesystem permissions are not required for v1.

## Summary table

| Task | Disposition | Owner after this decision |
| :--- | :--- | :--- |
| build-protocols-… | Re-scope → implement `stations.protocols` in cocli | cocli strangler Phase 1 |
| WASI data access | Defer to v2 optional enforcement | stations (future), not cocli-critical |
| WASI compaction / schema protection | Absorb into contract + strangler; no WASI in v1 | stations CONCURRENCY + cocli Phase 3 |

## Consequences

- cocli task queue should update these three tasks' bodies to link here so agents
  do not re-open competing designs.
- Nothing in v1 of the reference implementation depends on WASI, Wasmer, or
  hash-pinned binaries.
- Protocol work is not blocked on any WASI design.

## See also

- [spec/PROTOCOLS.md](../spec/PROTOCOLS.md)
- [0006-strangler-migration-from-cocli.md](./0006-strangler-migration-from-cocli.md)
- cocli `docs/DESCRIPTION.md` (historical product-coupled telling)
