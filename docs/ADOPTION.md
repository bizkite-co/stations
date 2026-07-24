# Adoption: finding out whether anyone else wants this

Working document. The question it answers is not "how do we market
stations" but the honest prior question: **would anyone besides its author
use it, and how do we find out cheaply?** It is working very well for one
person across three consumers (cocli, task-agent, and the library's own
tooling). That is a real signal, but it is one data point from the person
least able to see the product's flaws.

## One-sentence positioning (current best draft)

> **Stations is the queue you can `ls`** — a spec and reference library for
> coordinating distributed work through storage semantics alone: typed
> paths, atomic renames, and CAS, with no broker, no database, and no
> server to run.

Secondary framings, for different audiences:

- For data people: "maildir generalized into a typed, multi-worker
  pipeline substrate, with a written physical + concurrency contract."
- For agent builders: "durable, inspectable coordination between agents
  where the coordination state is plain files a human can read."
- For platform skeptics: "everything Kafka-shaped assumes you'll run a
  server. This assumes you won't."
- For Industry-4.0 / UNS people: "a broker-free, durable Unified
  Namespace — the UNS you can `ls`, and that survives the broker being
  off."

## The honest landscape (who is adjacent, and what's actually different)

| Category | Examples | What they assume | Where stations differs |
| :--- | :--- | :--- | :--- |
| Brokers | SQS, RabbitMQ, Kafka | A server (or AWS) owns coordination | No broker; POSIX rename / S3 conditional PUT are the coordinator |
| Durable execution | Temporal, Inngest, Hatchet, DBOS | Your *code* is the durable thing; state is opaque in their store | Your *data at rest* is the durable thing; state is inspectable files |
| Orchestrators w/ assets | Dagster, Prefect, Airflow | A scheduler process; assets as metadata about elsewhere-stored data | No scheduler; the asset's location *is* its state |
| App-level state machines | Apache Burr, XState | In-memory state blob per app instance, pluggable opaque persisters | Multi-worker by construction; storage layout is the state machine (Burr comparison already recorded in decision 0008) |
| File/embedded queues | maildir, persist-queue, litequeue, huey | Single machine, single language, no spec | Written language-portable contract; S3 + POSIX; typed models per path |
| Industrial UNS | MQTT + Sparkplug B; HiveMQ, HighByte, Litmus, iiot.university | A broker holds the namespace; current state = retained messages in broker memory | Same path-as-identity thesis, but durable at rest: all three trichotomy roles (queue/WAL/index), no broker to keep alive, history intrinsic rather than a bolted-on historian |
| Table formats | Delta Lake, Iceberg | Analytics-scale tables, heavy ecosystem | Same manifest/compaction ideas at ops scale, human-readable, zero infra |

The differentiated bundle — no one adjacent has all four: **(1)** written
on-disk contract independent of any implementation, **(2)** no server of
any kind, **(3)** same logical paths on local disk and S3, **(4)** the
inspector for free because state is already files.

## TAM hypotheses, ranked by current evidence

1. **AI-agent system builders.** Strongest hypothesis. Agents need durable,
   auditable, resumable coordination; opaque broker state is actively
   hostile to debugging agent behavior; "the agent's work queue is a folder
   a human can read" is a compelling pitch *right now*. task-agent is the
   existence proof, and its MCP server shows the integration path.
2. **Edge / small-fleet operators** (Raspberry Pi clusters, homelab,
   retail/IoT edge). cocli's Pi scraper fleet is the existence proof.
   These users *cannot* run Kafka and resent running Postgres for a queue.
3. **Data-engineering-lite** — teams for whom Dagster/Airflow is too much
   ceremony but cron-plus-hope is too little. The trichotomy
   (queue/WAL/index) gives them vocabulary for what they're already doing
   badly in ad hoc folders.
4. **Local-first / plain-text-ecosystem developers** — people who already
   believe files are the durable substrate and want coordination without
   abandoning that belief.
5. **Industrial UNS / Industry-4.0 practitioners** — a segment unlike the
   others because it is **pre-sold on the thesis**: the UNS movement
   (Walker Reynolds / iiot.university; HiveMQ, HighByte, Litmus) has spent
   years evangelizing hierarchical-namespace-as-single-source-of-truth,
   with courses, conferences, and consultants. The teaching is done; only
   the mechanism differs (broker + retained messages vs files at rest —
   see LINEAGE.md, topic hierarchies). Honest friction: that community
   *expects* real-time pub/sub, and rename-and-CAS is not
   report-by-exception millisecond delivery. The wedge is therefore not
   "replace your broker" but (a) the durable, inspectable substrate
   *under* the namespace — intrinsic WAL where they bolt on historians —
   and (b) UNS for edges that can't or won't run a broker, which loops
   back into segment #2.
6. **Other-language implementers** — people who would never adopt the
   Python library but might implement the *spec* (see maildir precedent
   below). Smallest group, highest leverage per person.

## Validation before promotion

Do this before spending on content. The goal of the first phase is
*disconfirmation*: find out which hypothesis above is wrong cheapest.

- **Ten conversations, Mom-Test style.** Not "would you use stations?"
  (everyone lies) but "how do you coordinate work between your workers
  today, and what did that cost you last month?" If their answer contains
  a war story, show the inspector. Where they live: r/selfhosted,
  r/dataengineering, HN, lobste.rs, the Dagster and Temporal community
  Slacks (their overflow users are the prospects), agent-builder Discords.
- **Signals that count** (in ascending order of meaning): stars → issues
  opened by strangers → "can it do X" questions → **someone builds a
  consumer you didn't write**. Only the last one is product-market fit;
  the first is vanity.
- **Signals to ignore:** praise from people who will never run it;
  comparisons to Kafka from people who need Kafka.

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
   single-writer invariants. War stories outperform feature tours.
3. **Show HN once, deliberately.** After the inspector gif, the spec
   landing page, and a 10-minute quickstart exist. Title shaped like the
   positioning line ("Stations – distributed queues with no broker, just
   rename() and CAS"), not like a product launch.
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
   - **MQTT/UNS bridge** — publish each index station's `CURRENT` values
     into a UNS topic tree (station path → ISA-95-style topic), and/or
     ingest a UNS subscription into a station WAL. Cheap in both
     directions because the namespaces are already isomorphic; turns the
     historian bolt-on problem into "point it at the WAL."
6. **Conference-talk shape** (later): "The filesystem is a state machine"
   — the LINEAGE.md material (statio/status, Petri nets, maildir) is the
   talk skeleton.

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

- **LLM-driven UNS transforms (Burr × UNS × stations).** The industrial
  UNS gives an agent a semantically organized, real-time picture of an
  operation; Burr-style agentic loops give it decision structure; what
  neither provides is a durable, auditable, resumable substrate for the
  agent's *actions*. Stations is that missing third leg: the agent reads
  namespace present-state (index stations / the MQTT bridge above),
  proposes typed transforms, and every action lands as a WAL fact a human
  can `ls` and audit after the fact. The Burr-persister and MQTT-bridge
  adapters (§5 above) are each modest alone; *composed*, they describe an
  auditable industrial-agent architecture that none of the three
  communities currently has a name for.
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
- [ ] Spec landing page: positioning line, the four-point bundle, quickstart.
- [ ] License check: spec CC-BY/Apache-2.0, package licensing decision recorded as a decision doc.
- [ ] Ten discovery conversations (log outcomes in this file).
- [ ] Genesis-story video/post no. 1.
- [ ] MCP-server-over-station-root spike (ties to hypothesis #1).
