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
