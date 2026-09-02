# Adoption: finding out whether anyone else wants this

Working document. Last landscape fold: 2026-09-01. Archived cited review
(session tables + deep-research report):
[docs/product/feasibility-cited-report.md](./product/feasibility-cited-report.md).

The question it answers is not "how do we market stations" but the honest
prior question: **would anyone besides its author use it, and how do we
find out cheaply?** It is working very well for one person across dogfood
consumers (`cocli`, `task-agent`, and the library's own tooling). That is
a real signal, but it is one data point from the person least able to see
the product's flaws.

## One-sentence positioning (current best draft)

> **Stations is the queue you can `ls`** — a spec and reference library for
> coordinating distributed work through storage semantics alone: typed
> paths, sibling `.lease` claims, and CAS, with no broker, no database, and
> no server to run.

Secondary framings, for different audiences:

- For data people: "maildir generalized into a typed, multi-worker
  pipeline substrate, with a written physical + concurrency contract."
- For agent builders: "Beads remembers *what's ready*. Stations is how
  workers *claim* a typed item without a broker, as a folder a human can
  read."
- For platform skeptics: "everything Kafka-shaped assumes you'll run a
  server. This assumes you won't."
- For Industry-4.0 / UNS people (not a 2026 beachhead — see ICP): "a
  durable namespace *under* the live bus — the WAL you can `ls` when the
  broker is off."

## The honest landscape (who is adjacent, and what's actually different)

Stations is **durable coordination of records at rest**, not durable
execution of code. That distinction decides almost every comparison.

| Category | Examples | What they assume | Where stations differs |
| :--- | :--- | :--- | :--- |
| Brokers | SQS, RabbitMQ, Kafka | A server (or AWS) owns coordination | No broker; create-if-absent `.lease` / S3 `If-None-Match` are the coordinator |
| Durable execution | Temporal, Inngest, Hatchet, DBOS | Your *code* is the durable thing; state is opaque in their store | Your *data at rest* is the durable thing; state is inspectable files. Not a substitute: they replay functions; stations cannot. |
| Orchestrators w/ assets | Dagster, Prefect, Airflow | A scheduler process; assets as metadata about elsewhere-stored data | No scheduler; the asset's location *is* its state. Substitute only for cron + `inbox/` folders. |
| App-level state machines | Apache Burr, XState, LangGraph checkpointers | In-memory state blob per app instance, pluggable opaque persisters | Multi-worker by construction; storage layout is the state machine (Burr comparison in decision 0008) |
| File/embedded queues | maildir, persist-queue, litequeue, huey, **SteadQ**, CERN **dirq**, **Filespooler**, **fsq**, **jqueue** | A FIFO of jobs (often one machine, one language, or one opaque blob) | Typed models per path; queue *and* WAL *and* index; one contract for POSIX and S3 |
| Agent issue graphs | **Beads**, tbd, pebbles, claude-task-master | Git-backed planning / agent memory (`bd ready`) | Fleet *claim/lease* of a work item, not session memory. Complement, not a Beads killer. |
| Spec-first object queues | **StowQ**, lakestream **S3-Queue** | Object-store-only log or claim-object protocol | Same *no-broker + CAS* instinct; stations wants one logical path layout on disk *and* S3, with typed stations |
| Industrial UNS | MQTT + Sparkplug B; HiveMQ, HighByte, Litmus, iiot.university | A broker holds the namespace; current state = retained messages | Same path-as-identity thesis, opposite mechanism. Complement (historian / edge), not a broker replacement. |
| Table formats | Delta Lake, Iceberg | Analytics-scale tables, heavy ecosystem | Same manifest/compaction ideas at ops scale, human-readable, zero infra |

### Closest cousins (2026) — the comparisons that matter

These were missing from the first cut. They occupy the *edges* of the
four-point bundle; none occupies the center.

| Product | What it actually is | vs stations |
| :--- | :--- | :--- |
| **SteadQ** (Aug 2026, Apache-2.0, Rust) | Daemonless Linux directory job queue. Jobs are files; claim by `renameat2(RENAME_NOREPLACE)`; leases, receipts, dead-letter; files-are-true thesis. Linux local FS only (NFS/FUSE rejected). | Closest *product* cousin. Queue-only; POSIX-only; pathnames encode ownership. Stations adds types, a station graph, trichotomy, dual-backend *intent*. |
| **StowQ** | Same author's object-store sister: immutable jobs, ownership as a chain of claim objects, conditional create. | Occupies the S3-CAS queue slot. **Different protocol from SteadQ**, not one dual-backend layout. |
| **lakestream S3-Queue** / Leaderless Log Protocol | Spec-first S3 log/queue: compaction, cursors, fencing. GTM is "paste the spec into an agent." | Same spec-first go-to-market. Kafka-shaped on S3, not path-as-FSM. No POSIX. |
| **jqueue** | One `queue.json` blob; CAS on a local file or S3/GCS. | The only small product that actually does POSIX+S3+no-server — by *refusing* path-as-state. Opposite of `ls`. |
| **CERN dirq** (Perl/Python/Java/C, unmaintained) | Language-portable directory queue, atomic FS ops. | Historical proof that **spec + multi-language** is how this pattern spreads. Queue only; no S3. |
| **Filespooler** (John Goerzen) | Files *are* the network; Syncthing/S3/USB as transport; ordered packets. | Unix-philosophy cousin. Sequential, not multi-worker leases; S3 as a mount, not native CAS. |
| **fsq** (~2014) | POSIX file-system queue *standard* (`tmp/queue/done/fail`). | Spec-first POSIX ancestor. Abandoned. |
| **Beads** (~27k GitHub stars as of the 2026-08-31 review), **tbd**, **pebbles** | Git-backed agent issue graphs. Anthropic's Claude Tasks copied the shape. | Occupies "agent memory as files." Different job: planning/amnesia, not fleet claim. |

Sources for this fold: parent-task `feasibility-cited-report.md` (deep-research,
2026-08-31) and the 2026-09-01 session review. Star counts are from that
review, not re-polled here.

### Uniqueness (narrowed)

The old line — "no one adjacent has all four: written contract, no server,
same paths on disk and S3, inspectability" — is still true *if interpreted
strictly as one product*. It is no longer true that the region is empty.
Neighbors sit on every edge (SteadQ on POSIX spec+queue; StowQ/S3-Queue on
S3 CAS; jqueue on dual-backend no-server; Beads on agent files).

The honest 2026 sentence:

> Nobody ships a **typed station graph** whose storage layout is the state
> machine for queue *and* WAL *and* index, with **one POSIX/S3 contract**
> and **inspectable files**. File-as-queue is taken. Agent-as-issue-tracker
> is taken. The nearest substitute is SteadQ locally and StowQ remotely —
> two protocols, two encodings, queue-only.

Until S3 engines are proven in production cutover, stations currently
occupies "documented maildir descendant with types," not the full bundle.
Do not pitch Temporal, Kafka, Iceberg, CrewAI, or HiveMQ as peers.

## TAM hypotheses, ranked by current evidence

Ranked by chance a *stranger* tries this in 12 months, not TAM poetry.

1. **AI-agent system builders who need claim/fleet, not another tracker.**
   Strongest hypothesis, but **not the Beads user**. Agents need durable,
   auditable, multi-worker claim of a typed work item; opaque broker state
   is hostile to debugging. task-agent is the existence proof; Beads/task-master
   explosion and Claude Tasks-on-disk are demand evidence for *files as
   agent state*, which is adjacent. Risk: they think Beads already solved it.
2. **Local-first / "files are true" developers.** The pebbles/tbd revolt
   against Beads' SQLite/daemon is the tell: they want files, not a cache
   of files. Easy demo (`ls`, `rg`, DuckDB). Risk: a 200-line maildir is
   enough; the spec looks heavy.
3. **Edge / small-fleet operators** (Raspberry Pi clusters, homelab,
   HPC login nodes, retail/IoT edge). cocli's Pi scraper fleet is the
   existence proof; SteadQ shipping musl aarch64 is independent confirmation.
   These users *cannot* run Kafka and resent running Postgres for a queue.
   Risk: they copy 80 lines of `mv` and never import a package — the *spec*
   is the win.
4. **Data-engineering-lite** — teams for whom Dagster/Airflow is too much
   ceremony but cron-plus-hope is too little. The trichotomy
   (queue/WAL/index) names what they're already doing badly in `inbox/` /
   `staging/` / `out/`. They still need a clock; position as substrate
   under cron, not an Airflow killer.
5. **Other-language spec implementers** — people who would never adopt the
   Python library but might implement the *spec* (maildir / dirq /
   lakestream precedent). Smallest group, highest leverage per person.
   One Go/Rust implementation by a stranger is worth more than 100 Python
   stars.
6. **Industrial UNS / Industry-4.0 — demoted; not a 2026 beachhead.**
   Pre-sold on *namespace*, allergic to "replace the broker," 18-month SI
   cycles, need Sparkplug/ISA-95 not Pydantic models. Keep as a talk story
   and a possible MQTT bridge; loop back through segment #3 (edge without
   a broker). Honest friction: that community *expects* real-time pub/sub,
   and rename-and-CAS is not report-by-exception millisecond delivery.

