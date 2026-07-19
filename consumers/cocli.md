# Consumer: cocli

Repo: `~/repos/company-cli` (worktree in use: `.gwt/commands`)

**Status:** primary dogfood consumer; origin of the pattern. Not yet formally mapped
against [METHOD.md](../METHOD.md) as a standalone exercise — the pattern was extracted
*from* cocli's existing structure rather than mapped *onto* it, so cocli's own
`docs/DESCRIPTION.md` is the closest thing to a station map today, written in
product-coupled language.

**Primary artifacts:**
- `docs/DESCRIPTION.md` — the original, product-coupled telling of this pattern.
- `docs/adr/010`, `011`, `012`→`013` — the concrete queue/lease/index implementations this
  pattern was distilled from.
- `docs/wal-strategy.md`, `docs/architecture/compaction-and-checkpointing.md` — the
  LSM-tree-shaped index maintenance this pattern's trichotomy formalizes.

**Open task:** `design-spec-for-reusable-typed-file-path-queue-transformer-library-extracted-from-cocli`
(cocli's task queue) — the reference-implementation extraction. As of 2026-07-14 its
completion criteria target `stations/decisions/` (this repo), not cocli's own `docs/adr/`;
cocli's ADR set stays product-specific and does not carry the spec itself.

**Do not duplicate here:** cocli's actual station declarations (paths, Pydantic models,
`datapackage.json` schemas) are product-specific and stay in cocli. Only the vocabulary and
method are shared.

**The extraction cut line is three-tier, not two-tier.** Surfaced 2026-07-15 after a
reviewer read cocli's `cocli/application/` vs `cocli/services/` split as evidence the
extraction boundary was getting fuzzy (e.g. `ClusterService` placed in `services/` while
most new Phase-5 extractions go to `application/`). It isn't fuzzy — it's two separate
boundaries that happen to look like one:

```
cocli/core/                      ← only extraction candidate (→ stations substrate)
cocli/application/ + services/   ← both product-specific; stay in cocli forever
cocli/commands/                  ← thin Typer adapters over the product tiers
```

1. **Extraction axis** — `cocli/core/` holds the queue/WAL/index primitives (cache, audit,
   DFQ machinery) this pattern was distilled from. **This is the only tier that eventually
   moves to `stations`.** Neither `application/` nor `services/` is an extraction candidate.
2. **Intra-product axis** — `cocli/application/` (domain/orchestration) vs
   `cocli/services/` (low-level infra drivers — SSH, Docker, S3, WAL ops). Both are
   product-specific and stay in cocli permanently. The split between them is
   orchestration-vs-driver responsibility *within* cocli, not extractability.
   `ClusterService` (SSH cluster ops, `docker` commands) is infra-driver work, same tier
   as the S3/WAL drivers already in `services/` — correctly placed, not inconsistent.

Rule of thumb: only code in `core/`'s typed-path-queue substrate is ever a candidate for
this repo. Everything in `application/` or `services/` is cocli product code regardless of
which of those two directories a module lives in. When reviewing placement: ask extraction
first (core vs product), then — only if product — ask orchestration vs infra-driver.

Implementer-facing copy of the same rule (directory tree + import-linter) lives in the
cocli worktree: `CLAUDE.md` ("Three-tier layering") and `docs/cli/target-tree.md` §3.1.
This consumer onramp is the stations-repo source of truth for *what extracts*.

**Strangler migration** into the `stations` reference package:
[decisions/0006-strangler-migration-from-cocli.md](../decisions/0006-strangler-migration-from-cocli.md).
Protocol surface to target: [spec/PROTOCOLS.md](../spec/PROTOCOLS.md). Overlapping cocli
tasks (build-protocols, WASI data access, WASI compaction) are disposed in
[decisions/0007-disposition-overlapping-cocli-tasks.md](../decisions/0007-disposition-overlapping-cocli-tasks.md).

**Inspector + `@transform` ergonomics** (decision
[0008](../decisions/0008-burr-telemetry-and-transform-ergonomics.md)): cocli consumes
via the pinned `stations` dependency. Thin adapter: `cocli stations inspect`
(`cocli/commands/stations_cmd.py`) — resolves campaign queue paths and calls
`stations.inspect` (read-only). Proof root: a live campaign queue such as
`campaigns/<campaign>/queues/to-call` or `gm-list`.
