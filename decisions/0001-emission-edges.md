---
status: proposed
date: 2026-07-14
---

# 0001: Emission edges — one primary output, N typed secondary emissions

## Context

A transform in this pattern has exactly one primary output type — the thing its
[portable task](../GLOSSARY.md#portable-task) done_check verifies. But real
task-handling legitimately produces artifacts beyond that primary subject: policy
proposals, ADRs, strategy notes, spawned subtasks. Without a declared mechanism, these
either get lost (mentioned in passing, never persisted) or get written directly into
some other system's ratified station (violating the single-writer rule).

Surfaced during cocli CLI-consolidation work (2026-07-13), then found to have been
independently anticipated by `task-agent`'s own `create-policies-queue` task
(created 2026-07-02) — a `policies/` queue with a discriminated-union model, populated by
users or agents, consumed by a processor that updates documents/lint rules/validators.
Two consumers converged on the same need from different directions before either had a
name for it.

## Decision

A transform may declare secondary emissions via `emits: [{type, file, to}]` in its
record's frontmatter. Each declared emission is routed, at the transform's completion, to
the **intake/proposal station** of the target system — never directly into that system's
ratified/terminal station. A two-way traceability link is stamped (`emitted_by:` on the
emitted record; the attachment listing stays on the source).

Decisions and policies are not two mechanisms: a decision is the fact (WAL-shaped,
append-only, superseded-not-edited); a policy is the fold of accepted decisions
(index-shaped, present-tense, rebuildable). One `decisions/proposed/` intake station, with
a `kind:` field (`policy-rule`, `strategy`, `architecture`, ...) discriminating them,
serves both — mirroring the log/index relationship already established in the trichotomy.

## Consequences

- `task-agent`'s `create-policies-queue` should implement against this shape rather than
  invent its own discriminated union independently — its existing model is likely the
  concrete `kind:` field this decision calls for.
- The reference implementation (not yet built) must expose `emits:` as a first-class part
  of the transform contract, or explicitly defer it to v2 — but the invariant (one primary
  output; emissions only into intake stations) must hold from v1 regardless, so early
  consumers don't invent incompatible side-channels.
- See [GLOSSARY.md § Emission edge](../GLOSSARY.md#emission-edge) for the full definition.

## Example (added 2026-07-17, prompted by external review)

An emitting record — a Markdown+frontmatter task in `task-agent` — as its transform
completes:

```yaml
---
id: task-agent#extract-data-py-logic
status: completed
transform:
  context: cocli
  input_type: commands/data.py with inline business logic
  output_type: DataSyncService + thin Typer adapter
  done_check: "pytest tests/unit/test_data_sync_inspection.py -q"
emits:
  - type: decision
    kind: policy-rule
    file: emissions/no-rich-in-application-tier.md
    to: stations#decisions/proposed
---
```

The completion transition routes the attachment to the declared intake station, stamping
the back-link; the emitted record as it arrives in the intake station:

```yaml
---
kind: policy-rule
status: proposed
date: 2026-07-17
emitted_by: task-agent#extract-data-py-logic
---

# Application-tier services must not import Rich

(proposed rule text…)
```

Note that `to:` and `emitted_by:` are identities (`repo#slug`), not paths — the emitted
record will move (`proposed/` → `accepted/`), and identity is what survives the move
(GLOSSARY § Cross-repo referencing; decision 0002).

## Intake stations have ordinary edge roles — nothing is inherited

Question raised by the same review: do intake stations carry their own edge roles or
inherit them from the target station they feed? Answer: an intake station is a station
like any other, and roles attach per-edge as always. To the target machine's ratification
transition it is a **queue** (proposals claimed, driven to accepted/rejected terminal
states); to an auditor it is the tail of a decision **log**. It inherits nothing from the
ratified station downstream of it — "inheritance" would re-attach roles to stations rather
than edges, contradicting GLOSSARY § Edge role.

Corollaries: a transform MAY emit into the intake of the very machine it belongs to
(self-spawned subtasks are exactly this); and two transforms MAY emit conflicting
proposals — conflict resolution is the ratification transition's job, which is the point
of routing through intake rather than writing ratified state directly.

## See also

- [consumers/task-agent.md](../consumers/task-agent.md)
- cocli task `design-spec-for-reusable-typed-file-path-queue-transformer-library-extracted-from-cocli`,
  design decision #7
