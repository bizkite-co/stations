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
  Decision 0010 extends the projection to a fourth medium: a consumer's
  module tree can mirror its station tree, making the code namespace the
  *type-level* shadow of the data tree (static roots and segment types in
  code; segment values — shard `07`, day `23` — only in storage).
- **Topic hierarchies** (MQTT, message-bus subject trees) — namespaces that
  look like paths and route by prefix. The resemblance is real but shallow:
  topics route messages in flight; stations hold records at rest. The
  difference is durability-first vs delivery-first, and it is why stations
  needs no broker. The industrial incarnation of this pattern is the
  **Unified Namespace (UNS)** of Industry 4.0 (Walker Reynolds /
  iiot.university; implementations from HiveMQ, HighByte, Litmus): all
  plant-floor systems publish state into one hierarchical namespace,
  typically an ISA-95 tree (`enterprise/site/area/line/cell`), declared the
  single source of truth. UNS independently arrived at the path-as-model
  thesis — the topic path *is* identity plus semantic location — but by the
  mirror-image mechanism: a broker at the hub, with "current state" held as
  MQTT retained messages (or Sparkplug B's birth/death session state — whose
  device-oriented namespace is itself in tension with ISA-95 semantics, a
  live debate in that community). In trichotomy terms, UNS is the
  **index/present corner delivered by transport instead of storage**: a
  retained message at a topic is a `CURRENT` value at a path. What it lacks
  are the other two corners — nothing is ever *claimed* (pub/sub, no queue
  role), and history is a bolted-on "historian" database rather than an
  intrinsic WAL. Stations is structurally a superset: all three roles,
  durable at rest, no broker to keep alive.
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

## The biology of the pattern

A growing plant is the clearest teaching image the project has, because it
shows *two distinct regularities* at once — and separating them is what
makes the combinator idea (decision 0010) precise rather than merely
pretty.

- **Fractal branching — the self-similar part.** A twig forks the way the
  branch forked, which forked the way the trunk forked; the shape recurs at
  every scale. This is the Aristotelian microcosm sense, the part that "goes
  back to the whole in miniature." In stations it is **composition**: a
  station's output is another station's input, subgraphs nest, and the graph
  looks the same at every zoom level. It is free and structural — you get it
  from the model-to-model discipline without building anything.

- **Terminal convergence — the conserved-organ part.** However different the
  branches, the *leaves and flowers converge*: a small set of genetically
  fixed organ templates, instantiated over and over. Biologists call this
  serial homology; it is not self-similarity but almost its opposite —
  divergence in the connective topology, convergence at the functional ends.
  In stations this is the **shared segment library**: `phases`,
  `shard_by_hash`, `partition_by_day_of_month` are the leaves — built once,
  well tested once, terminated into by every branch. A leaf is not a smaller
  copy of the tree; it is a reused module the branch merely ends in.

Two consequences fall out of the second regularity, and they are the
load-bearing ones:

1. **The metaphor undersells the design.** In botany each species grows its
   own flower — a rose and an apple share no petals. Stations proposes the
   stronger thing: *one flower across all species*, the identical organ set
   shared by cocli, task-agent, and every future consumer. A universal organ
   set is a bolder claim than any single plant makes, and it is the whole
   point of extracting the combinators into the library rather than
   re-growing them per consumer.

2. **Test investment follows reuse down the same gradient.** The organs are
   few, shared, and stable, so they are tested exhaustively — once — and
   every branch inherits that trust. Branches then need only their *wiring*
   tested (does this model route to that station), not their organs. This is
   the mechanism by which growing the graph stays cheap: the marginal cost of
   a new branch queue falls toward "wire up organs you already trust." "Well
   tested leaf and flower models" is therefore not an ornament on the idea —
   it is how the idea pays off.

The healthy ratio is **few leaves, many branches** — a plant has a handful
of organ types and unbounded branch variety. A proliferation of one-off leaf
types would be the smell, which is exactly why decision 0010 keeps the
combinator set closed and small.

## The philology of the pattern

The pattern is older than software. The observation that prompted this
section: the author's own pre-cocli tooling already practiced it (`wrt`,
below), pub-sub systems namespace themselves with a word that turns out to
mean "place," and the trail runs back through the rhetoric tradition to
Aristotle. The vocabulary of logic and of knowing has been place-and-stand
vocabulary from the start — which is likely *why* stepwise, navigational
language keeps resurfacing in logic-driven technologies.

