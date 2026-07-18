---
status: proposed
date: 2026-07-17
---

# 0002: Cross-repo identity — format binds now, registry deferred as an index station

## Context

Records move between stations, so a path written down today is stale the moment the record
transitions. [GLOSSARY § Cross-repo referencing](../GLOSSARY.md#cross-repo-referencing-identity-not-path)
already names the rule (reference by identity, never by path) but external review
(2026-07-17) correctly flagged what it leaves open: what a registry entry looks like, who
maintains it, and whether the registry is itself a station. A live instance of the
underlying defect exists: task-agent derives record identity from a mutable title
(its STATION-MAP gap #1).

## Decision

1. **The identity format binds now.** A record's identity is `repo-moniker#slug`. The slug
   is fixed at record creation and immutable thereafter; it MUST NOT be derived from any
   mutable attribute (title, status, location). File-per-object names derive from this
   identity ([spec/PHYSICAL-CONTRACT.md](../spec/PHYSICAL-CONTRACT.md) §2, P2).
2. **Recorded paths are caches.** Any consumer holding a path MUST tolerate it being
   stale and re-resolve by identity; nothing may treat a stored path as a source of truth.
3. **The registry, when built, is an index station — not a service.** Its entries are a
   fold of record-location facts, rebuildable by scanning the participating repos
   (replay), written by a single compactor under the standard protocol
   ([spec/CONCURRENCY.md](../spec/CONCURRENCY.md) §3). No central server: a derived file,
   synced and read like any other station. This answers "who maintains it" structurally —
   whichever repo hosts the registry station owns its compactor role.
4. **Resolution machinery is deferred** until a second consumer needs mechanical
   cross-repo resolution. Open when picked up: the entry schema, which repo hosts the
   station, and scan cadence. Until then resolution is manual, per the GLOSSARY.

## Consequences

- The part that "can't be left to the reference implementation" no longer is: the format
  and the paths-are-caches rule bind every consumer today; only resolution tooling waits.
- The registry adds no new machinery — it is expressible entirely inside the pattern it
  serves (an index with a watermark and one compactor), which is itself a useful
  validation that the pattern closes over its own infrastructure needs.
- task-agent's mutable-title identity is confirmed as a conformance gap against point 1,
  to be fixed in its own queue (METHOD step 7).
