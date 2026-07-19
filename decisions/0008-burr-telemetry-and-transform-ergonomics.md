---
status: ratified
date: 2026-07-19
---

# 0008: Burr telemetry lesson and @transform ergonomics

## Context

Apache Burr is the closest philosophical neighbor to stations (immutable state
transforms, declared reads/writes, explicit transitions). The comparative
analysis lived only in consumer docs — cocli `docs/DESCRIPTION.md` and a
completed task-agent prototype — which decision 0005 forbids as normative homes.
This decision records the prior-art rationale in the stations repo.

## Decision

### 1. Borrow the ergonomics, not the runtime

From Burr, stations takes two surface lessons:

1. **`@action(reads=, writes=)` → `@transform(from_station=, to_station=)`**
   Decorator registration of pure model-to-model functions against typed
   stations. The decorated callable remains a structural
   `Transform` (PROTOCOLS.md §4) — the decorator registers, it does not
   reinterpret. Builder-validated graph assembly
   (`ApplicationBuilder.build()`) fails closed when stations are missing or
   types do not line up (Burr's ApplicationBuilder lesson).

2. **Telemetry / observability UI over formalism.** Burr users praise the
   telemetry UI more than the state-machine mechanism. Stations hold that
   property in a stronger form: state is *already* on disk as inspectable
   files, so an inspector is "render what's there," not "build
   instrumentation." Ship a read-only inspector CLI early.

### 2. Inspector is read-only and terminal-first

- `stations inspect` (package module `stations.inspect`) renders any
  conforming station root: per-station counts, age-of-oldest item, lease/claim
  status, and CURRENT/watermark for index stations.
- **Strictly read-only** — no repair, no GC (Compactor duties per
  CONCURRENCY §5).
- Terminal-first (Rich or plain text). A web UI is an explicit non-goal for
  v1; Burr's lesson was that observability matters, not that it needs a
  browser.
- Implementation discipline (from cocli FsAuditor lessons): stream +
  aggregate (never load whole trees as models); cache schema lookups per
  directory; separate structure-checks from content-checks.

### 3. Prior art and consumers

- **Prototype:** task-agent `ta dashboard` (completed task
  `build-station-inspector-cli-borrowing-burr-telemetry-ux`, commit e1cb121) —
  per-station counts, oldest-age, blocked-chain fold, Theme styling.
  Generalize station-walking onto `PathBackend`; do not re-derive the view
  design.
- **Normative home:** this decision + `python/src/stations/{transform,inspect}.py`.
  Consumer repos may cite this decision; they must not host the normative
  description (0005).
- cocli `docs/DESCRIPTION.md` remains a product-coupled comparison table;
  it should point here for the binding ergonomics/inspector decision.

### 4. What we deliberately do not borrow

- Burr's single-process in-memory state blob and opaque snapshot persistence.
- Builder as a runtime orchestrator — stations engines (`TransformEngine`,
  `Compactor`) own claim/lease and I/O; the decorator/builder only register
  and validate the pure graph.
- Served HTML telemetry.

## Consequences

- `stations.python` ships `@transform` + `ApplicationBuilder` and
  `stations inspect` without waiting for full S3 backends or engines (a
  minimal `LocalPathBackend` is enough for read-only inspect).
- Engines remain strangler Phase 3 (decision 0006); this decision does not
  pull engines forward.
- Vocabulary stays owned by GLOSSARY / PHYSICAL-CONTRACT / CONCURRENCY /
  PROTOCOLS — the inspector renders ratified terms only.

## See also

- [0005-packaging-and-reference-implementation.md](./0005-packaging-and-reference-implementation.md) (item 4 of implementation order)
- [spec/PROTOCOLS.md](../spec/PROTOCOLS.md) §4 Transforms
- task-agent completed: `build-station-inspector-cli-borrowing-burr-telemetry-ux`
- cocli (historical comparison): `docs/DESCRIPTION.md`
