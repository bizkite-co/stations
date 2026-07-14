# Consumer: task-agent

Repo: `~/repos/task-agent`

**Status:** dogfood consumer #2; first system formally mapped with [METHOD.md](../METHOD.md).

**Primary artifact:** `docs/tasks/pending/ratify-station-map-declaring-task-agent-as-a-typed-file-path-station-system/STATION-MAP.md`
— pending ratification. Once ratified, moves to `docs/STATION-MAP.md` in that repo and
becomes the authoritative instance document; this onramp should be updated to link there
instead of the pending draft.

**Conformance gaps identified by the mapping** (see STATION-MAP.md §5 for full detail):
identity derived from mutable title, edge-role data stored as body prose instead of
frontmatter, non-atomic record updates, station store excluded from its own durability
(`.task-agent` gitignored), edge-type conflation (`blocked_by` vs `subtask_of` migration
in progress), undeclared `mr/` station, undeclared `AuditLog` role (telemetry vs WAL),
unproven index rebuildability.

**Related pending tasks in task-agent's own queue:**
- `build-station-inspector-cli-borrowing-burr-telemetry-ux` — the Observability surface
  (see GLOSSARY.md, and design decision in cocli's spec task) prototyped here first,
  single-repo, before generalizing.
- `create-a-global-task-agent-registry-of-repos-and-tasks` — the cross-repo identity
  registry (see GLOSSARY.md § Cross-repo referencing).
- `create-policies-queue` — task-agent's independently-conceived version of
  [Emission edges](../GLOSSARY.md#emission-edge); needs reconciling with the glossary's
  `decisions/proposed/` + `kind:` discriminator design, not built as a second mechanism.
