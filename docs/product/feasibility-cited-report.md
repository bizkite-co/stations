# Feasibility review (2026-08-31 / 2026-09-01)

Archived product review: is stations a real gap, who is adjacent, who might
use it. Working positioning lives in [ADOPTION.md](../ADOPTION.md); this file
keeps the cited research and the session tables that fed that fold.

**Provenance.** Session review 2026-09-01 plus a deep-research run
(`wf_01a05b9e1f007642b585d5cf820281f5`, status: Partial). Also attached to
task-agent parent
`close-spec-impl-and-positioning-gaps-from-the-2026-feasibility-review`.

**Verdict in one line.** The idea is valid. The 2026 market is real but
small. The repo is a pattern language plus a young reference library — not
a product a stranger should run workers on yet.

---

## What stations actually is

Stations is **durable coordination of records at rest**, not durable
execution of code.

| They persist | Stations persists |
| :--- | :--- |
| Control flow of functions (Temporal, Hatchet, DBOS) | Where a typed record currently stands |
| Scheduler + metadata about tables (Dagster, Airflow) | The record's location *as* its state |
| An in-process state blob (Burr, LangGraph checkpointers) | Many records, each at a path, concurrently |
| A FIFO of jobs (SteadQ, dirq, persist-queue) | A graph of typed stations with three consumption roles (queue / WAL / index) |

The one-line that survives contact with buyers: **the queue you can `ls`**.
"Lightweight Temporal" and "broker-free Kafka" are false.

---

## 2026 landscape — neighbors on every edge

The four-point uniqueness claim (written contract, no server, same paths on
POSIX and S3, inspectability) is still true *if interpreted strictly as one
product*. The region is no longer empty.

