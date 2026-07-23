---
status: ratified
date: 2026-07-23
---

# 0009: Field-update (patch) records as first-class log facts

## Context

Concurrent writers often know only a *slice* of an entity: one worker updates a phone
number while another updates an address for different reasons. A full-record overwrite
of the living entity file loses the other writer's field. The same class of problem
appears in task-agent as heading-addressed task patches versus full-body replace.

The glossary defines **Transform** as a whole-record operation that "never partially
rewrites a record" ([GLOSSARY.md](../GLOSSARY.md) § Transform). That line is easy to
misread as "stations forbids concurrent field-level updates."

cocli already carries a product instance of field-level facts: `DatagramRecord`
(`target`, `field`, `value`, timestamp) in a centralized journal (`wal.py`), applied
onto company `_index.md` at read time. Campaign index WALs (prospects, emails) are
separate stations-shaped logs of whole domain rows.

## Decision

### 1. Field-update facts are in scope for stations

**Yes.** Concurrent field-level updates are part of the stations model when encoded as
**append-only log records**, not as in-place surgery on a living file.

| Layer | Rule |
| :--- | :--- |
| **Log record** | A field-update is itself a **whole typed record** (identity of the patch event + target entity + field + value + monotonic version stamp). Shape A/B WAL layout and P7/P8 apply. |
| **Fold / index** | Present entity (or index row) state is `fold(base, field-updates…)` — typically LWW **per field** (or per declared merge key), producing a **whole** present record. Single-writer on the index/entity commit path still holds (CONCURRENCY §4). |
| **Transform** | Still whole-record: never "open file and rewrite three YAML keys" as the multi-writer protocol. A transform may *emit* field-update records into a log, or *consume* a whole folded entity. |

**Canonical product example:** User A sets `phone`; User B sets `address` for the same
company. Both append field-update records. Fold/LWW-by-field yields one company snapshot
with both fields. Neither writer needed the other's full document.

### 2. What remains forbidden

- Concurrent **in-place** partial rewrite of a file at its final path as the coordination
  protocol (violates whole-record transforms and P3 visibility).
- Treating "patch" as a transform that mutates a station item without going through a log
  (or an equivalent emission edge into a log).

### 3. Relationship to the trichotomy

Unchanged: `WAL = log + compaction policy`; `index = fold(log) + watermark`. Field-update
records are one **payload kind** of log record. Uncompacted segments remain a queue for
exactly one consumer — the compactor (GLOSSARY subtlety 1).

Per-field LWW is a **fold policy** choice (compatible with C7 when deterministic), not a
new edge role.

### 4. Consumer instances

A consumer may keep a product journal that already implements this pattern (e.g. cocli
`wal.py`) as **document-and-keep** until a LogEdge + Compactor cutover is scheduled. The
pattern is stations; the wiring may lag. Product code should docstring-link this decision
so agents do not treat the journal as "out of stations" husk.

## Consequences

- GLOSSARY § Transform is unchanged; this decision is the normative cross-ref that
  "not a patch" means not in-place transform surgery, not "no field-level concurrency."
- Future engine work may add helpers (e.g. per-field LWW fold factories) without changing
  Protocols in v1 if `Fold` already abstracts merge policy.
- cocli disposition (2026-07-23): document + keep `wal.py`; implement LogEdge/compactor
  cutover as a follow-on under the stations extraction epic.

## See also

- [GLOSSARY.md](../GLOSSARY.md) — trichotomy; Transform
- [spec/PHYSICAL-CONTRACT.md](../spec/PHYSICAL-CONTRACT.md) §5 WAL; hybrid read
- [spec/CONCURRENCY.md](../spec/CONCURRENCY.md) §3 compaction; C7 fold
- [consumers/cocli.md](../consumers/cocli.md) — entity field journal note
