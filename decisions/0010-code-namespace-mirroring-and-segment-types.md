---
status: proposed
date: 2026-07-24
---

# 0010: Code-namespace mirroring and typed path segments

## Context

The spec binds two of the three namespaces a station lives in: **logical
station path ↔ physical path** (the whole of PHYSICAL-CONTRACT.md) and
**station ↔ model + schema version** (typed paths). It is silent on the
third: **station path ↔ code namespace**. Nothing says where a station's
*definition* — its model reference, path template, and declared edges —
lives in a consumer's package tree. In cocli today the answer is
"wherever": models in `cocli/models/`, station wiring centralized in
`stations_runtime.py`, and the code tree screams nothing about the station
graph. "Screaming architecture" was named during the extraction epic but
never acted on.

Two observations motivated this decision (conversation of 2026-07-24):

1. A consumer's package tree can mirror its station tree, so that `tree`
   on the code and `ls -R` on the data show the same shape — and station
   discovery becomes package-walking instead of registry-maintaining.
2. The runtime path segments that seem to *break* the mirroring — phase
   dirs, shards, date partitions — are themselves reusable code. Every
   consumer hand-rolls them today: maildir's `tmp/new/cur`, task-agent's
   `draft/pending/active/completed`, the inbox design's day-of-month
   sharding with TTL 7, cocli's sharded USV pages. Each is an instance of
   a small set of segment *types* that could be implemented once and
   declared per station.

## Decision

### 1. The type/value split is the mirroring rule

The code tree is the **type-level projection** of the data tree.

- **Type-level** (lives in the code namespace): the static template root
  of a station, and the *types* of its dynamic segments
  (`phases(…)`, `shard_by_hash(n)`, `partition_by_day_of_month(ttl_days=…)`).
- **Value-level** (lives only in storage): the *values* those segments
  take at runtime — shard `07`, day `23`, `pending/` vs `completed/`.

A physical path is therefore: code-path (types) + runtime values. The
earlier caution "runtime segments have no business in a code namespace"
was half right — the values don't; the types do, as imports.

### 2. Consumer convention: mirrored station packages

Consumer applications SHOULD lay out station definitions in a package
tree that mirrors the station tree — e.g. a station whose data lives
under `prospects/enrichment-queue/…` is defined in
`myapp/stations/prospects/enrichment_queue.py`. The unit at the mirrored
code path is the **station definition** (model reference + template +
edges), not the model itself: one model may stand at several stations
(the queue/WAL/index trichotomy is consumer-relative), so binding the
model's own module to a single station would force duplication.

Consequences of the convention:

- Station discovery = walking the package (or importing the module named
  by the path). No separate registry to maintain or drift.
- The repo tree screams the station graph — the screaming-architecture
  payoff, realized rather than cited.

### 3. Segment types as shared combinators

Dynamic path segments are implemented **once, in the library**, as
declared, importable combinators, each carrying its full contract:

| Combinator (illustrative) | Contract it owns |
| :--- | :--- |
| `phases("pending", "active", "completed")` | which phase dirs exist; legal phase transitions; claim/lease enumeration surface |
| `shard_by_hash(n)` / `shard_by_prefix(k)` | routing a record to its shard; shard enumeration; fan-in for compaction |
| `partition_by_day_of_month(ttl_days=…)` | partition naming; TTL/GC semantics; watermark interaction |

This is the largest payoff of the model-as-path idiom identified so far:
phase dirs behave identically across every station in every consumer;
shards are uniform "or at least by declared type-of-shard"; and spec
layouts become *derivable instances of combinator contracts* rather than
prose descriptions repeated per layout. The claim protocol asks the phase
combinator how to enumerate candidates; compaction asks the partition
combinator what is expired — the P-rules and C-rules gain a vocabulary to
attach to.

### 4. Spec-side vs implementation-side (language portability)

The mirroring convention and the combinator library are
**implementation-side**; the spec stays language-neutral. The split,
following the protobuf precedent (one logical `package foo.bar`
projected mechanically into every language's module system, schema file
location mirroring the package):

- **Spec** gains (a) a naming discipline — station path segments MUST be
  valid identifier segments in mainstream module systems (lowercase,
  `[a-z0-9_-]`, with a defined `-`→`_` projection rule) — and (b) a
  declarative segment-type block in the station manifest, e.g.
  `{"partition": {"type": "day-of-month", "ttl_days": 7}}`, so any
  implementation can project declared types into its own combinators.
- **Reference implementation** (Python) ships the combinator library and
  adopts the mirrored-package convention in its docs and consumers.

An implementation in Go or Rust mirrors into Go packages or Rust modules
the same way — the spec's declarative block is the shared truth.

### 5. Guardrails against frameworkiness

- The initial combinator set is **closed and small**: phases, hash-shard,
  prefix-shard, day partition. Everything observed in the existing
  consumers is an instance of these four. The constraint is principled, not
  arbitrary: it is the **few-leaves-many-branches** ratio of a healthy
  plant (LINEAGE.md, "The biology of the pattern") — a handful of conserved
  organ types carrying unbounded branch variety. A proliferation of one-off
  leaf types is the smell this guardrail exists to catch.
- Bespoke segments remain legal as opaque template variables; a station
  is not required to describe its segments in combinator terms.
- A combinator extension/plugin mechanism is explicitly deferred — add a
  fifth combinator only when a third consumer hand-rolls the same shape.

## Consequences

- Retroactive audit needed: existing station paths in cocli and
  task-agent must be checked against the identifier-segment discipline
  (§4a) before it becomes normative.
- cocli's Phase 4 (husk deletion, decision 0006) is the natural trial
  moment: station definitions get re-homed into a mirrored
  `cocli/stations/` tree instead of back into `stations_runtime.py`.
  Filed as a task in the cocli store under the extraction epic.
- LINEAGE.md gains this as a fourth rediscovery of path-as-namespace
  (after Plan 9, REST, and Hive): this time in the code itself.
