---
status: ratified
date: 2026-07-17
---

# 0006: Strangler migration — cocli as consumer #1 of `stations`

## Context

cocli already implements most of the on-disk contract in product form
(ADR-010/011/013, `wal-strategy.md`, `compaction-and-checkpointing.md`,
filesystem/S3 queues). The design-spec goal is extraction, not redesign. The
falsifiability test from METHOD.md: once the reference implementation exists,
refactoring cocli onto it should require **no on-disk format change**.

## Decision — strangler phases

### Phase 0 — Contract freeze (done / in progress)

- On-disk contract documented in `stations/spec/` (PHYSICAL + CONCURRENCY).
- Vocabulary in GLOSSARY; consumers/cocli.md documents the three-tier cut line:
  only `cocli/core/` queue/WAL/index primitives are extraction candidates;
  `application/` and `services/` stay product code.

### Phase 1 — Protocols as dependency (no behavior change)

1. Scaffold `stations/python` with `stations.protocols` only (decision 0005).
2. cocli depends on `stations` (path or git).
3. Annotate existing cocli types as structural subtypes:
   - `CampaignQueueProtocol` / filesystem & S3 queues → `QueueEdge`-compatible
   - compactors (`CompactManager`, domain/email index managers) → `Compactor`-shaped
   - pure model-to-model functions (ADR-001) → `Transform`-shaped
4. mypy verifies structural compatibility. **No runtime switch yet.**

### Phase 2 — Backend claim primitive unification

1. Implement `stations.backends` (local + S3): `PathBackend` + claim CAS.
2. Re-point cocli queue claim/release through the stations backend, keeping
   cocli path layouts and file names unchanged.
3. Delete duplicated claim code paths only when tests prove equivalence.

### Phase 3 — Engines replace product loops

1. Queue workers: `TransformEngine.run_once` drives claim→transform→complete
   for one queue family at a time (start with a non-critical queue).
2. Compaction: `Compactor.compact_once` wraps existing fold logic for one index
   (e.g. email or domain) before generalizing to GM prospects.
3. Each cutover is a thin adapter in `cocli/core/` that calls stations engines;
   Typer commands and application services stay product-side.

### Phase 4 — Delete the husk

1. When no cocli-specific reimplementation remains for a primitive, remove the
   cocli copy.
2. cocli `docs/adr/010–013` remain historical; `stations/spec/` is normative.
3. Inspector: generalize from task-agent / cocli audit into `stations inspect`
   (separate task; not a migration blocker).

## Non-goals of the strangler

- **No on-disk migration.** Path grammar, USV, leases, CURRENT pointers stay.
- **No rewrite of application/services.** Those are product orchestration
  (three-tier rule); they *call* stations, they never move into stations.
- **No DuckDB replacement.** DuckDB remains the read/analytics engine.
- **No WASI requirement for cutover** (decision 0007).

## Success criteria

| Gate | Test |
| :--- | :--- |
| Phase 1 | mypy: cocli queue/compactor types satisfy `stations.protocols` |
| Phase 2 | Existing queue integration tests pass against stations backend |
| Phase 3 | One queue + one index compacted solely via stations engines in CI |
| Phase 4 | No duplicate claim/compact implementation left in cocli.core |

## Coordination with the CLI consolidation epic

- Phase 4/5 service extractions in cocli **should** type-hint against
  `stations.protocols` once Phase 1 is complete — avoids double refactor.
- Service extraction does **not** wait for Phase 2–4. Thin Typer adapters over
  application services continue independently (already underway).

## See also

- [consumers/cocli.md](../consumers/cocli.md) — extraction cut line
- [spec/PROTOCOLS.md](../spec/PROTOCOLS.md)
- [0005-packaging-and-reference-implementation.md](./0005-packaging-and-reference-implementation.md)
- [0007-disposition-overlapping-cocli-tasks.md](./0007-disposition-overlapping-cocli-tasks.md)