| Product | What it is | Why it matters |
| :--- | :--- | :--- |
| [SteadQ](https://davidtorcivia.com/posts/steadq) (Aug 2026, Apache-2.0, Rust) | Brokerless Linux filesystem job queue. Jobs are files; claim by `renameat2(RENAME_NOREPLACE)`; leases, receipts, dead-letter, crash-lab, TLA+. Author independently restates "files should be true." | Closest *product* cousin. Same thesis, queue-only, POSIX-only, more engineered than stations' runtime. |
| [StowQ](https://github.com/davidtorcivia/StowQ) | S3/object-store sister: claim objects via conditional create. | Same author, **different protocol** from SteadQ. Occupies the S3-CAS queue slot. |
| [lakestream S3-Queue](https://github.com/lakestream-io/leaderless-log-protocol) | Spec-first S3 log/queue with compaction, cursors, fencing; GTM is "paste the spec into an agent." | Same spec-first go-to-market. Kafka-shaped on S3, not path-as-FSM. |
| [jqueue](https://github.com/janbjorge/jqueue) | One `queue.json` blob, CAS on local file or S3. | The only small product that actually does POSIX+S3+no-server — by *refusing* path-as-state. |
| CERN dirq (Perl/Python/Java/C, unmaintained) | Language-portable directory queue. | Historical proof that **spec + multi-language** is how this pattern spreads. |
| [Filespooler](https://www.complete.org/filespooler/) (John Goerzen) | Files *are* the network; Syncthing/S3/USB as transport; ordered packets. | Unix-philosophy cousin. Sequential, not multi-worker leases. |
| fsq, IPC::DirQueue, nq, persist-queue, FileHuey | Recurring maildir-as-jobs. | Demand is real and old. None generalized to types + S3 + WAL/index. |
| [Beads](https://github.com/gastownhall/beads) (~27k stars as of 2026-08-31), tbd, pebbles, claude-task-master (~26k) | Git-backed agent issue graphs. Anthropic's Claude Tasks copied the shape. | Occupies "agent memory as files." Different job: planning/amnesia, not fleet claim. |
| Name collision: [jeremy0dell/station](https://github.com/jeremy0dell/station) | Terminal control plane for agent worktrees. | Unrelated, but "station" is a crowded word in agent-tooling in 2026. |

Honest 2026 sentence:

> Broker-free file and object queues now exist as serious spec-first
> projects. None of them is a **typed, dual-backend, inspectable station
> graph** whose layout is the state machine for queue *and* WAL *and*
> index. The nearest substitute is SteadQ locally and StowQ remotely —
> two protocols, two encodings, queue-only.

### False comparisons to refuse

| They say | Reality |
| :--- | :--- |
| Kafka | Need independent consumer groups, replay, 10k+ partitions. Stations is a work queue + WAL of records. People who need Kafka should buy Kafka. |
| SQS / Rabbit | Managed at-least-once *messaging*. Stations is inspectable *state*. |
| Temporal | Code durability vs data-at-rest. |
| Iceberg | Analytics tables vs ops records. |
| CrewAI / LangGraph | Agent framework vs substrate. Stations has no LLM loop. |
| Redis / Celery | Throughput-first queues. Stations will lose a benchmark and win `ls`. |
| "Broker-free UNS" | OT will hear "you turned off MQTT." Don't. |

---

## Technical validity (claims stress-tested)

| Claim | Rating | Why |
| :--- | :--- | :--- |
| Storage layout is the state machine; no broker | Partially true | Layout encodes *where a record stands*, not *who fires*. S3/cron still coordinate. |
| POSIX rename + S3 CAS suffice for claim | Design: yes. Impl: overstated | Spec correctly uses **sibling `.lease` create-if-absent**, not rename (S3 has no rename). Local `replace_if_match` is check-then-rename, not CAS. |
| Same logical paths on disk and S3 | Path strings yes; semantics no | chmod, listing, etags, codecs differ. |
| Inspector is nearly free | Cheap to *build*; not cheap to *run* at scale | Tree walk + S3 LIST. Dual-role directories get mislabeled. |
| Spec is language-portable (maildir) | In principle; not yet | Draft v0. Schema evolution, identity registry, done_check deferred. No golden fixtures. |
| Queue / WAL / index trichotomy | Useful; not complete | Excellent diagnostic. Does not cover in-place edits, delay/priority, real-time fanout. |
| Single-writer + emission edges prevent split-brain | Overstated | `CURRENT` CAS is the real safety (if CAS is real). Emission routing is log-only in the engine. No fencing token. |
| Three consumers prove generality | Overstated | cocli is the origin. task-agent mapping is unratified. Video pipeline has no `consumers/` doc. |
| Engines not shipped is OK | Stale as of the review | Engines were already in the tree; docs said Phase 3. (Docs alignment landed 2026-09-01.) |

Adoption-killing technical risks if promoted now: S3-compat conditional PUT missing or wrong; listing-based workers at queue depth; at-least-once without fencing plus unimplemented "terminal already exists" recovery; local CAS TOCTOU on a shared disk; NFS users hitting the non-conforming-backend clause.

---

## Who the users actually are

Ranked by chance a *stranger* tries this in 12 months, not TAM poetry.

| Rank | ICP | Job stations uniquely does | Kill signal |
| :--- | :--- | :--- | :--- |
| 1 | Agent system builders who outgrew Markdown and are not ready for Temporal | Multi-worker *claim* of a typed work item, mid-flight `ls`, laptop and S3 prefix. **Not** the Beads user. | "Beads + git is enough" |
| 2 | Local-first / "files are true" developers | Typed directories + inspector beat JSONL+SQLite for people who debug with `rg` and `ls`. | A 200-line maildir is enough; spec looks heavy |
| 3 | Edge / homelab / Pi / HPC login nodes | Claim via exclusive-create on a shared FS or MinIO; inspect without a VPN to a dashboard. | They copy `mv` + flock, or already run Redis on the Pi |
| 4 | Data-engineering-lite (`inbox/` / `staging/` / `out/` + cron) | Trichotomy names what they're doing badly; `stations inspect` replaces "which folder is stuck." | They install Prefect in an afternoon |
| 5 | Other-language spec implementers | PHYSICAL-CONTRACT + CONCURRENCY as the thing they implement against. | Only Python users, asking for Celery features |
| — | Industrial UNS / HiveMQ / HighByte | **Not a 2026 beachhead.** Thesis overlap, opposite mechanism. | OT: "this isn't real-time" |

**Not first users:** Temporal Cloud buyers, Kafka shops, HiveMQ RFPs, lakehouse platforms, CrewAI/LangGraph app builders.

---

## Feasibility as a project

| Question | Answer |
| :--- | :--- |
| Is the idea fake? | No. Independently rediscovered in Aug 2026 (SteadQ), and every 5–10 years before that. |
| Is there a gap? | Yes, but narrow: **typed station graph + one POSIX/S3 contract + inspectable files**. File-as-queue is taken. Agent-as-issue-tracker is taken. |
| Can you win as a Python library? | Unlikely soon. persist-queue, huey, litequeue already exist for "Python queue on disk." Strangers who want a queue will pick SteadQ's CLI. |
| Can you win as a spec? | That's the actual maildir play. The spec is not yet implementable-and-testable by a stranger. |
| Is it premature to promote? | Yes, until CAS, terminal-exists recovery, and docs/spec/impl agree. |
| Is it worth continuing? | Yes, as the named substrate for *your* systems, and as a spec you freeze before Show HN. |

PMF is a **stranger-built consumer**. Author dogfood is one data point.

---

## Cited research report

**Status: Partial** (deep-research workflow, 2026-08-31)

A spec-first, broker-free, dual POSIX-rename and S3-conditional-PUT state machine of typed records in directories—with no server and `ls` as the inspector—does not exist among the compared products. [S20] The nearest brokerless cousins split that design in two (local directory rename vs object-store claim CAS); older file queues and blob/log queues stay broker-free without a typed multi-station path contract; durable-execution engines, orchestrators, lake table formats, and MQTT Unified Namespace keep state in services, catalogs, or brokers rather than path membership. [S1][S2][S3][S4][S5][S6] Files and object stores are already used as production queues and shuffle media, but those deployments are mail trees, append files, rename-as-commit, or S3 shuffle objects—not a language-portable on-disk-plus-S3 contract with a Python reference. Product-market fit is defined as an independent third-party consumer and is disconfirmed if that never appears, if buyers reject path inspectability, or if the work already fits Temporal, Airflow/Dagster, or Iceberg. [S15][S17][S19]

### Closest broker-free file and object queues

SteadQ is a daemonless Linux directory queue of immutable job files whose pathnames encode ownership and whose transitions are atomic no-overwrite `renameat2`; layout is `ready/`, `delayed/`, `dead/`, `receipts/`, `quarantine/`, and `tmp/` on local ext4, XFS, btrfs, f2fs, or ZFS only (NFS/FUSE rejected, no S3 conditional PUT). StowQ is the remote analogue: a key prefix in one certified bucket (Cloudflare R2, Amazon S3, Google GCS, Azure Blob), jobs as immutable objects, ownership as a chain of immutable claim objects, and transitions as atomic conditional creations, with no daemon, leader, database, or broker.

maildir, Filespooler, fsq, and qlobber-fsq are write-then-rename (or `flock`) directory queues, not typed multi-station path machines and not coordinators via S3 `If-Match`/`If-None-Match` PUT (Filespooler may use S3 only as a filesystem transport). Maildir is a lock-free mailbox (`tmp` → `new` → `cur` as `uniq:info`); extra files are mail-delivery artifacts, not WAL or index stations. [S13] Filespooler is a sequential command-execution spool (`queuedir/{nextseq,nextseq.lock,jobs/}`, Rust `fspl` CLI), not a typed path state machine. [S14] qlobber-fsq is a Node.js npm library with a concrete `fsq_dir` layout (staging/messages/topics), `flock` work-queue claims, no delivery-order guarantee, possible drop on crash, and no language-portable on-disk spec. [S16]

jqueue, persist-queue, and Leaderless-Log S3-Queue are broker-free storage queues that are not per-record directory/object-path machines: jqueue is one JSON blob mutated with `If-Match` CAS (local `fcntl.flock`); persist-queue is pickle files or SQLite `put`/`get`/`task_done`; S3-Queue is an offset log coordinated by S3 conditional writes (produce/consume/ack, compaction, fencing). StowQ and S3-Queue ship language-agnostic object-store specs with Rust reference CLIs and no dual POSIX+S3 path layout.

### Servers, catalogs, and brokers (not path state)

Temporal, Inngest, Hatchet, DBOS, and Apache Burr persist opaque execution state in a server or database and recover by event-history or checkpoint replay of code: Temporal's History Service writes to Cassandra/MySQL/PostgreSQL/SQLite while workers poll task queues; Inngest checkpoints through its engine (Redis as queue/state store when self-hosted); Hatchet keeps workflow state in PostgreSQL; DBOS checkpoints workflows/steps to Postgres with no separate orchestrator besides the database; Burr keeps an in-memory `State` object with SQLite/PostgreSQL/Redis/MongoDB persisters and a telemetry UI.

Airflow, Dagster OSS, and scaled Prefect require long-running scheduler, daemon, and/or API processes plus a metadata database (Prefect also Redis at scale). Iceberg tracks individual data files rather than directories and commits by atomic catalog metadata-pointer swap (rename is optional, only when used to publish new metadata files). MQTT Unified Namespace holds last values as broker retained messages, not files at rest. Delta Lake is closer to self-describing files: a `_delta_log` of JSON (and checkpoint) files on a DFS or object store for serializable ACID writes and snapshot isolation without a required metastore, with a goal of billions of files; S3 still lacks put-if-absent, so multi-cluster writers need DynamoDB LogStore or Databricks' S3 commit service rather than S3 alone. [S12]

### Who uses files or object stores as queues in production

The pattern that has actually shipped is durable files or objects as the work medium—not a typed multi-station contract. Record-append and shuffle copies are at-least-once (padding/duplicates possible); GFS replicates chunks three ways because component failure is the norm; MapReduce leaves completed map output unreplicated on the worker disk (death re-executes maps) and uses GFS atomic rename so duplicate reduce executions leave one winner.

| System | Coordination | Production envelope |
| :--- | :--- | :--- |
| Google GFS | Persistent files with atomic record-append as m-to-1 producer-consumer queues and many-way merge (no extra broker; GFS is efficient at m-to-1, not general queues) | Largest clusters >1000 storage nodes / >300 TB, hundreds of clients; cluster Y write:append 3.7:1 by bytes and 2.5:1 by ops, with empty-read races when consumers outpace producers [S7] |
| Google MapReduce | Local-disk partitioned shuffle; GFS atomic rename of reduce output | Typical terabytes on thousands of machines (e.g. M=200,000, R=5,000, 2,000 workers); August 2004: 29,423 jobs, 3,288 TB input, 758 TB intermediate, 193 TB output, 1.2 worker deaths/job; production indexing >20 TB raw [S8] |
| qmail | Crash-safe inode-named directory tree; enqueue commits by hard link into `todo/`; hashed split directories | 5,000 messages queued in 23 minutes with no slowdown as the queue filled; Red Hat moved a 70,000 msg/day sendmail hub onto qmail on a smaller machine [S9] |
| Postfix | On-disk `maildrop`/`incoming`/`active`/`deferred`/`hold`; in-memory scheduler holds only the active set; incomplete `0600` files ignored | Active default 20,000; deferred ~10⁵–10⁶ practical envelope (good performance unlikely above); Feb 2004 congestion example 11,775 messages with active full at the 10,000 Postfix 1.x limit [S10] |
| AWS Glue Spark | S3 objects as shuffle/spill (`shuffle_<jobid>_<mapperid>_<reducerid>.data`/index); no shuffle-service daemon | TPC-DS q80 failed after >50 GB/worker on 10 G.1X DPUs (~1h25m); completed after 479.7 GB shuffled to S3 in ~2h53m [S11] |

### Gap for a portable on-disk contract plus Python reference

What is missing is one language-portable contract that is both a POSIX directory machine (atomic no-overwrite rename) and an S3 object machine (conditional PUT), with typed records whose directory or key membership is the state, inspectable with `ls` (or equivalent listing) but not claimed by listing. SteadQ is local-filesystem only; StowQ and S3-Queue are object-store-only with Rust references; qlobber-fsq is a Node library rather than a spec; maildir/Filespooler/fsq/jqueue/persist-queue are not that dual path layout. A Python reference would fill a hole those projects do not claim.

The coordination primitive set is deliberately thin and would itself bound the product: every step is one backend primitive; S3 has no atomic rename, so claims are marker-style leases; NFSv2/v3 and S3-over-FUSE are non-conforming for claims; delivery is at-least-once and processing must be idempotent; leases compare clocks and must tolerate skew of at least the TTL safety margin; there are no multi-index transactions (each index commits independently via its own `CURRENT`); rename-and-CAS is not millisecond report-by-exception delivery for UNS-style use. [S21] Amazon S3's create-if-absent `If-None-Match` only shipped 20 August 2024, applies only to the current version, can 409 against concurrent deletes, ignores in-progress multipart uploads, and some endpoints reject the header (`InvalidArgument`/`NotImplemented`). [S22]

### What would disconfirm product-market fit

PMF is not author dogfood, stars, or unused praise—one author already running three consumers (cocli, task-agent, library tooling) counts as a single data point. The ranked signal that counts is a stranger-built consumer the project did not write; absence of that consumer fails the test. Cheap disconfirmation is Mom-Test discovery of how work is coordinated today and what it cost last month (a war story is the cue to show the inspector), not stated purchase intent; those ten conversations remain unlogged. [S18]

Prospects are overflow users of Temporal, Dagster/Airflow, and Iceberg communities—teams for whom those tools are too much ceremony—not people whose job those incumbents already fit (Kafka comparisons from people who need Kafka are ignore signals). Buyer rejection of file-path inspectability rejects the positioning ("the queue you can `ls`"); treating `ls` as a claim would violate the concurrency contract (the only claim is a successful create-if-absent of the lease).

## Sources

- [S1] "SteadQ README" — https://github.com/davidtorcivia/SteadQ
- [S2] "StowQ README" — https://github.com/davidtorcivia/StowQ
- [S3] "Using maildir format (D. J. Bernstein)" — https://cr.yp.to/proto/maildir.html
- [S4] "jqueue README" — https://github.com/janbjorge/jqueue
- [S5] "Temporal architecture" — https://docs.temporal.io/encyclopedia/architecture/temporal-architecture
- [S6] "Apache Iceberg Table Spec" — https://iceberg.apache.org/spec/
- [S7] "The Google File System (SOSP 2003)" — https://static.googleusercontent.com/media/research.google.com/en//archive/gfs-sosp2003.pdf
- [S8] "MapReduce: Simplified Data Processing on Large Clusters (OSDI 2004)" — https://www.usenix.org/legacy/publications/library/proceedings/osdi04/tech/full_papers/dean/dean_html/index.html
- [S9] "qmail (D. J. Bernstein)" — https://cr.yp.to/qmail.html
- [S10] "Postfix Bottleneck Analysis (QSHAPE_README)" — https://www.postfix.org/QSHAPE_README.html
- [S11] "Introducing Amazon S3 shuffle in AWS Glue" — https://aws.amazon.com/blogs/big-data/introducing-amazon-s3-shuffle-in-aws-glue/
- [S12] "Delta Transaction Log Protocol" — https://github.com/delta-io/delta/blob/master/PROTOCOL.md
- [S13] "Using maildir format (D. J. Bernstein)" — https://cr.yp.to/proto/maildir.html
- [S14] "fspl(1) — filespooler — Debian Manpages" — https://manpages.debian.org/unstable/filespooler/fspl.1
- [S15] "S3-Queue Service Specification" — https://github.com/lakestream-io/leaderless-log-protocol/blob/main/examples/s3-queue/SPEC.md
- [S16] "qlobber-fsq README" — https://github.com/davedoesdev/qlobber-fsq
- [S17] [S18] [S19] [S20] [ADOPTION.md](../ADOPTION.md) (as of the review; later folded)
- [S21] [CONCURRENCY.md](../../spec/CONCURRENCY.md)
- [S22] "How to prevent object overwrites with conditional writes" — https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html

## Coverage and uncertainty

- No listed product implements both POSIX atomic rename and S3 conditional PUT in one typed, multi-station path contract; SteadQ and StowQ are sibling protocols, not one dual-backend spec.
- Filespooler can use S3/rclone as a transport filesystem; that is not S3 conditional PUT as the linearization primitive.
- persist-queue file internals were not read from source, only the PyPI API.
- Delta Lake's catalog/log commit path was not fetched as a primary spec; do not read the Iceberg claim as a fully verified Delta claim.
- Burr's optional filesystem/S3 tracking is telemetry snapshots, not a directory of typed records.
- Chronicle Queue claims a broker-less memory-mapped filesystem queue (HFT); inspected sources are vendor docs without a named independent production deployment.
- CERN dirq was used at CERN; inspected READMEs give no production scale numbers.
- Spotify Luigi treats HDFS/S3 target existence as task completion, but production also used a central scheduler.
- MapReduce and Glue still have a job master/driver; the filesystem/object store is the shuffle/commit medium, not a replacement for all coordination.
- Whether a "real gap" exists in demand or only in positioning: the four-part bundle was the project's own comparison, not an independent market survey. That is why this review exists.
- A Python implementation of the S3-Queue SPEC is explicitly invited by that SPEC.
- No logged Mom-Test outcomes or independent consumers exist; market rejection is specified as a test, not observed.
- Claim excluded by verification: SteadQ is Linux-local rename/lease/ack, Experimental; the cited contract does not explicitly reject object stores (StowQ is the sister).
- Claim excluded by verification: engines (`DefaultTransformEngine`, `DefaultCompactor`) were already implemented at review time; docs that said they were still planned were stale (fixed 2026-09-01).
