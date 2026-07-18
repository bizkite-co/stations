# Glossary

Canonical definitions. Every consumer doc and every external mention of these terms should
link here rather than restate the definition — this file is the single-writer for what
these words mean. If a term needs a different meaning in one consumer, that's a sign the
term is being reused for two concepts; split it, don't override it.

## Station

A path — local filesystem or object storage (e.g. S3), interchangeably — bound to a
declared record type (a schema), a versioned serialization format, and a location template.
The hierarchical path tree *is* the logical schema and domain organization. A station is a
noun: `pending/`, `completed/2026/`, `campaigns/{campaign}/discovery-gen/pending/`.

## Transform

A pure, immutable, strongly typed function that converts an object in one station into an
object of another type in another station. Directories are states; transforms are the
typed edges between them. A transform never partially rewrites a record it isn't moving —
each move is a whole-record typed operation, not a patch.

## Edge role

The consumption semantics between one *consumer* and one *station* — queue, WAL, or index
(see Trichotomy below). Roles attach to the edge, not the station, because the same
physical directory can play different roles to different consumers (e.g. a completed-queue
directory is simultaneously the tail of a log, for a different reader).

## The trichotomy: queue / WAL / index

Three roles built on one primitive — the append-only log — distinguished by consumption
semantics, remembered by tense:

| Structure | Tense | Semantics | Deletion test |
| :--- | :--- | :--- | :--- |
| **Queue** | future | intentions/work; claimed by exactly one worker (lease), driven to a terminal state | loses pending work, no history |
| **WAL / log** | past | immutable facts; append-only, read by anyone, retired only by compaction | loses information — source of truth |
| **Index** | present | derived state; a fold of one or more logs, with a freshness watermark | loses only time — always rebuildable by replay |

Formally: `queue = log + claim protocol + terminal states`; `WAL = log + compaction
policy`; `index = fold(log) + watermark`, written by exactly one compactor (see
Single-writer rule).

Two subtleties: (1) the set of not-yet-compacted WAL segments is itself a queue *for
exactly one consumer, the compactor* — queue-ness is a per-consumer view, not an intrinsic
property of the directory. (2) A completed-queue directory can simultaneously be the tail
of a log for a different reader — hence edge roles attach to edges, not stations.

## Claim / lease

The per-backend primitive that lets exactly one worker take ownership of a queue item:
POSIX atomic rename locally, S3 conditional PUT/If-None-Match remotely. This is the part
general-purpose filesystem libraries (e.g. fsspec) don't provide — it's the actual
load-bearing IP of any implementation of this pattern. Full state machine:
[spec/CONCURRENCY.md](./spec/CONCURRENCY.md) §2.

## Single-writer rule

Each index (or any derived/ratified station) has exactly one writer-class: the compactor
or ratification transition that folds the log into it. Other processes may read; only that
one role may write the authoritative set. This is what makes emission edges (below) safe:
an emission is a *proposal* into another station's intake, never a direct write into its
ratified set. Enforcement (lock for liveness, CAS commit for safety):
[spec/CONCURRENCY.md](./spec/CONCURRENCY.md) §4.

## Watermark

The marker on a derived station stating how much of the source log has been folded into
it — the freshness/staleness signal. An index without a watermark is not trustworthy as
"current." Physical form (the `CURRENT` commit pointer; implicit vs. explicit frontiers):
[spec/PHYSICAL-CONTRACT.md](./spec/PHYSICAL-CONTRACT.md) §6.

## Portable task

A task record whose payload declares a typed transform *on some other system*, with an
executable acceptance predicate as its done-check:

```yaml
transform:
  context: <the system being transformed>
  input_type: <state before>
  output_type: <state after>
  done_check: <a command; exit 0 iff output_type has been reached>
```

The done_check is the transform's watermark: anyone can re-run it to verify completion
without trusting the task's status field. First live instance: task-agent's
`ratify-station-map-declaring-task-agent-as-a-typed-file-path-station-system` task.
Prototype done_check: cocli's CLI-epic done-condition, `diff actual_tree.txt
target_tree.txt`.

## Emission edge

A transform has exactly ONE primary output type — the thing its done_check verifies — but
may also produce N declared secondary emissions: policy statements, ADRs, spawned tasks,
strategy docs. These are not side effects; each is a typed record routed into the
*intake/proposal station of a different state machine*, never directly into that machine's
ratified/terminal station (this is what preserves the single-writer rule — the target
machine's own ratification transition remains the only writer of its authoritative set).

Mechanically: an emitting record declares `emits: [{type, file, to}]` in its frontmatter;
its completion transition routes each attachment to its declared intake station with a
two-way traceability link (`emitted_by:` on the emitted record ↔ the attachment listing on
the source). A spawned subtask is this same mechanism with record type = task. A proposed
policy or ADR is this same mechanism with record type = decision.

Nearest external prior art (for grounding, not lineage): Flink/Beam "side outputs"
(`OutputTag` — one primary output + N declared typed channels); DDD "domain/integration
events" (a typed fact crossing a bounded-context boundary into another context's inbox).

## Cross-repo referencing (identity, not path)

A record's path encodes its *station membership*, and records move — so a path or URL
written down today is stale the moment the record transitions. Records reference other
records by **identity** (`repo-moniker#slug`), never by path. A registry resolves identity
→ current path; until one exists, resolution is manual and any recorded path is a cache,
not a source of truth.

## Decisions vs policy (a derived pair, same as WAL vs index)

A **decision** is a fact — append-only, superseded-not-edited, with a tombstone link when
replaced (an ADR). A **policy** is the *fold* of accepted decisions — the present-tense,
rebuildable summary of what currently holds. Don't build separate mechanisms for these;
one `decisions/proposed/` intake station with a `kind:` field (`policy-rule`, `strategy`,
`architecture`, ...) discriminates them, mirroring the log/index relationship above.
