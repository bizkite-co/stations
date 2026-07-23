# Lineage: where "station" comes from, and the family of ideas this pattern lives in

This document answers a question that came up while naming the project: is
"station" a term of art from state machines? From category theory? From
namespace/topic hierarchies? The answer turned out to be richer than the
naming conversation assumed, and the connections are worth recording because
they are load-bearing: several of them predict design decisions this spec
already made independently.

## The etymology is the thesis

"State" and "station" are cognates. Both descend from Latin *stare*, "to
stand":

- ***status*** — the **condition** of standing. A state.
- ***statio*** — the **place** of standing. A station.

A station is a state with an address.

That is not wordplay; it is the entire architectural claim of this project
compressed into an etymology. A finite-state-machine "state" is a label held
in memory by a running process. A station is a state that has a *location* —
a path — so that being in the state and being at the place are the same
fact. This is what "the storage layout is the state machine" means: the
system's state does not need to be tracked, because it cannot be anywhere
other than where it is.

Everything else in this document is family resemblance around that core.

## Formal neighbors

### Finite state machines — the resemblance that prompted the name

The obvious parent: typed stops, legal transitions between them, illegal
transitions unrepresentable. But the resemblance breaks down at concurrency,
and the breakdown is instructive. An FSM has **one current state**. A
stations system has thousands of records, each at its own station,
simultaneously. "Which state is the system in?" has no answer; "which
station is this record at?" always does. The FSM lens is right for one
record's lifecycle and wrong for the system — which is exactly why the next
neighbor matters more.

### Petri nets — the closest formalism

Carl Adam Petri introduced these (1962) precisely because FSMs cannot
express concurrency. A Petri net has:

| Petri net | stations |
| :--- | :--- |
| **place** (holds tokens) | station (holds records/files) |
| **token** | one record at one station |
| **transition** (consumes tokens from input places, produces tokens in output places) | transform (consumes from from-station, emits to to-station) |
| marking (token distribution across places) | the full `ls -R` of the store |
| token reservation in extended nets | claim/lease (CONCURRENCY.md §2) |

This is the formalism to reach for if the spec's concurrency contract ever
wants mechanical verification — reachability, liveness, and boundedness
analysis of Petri nets is mature tooling. It is also the honest answer to
"is this a state machine?": no — it is nearer to a Petri net whose places
are directories and whose tokens are files, with POSIX rename / S3
conditional PUT as the atomic firing rule.

### Queueing theory — where "station" is already a term of art

Queueing networks (Jackson networks, BCMP networks) are composed of
**service stations**: nodes where jobs queue, receive service, and are
routed onward to other stations. The vocabulary maps directly — station,
queue at the station, service (transform), routing (emission edges). This
matters beyond vocabulary comfort: queueing theory is the mathematics of
throughput, dwell time, and bottleneck analysis, and the inspector already
surfaces the raw inputs (per-station counts, age-of-oldest). If stations
ever grows capacity-planning features, the math has been sitting there since
the 1950s under the same word.

### Category theory — light touch, real influence

The from-model-to-model discipline (cocli ADR-001) is morphism thinking:
models as objects, pure transforms as arrows, composition of transforms as
the only way to build pipelines. Stations add one structure on top: a
mapping from the category of models to the category of paths, such that
transform composition corresponds to path-to-path movement. Treat this as
evocative rather than load-bearing — the spec does not need functor laws to
be correct — but the intuition "a transform is an arrow between typed
objects, and the path mapping preserves that structure" is genuinely what
keeps the design honest about purity and composition.

## Systems ancestors

- **maildir** (qmail, 1995) — the pattern's most direct ancestor.
  `tmp/` → `new/` → `cur/`: state transitions via atomic rename, one file
  per message, no locks, no daemon, safe over NFS. Maildir is a two-station
  system that never generalized. Stations is, in one sense, "maildir with a
  type system and a spec."
- **POSIX paths as namespace** — the path is simultaneously identity, type,
  and state. That triple duty is the compression that makes `ls` the
  monitoring surface and `mv` the transition operator. Plan 9 pushed this
  furthest (every service a file server); REST rediscovered it for the web
  (URIs as typed nouns); Hive partitioning rediscovered it for data lakes
  (path segments as typed columns). Stations sits squarely in this lineage:
  the filesystem is not where state is *recorded* — it is where state *is*.
- **Topic hierarchies** (MQTT, message-bus subject trees) — namespaces that
  look like paths and route by prefix. The resemblance is real but shallow:
  topics route messages in flight; stations hold records at rest. The
  difference is durability-first vs delivery-first, and it is why stations
  needs no broker.
- **LSM trees / write-ahead logs** — the queue/WAL/index trichotomy
  (future/past/present) borrows its compaction vocabulary (leveling,
  tombstones, watermarks, `CURRENT` pointer) from LevelDB/RocksDB — prior
  art in *mechanism*, deliberately rejected as a *component* (decision
  0007): SST files break the inspectability that makes the whole idiom
  worth having.
- **Assembly-line work stations / railway stations / stations of the
  cross** — the ordinary-language senses, all sharing one meaning: *a fixed
  waypoint along a path where something stops and something is done to it or
  witnessed about it*. This is why the term teaches itself to newcomers in a
  way "place" (Petri), "node" (queueing), or "directory" (POSIX) would not.

## Why the word is right

Every alternative loses something the word "station" keeps:

- **"state"** loses the address — and the address is the point.
- **"directory"** loses the type and the contract — a station is a
  directory *plus* a model, a schema version, and declared edges.
- **"place"** (Petri's own term) is formally exact but colorless, and
  collides with geography in a codebase that also does geocoding.
- **"stage"** implies a single linear pipeline; stations form a graph.
- **"queue"** names only one of the three roles a station can play
  (queue/WAL/index — the trichotomy is consumer-relative).

"Station" holds the whole bundle: a typed, addressable, inspectable stopping
place on a path, where records stand — *stare* — until a transform moves
them on.

## Open threads worth traversing later

- Petri-net formalization of CONCURRENCY.md's invariants (C1–C14) —
  reachability analysis as a proof that no crash matrix cell loses a token.
- Queueing-theoretic capacity analysis over inspector output (dwell time,
  bottleneck stations) — the math exists; the inputs are already collected.
- The path-mapping-as-functor intuition, written up properly or explicitly
  retired.
- A comparative note on maildir's NFS-safety arguments vs this spec's S3
  conditional-PUT arguments — same shape of reasoning, thirty years apart.