## Validation before promotion

Do this before spending on content. The goal of the first phase is
*disconfirmation*: find out which hypothesis above is wrong cheapest.

- **Ten conversations, Mom-Test style.** Not "would you use stations?"
  (everyone lies) but "how do you coordinate work between your workers
  today, and what did that cost you last month?" If their answer contains
  a war story, show the inspector. Where they live: r/selfhosted,
  r/LocalLLaMA, r/dataengineering, HN, lobste.rs, the Dagster and Temporal
  community Slacks (their *overflow* users are the prospects), agent-builder
  Discords. Put the inspector gif in front of SteadQ/Beads users; if they
  say "I already have `ls` / `bd ready`," the wedge is the spec, not the CLI.
- **Signals that count** (in ascending order of meaning): stars → issues
  opened by strangers → "can it do X" questions → **someone builds a
  consumer you didn't write**. Only the last one is product-market fit;
  the first is vanity. Author dogfood is one data point.
- **Signals to ignore:** praise from people who will never run it;
  comparisons to Kafka from people who need Kafka; Temporal Cloud buyers;
  HiveMQ RFPs.

### Falsifiable ICP tests

| ID | Hypothesis | Kill it if |
| :--- | :--- | :--- |
| H1 | Agent builders need *claim + inspectable work items*, not another issue tracker | 8/10 say "Beads + git is enough" |
| H2 | Edge/Pi/homelab will take a spec because they refuse brokers | They star and keep using `mv` + flock, or already run Redis on the Pi |
| H3 | DE-lite will use trichotomy vocabulary | They install Prefect in an afternoon instead |
| H4 | Spec > library (maildir path) | Only Python users, asking for Celery features; nobody implements the spec |
| H5 | Inspector is the wedge | People ask for a web UI / Temporal-like replay and ignore `stations inspect` |
| H6 | UNS is complement not substitute | OT Slack: "this isn't real-time" and leave; time-box to one MQTT-bridge spike + two SI chats |
| H7 | Durable-execution users are overflow, not ICP | Temporal Slack tells you to use the workflow UI |