- **"Topic" means "place."** Aristotle's *Topics* (Τοπικά, from τόπος,
  "place") catalogs the τόποι — the *places* an arguer goes to find
  premises. One refinement to the intuition: Aristotle's places are less a
  terrain traversed stepwise than a spatially-indexed toolbox of argument
  shapes — which is why Latin rhetoric rendered them *loci*, and why English
  still says "commonplace" (*locus communis*, κοινὸς τόπος). But the naming
  survives intact: when Kafka and MQTT called their namespace nodes
  **topics**, the messaging world reached — without knowing it — for the
  same word this project reached for with "station." Two independent
  derivations landing on place-words is the etymology-is-the-thesis claim
  showing up again (see the topic-hierarchies bullet above).
- **"Method" means "path."** Greek *méthodos*, *meta-* + *hodós* ("way,
  road"): inquiry as travel along a way. The stepwise-navigation language
  observed in logic-driven technologies is not a modern metaphor imported
  into computing; it is the founding vocabulary of inquiry itself.
- **The Tree of Porphyry — stepwise navigation of a type tree.** The honest
  ancestor of "navigating to a logical domain through a sequence of steps":
  Porphyry's *Isagoge* (3rd c. AD, the standard introduction to Aristotle's
  *Categories*) arranges being as a tree — descent by differentiae through
  genus and species to the individual — where following the path down *is*
  constructing the definition. It is the ancestor of every taxonomy, class
  hierarchy, and directory tree. Its root node is, literally, **Substance**.
- **The memory arts — state at an address, in the head.** The method of loci
  (Simonides' legend; codified in the *Rhetorica ad Herennium*, Cicero,
  Quintilian): to remember, place items at addresses in an imagined
  building; to recall, walk the path. Memory organized as a filesystem,
  with retrieval as path traversal — the oldest evidence that addressable
  places are the native indexing structure of human cognition.
- **Commonplace books — the write side, and `wrt`'s direct ancestor.**
  The practice built on the loci: readers kept notebooks under topical
  headings, appended excerpts to the right heading as they read, and
  periodically distilled them into indexes and florilegia. *Append to a
  named place now, compact later* — the WAL discipline, practiced on paper
  for centuries. The author's own pre-cocli PowerShell tool `wrt`
  (`wrt -p cpt/characters/publicus "…"` appends into the file that a
  `namespaces.yml` maps that path to, with a declared document type per
  namespace) is a commonplace book with a manifest — and personal prior
  art showing the stations idiom developing in this toolchain before it
  had a name: path-to-namespace mapping, declared types per place,
  append-then-compact.
- **The stand-family — substance and understanding are station words.**
  The etymology section claims *status/statio*; the family is wider, all
  from the same root (PIE *\*steh₂-*, "stand"): **substance** (*substantia*,
  what stands under), **understand** (stand under/among), **instance**
  (*in-stare* — a record at a station is an instance in both senses),
  **exist** (*ex-sistere*, to stand forth), **destination** (*destinare*,
  where something is fixed to stand). The vocabulary of knowing is
  stand-vocabulary and the vocabulary of logic is place-vocabulary; when a
  record stands at a station, the language is operating at its root senses,
  not in metaphor.

Why the convergence keeps happening — hedged, but worth stating: spatial
navigation is the oldest and best-tested indexing structure humans possess,
so when a domain needs addressable structure, language reaches for places,
paths, and standing. Path-shaped namespaces in technology (POSIX, REST,
Hive, MQTT/UNS, stations) are then not a coincidence of fashion but the
newest instances of the oldest pattern — which is a reason to trust the
idiom's teachability: it runs on cognitive rails that predate literacy.

## Open threads worth traversing later

- Petri-net formalization of CONCURRENCY.md's invariants (C1–C14) —
  reachability analysis as a proof that no crash matrix cell loses a token.
- Queueing-theoretic capacity analysis over inspector output (dwell time,
  bottleneck stations) — the math exists; the inputs are already collected.
- The path-mapping-as-functor intuition, written up properly or explicitly
  retired.
- A comparative note on maildir's NFS-safety arguments vs this spec's S3
  conditional-PUT arguments — same shape of reasoning, thirty years apart.
- The philology thread, sourced properly: Aristotle's *Topics*, Porphyry's
  *Isagoge*, and Frances Yates, *The Art of Memory* (1966) — the standard
  history of the loci tradition. Also worth mining: commonplace-book
  compaction practice (indexes, florilegia) as design precedent for
  index-station and digest patterns.
- Segment combinators (decision 0010): phase dirs, shards, and date
  partitions implemented once as declared, importable segment types —
  maildir's `tmp/new/cur`, task-agent's four phases, and day-of-month
  inbox sharding are all hand-rolled instances of the same four
  combinators. If the spec's layouts become derivable from combinator
  contracts, that may be the largest single payoff of the model-as-path
  idiom.