## Distribution plays (ordered; each builds on the last)

1. **Lead with the inspector, always.** Burr's most-praised feature was
   their telemetry UI, not their formalism (decision 0008). Ours is nearly
   free because state is files. Every demo, video thumbnail, and README
   gif should be `stations inspect` output, never YAML.
2. **The genesis story is the best content.** "I tried to simplify a CLI's
   command tree and found a distributed-systems substrate hiding in it" is
   a genuinely good arc for the planned YouTube/blog series — it models
   the discovery for the viewer instead of pitching at them. Second
   episode: the store-divergence incident and what it taught about
   single-writer invariants. War stories outperform feature tours. Beat
   SteadQ on graph + types + one dual-backend contract, not on being "a
   file queue." Beat Beads on claim/lease/fleet, not on being "agent memory."
3. **Show HN once, deliberately.** After the inspector gif, the spec
   landing page, and a 10-minute quickstart exist. Title shaped like the
   positioning line ("Stations – the queue you can ls: typed paths, leases,
   no broker"), not like a product launch, and not `rename()` as the claim.
4. **Market the spec, not just the library — the maildir precedent.**
   maildir won because it was a *contract* anyone could implement, not a
   library anyone had to adopt. PHYSICAL-CONTRACT.md and CONCURRENCY.md
   are the durable artifact; the Python package is "the reference
   implementation," which flatters it correctly. A Go or Rust
   implementation by a stranger would be the single strongest adoption
   event available — make it easy: keep the spec permissively licensed
   (CC-BY or Apache-2.0) and version it independently of the package.
5. **Integration adapters as marketing.** Each one is a doorway into an
   existing community rather than a request that they move:
   - **MCP server over a station root** — agents browsing/claiming work via
     MCP. Highest-leverage adapter given hypothesis #1; task-agent already
     prototypes the shape.
   - **fsspec** compatibility notes (their ecosystem, our claim primitive).
   - **DuckDB recipes** — "query your queue with SQL" (read side only; the
     spec already designates DuckDB as the read planner, not the engine).
   - **Burr persister backend** implemented over stations — turns the
     comparison in decision 0008 into a collaboration instead of a rivalry.
   - **Dagster asset-observation** hook (their observability, our storage).
   - **MQTT/UNS bridge** (later, not a beachhead) — publish each index
     station's `CURRENT` values into a UNS topic tree, and/or ingest a UNS
     subscription into a station WAL. Cheap because the namespaces are
     already isomorphic; turns the historian bolt-on problem into "point
     it at the WAL."
6. **Conference-talk shape** (later): "The filesystem is a state machine"
   — the LINEAGE.md material (statio/status, Petri nets, maildir) is the
   talk skeleton. Name SteadQ/StowQ as cousins, not as absences.

## Folding into / coexisting with other systems

Realistic postures, from least to most entangled:

- **Coexist (default):** stations runs under anything that can touch a
  filesystem or S3 bucket. No integration required is itself a feature.
- **Adapter into their world** (the §5 list above) — keeps stations
  sovereign while borrowing distribution.
- **Their backend, our substrate** — e.g. Burr persister, Celery-style
  transport. Worth doing once, opportunistically, if a maintainer is
  receptive; not worth chasing.
- **Donation/merger into a larger project** — premature and probably
  wrong: the spec-first identity is the differentiator, and it would be
  the first thing a larger host project would compromise.

## Speculative interop surfaces (recorded, not planned)

Explicitly speculative — none of this is roadmap. Recorded because the
adjacencies keep compounding, which itself is evidence of hidden value:
the pattern seems to sit at an interop nexus, plausibly because "typed
files at rest" is the lowest common denominator that *every* adjacent
system — brokers, orchestrators, agents, historians, SQL engines — can
already touch without adopting anything.

- **LLM-driven UNS transforms (Burr × UNS × stations).** Year-two
  complement, not a 2026 ICP. The industrial UNS gives an agent a
  semantically organized, real-time picture of an operation; Burr-style
  agentic loops give it decision structure; what neither provides is a
  durable, auditable, resumable substrate for the agent's *actions*.
  Stations is that missing third leg *if* OT will accept files under the
  bus. Do not lead with this.
- **The general pattern behind that example:** any pairing of (a
  live/semantic view of the world) with (an agent that acts on it) needs
  (a durable, inspectable action substrate) — and stations keeps showing
  up as the third leg regardless of what fills the first two slots. Worth
  watching for more instances rather than engineering toward any one.

## Business posture (so it's written down)

Open source, staying open source. The defensible open-core line, if one is
ever wanted, is the same one every storage-adjacent company found:
**the contract and library stay free; operating them for you is the
product** (hosted inspector/dashboards, managed compaction, fleet health).
Products built *on* stations (cocli and successors) are their own
businesses and impose no obligation on the substrate. Keeping the spec
permissive is both the adoption strategy and the moat: the more
implementations exist, the more valuable being the reference one becomes.

## Next actions

- [ ] Inspector demo gif in the README (before any promotion).
- [ ] Spec landing page: positioning line, the narrowed uniqueness claim
      (typed station graph + one POSIX/S3 contract + inspectable files),
      quickstart.
- [ ] License check: spec CC-BY/Apache-2.0, package licensing decision recorded as a decision doc.
- [ ] Ten discovery conversations (log outcomes in this file). Kill H1–H3
      from those, not from praise.
- [ ] Genesis-story video/post no. 1.
- [ ] MCP-server-over-station-root spike (ties to hypothesis #1).
- [ ] Time-box UNS: one MQTT-bridge prototype + two SI chats, then drop or
      keep as year-two complement.
