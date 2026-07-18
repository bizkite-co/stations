# Physical Contract: bytes on disk

Status: draft v0 (2026-07-17). Normative keywords MUST / SHOULD / MAY are used per RFC 2119.
All terms of art (station, transform, edge role, the trichotomy, claim/lease, watermark,
single-writer rule) are defined in [GLOSSARY.md](../GLOSSARY.md) and are not redefined here.

This document is the **static half** of the on-disk contract: what a conforming writer
produces and what a conforming reader may rely on. The dynamic half — who may write when,
the lease protocol, compaction ordering, crash recovery — is
[CONCURRENCY.md](./CONCURRENCY.md). Invariants here are numbered `P1…` so the concurrency
spec can cite them.

Provenance: distilled from cocli ADR-010/011 (queue/lease), ADR-013 (hash-sharded index and
compiler), `wal-strategy.md`, and `compaction-and-checkpointing.md`. Those documents remain
product-specific; this one is the portable statement.

## 1. Serialization formats

A station declares exactly one serialization format. Three are recognized in v1:

| Format | Shape | Use when |
| :--- | :--- | :--- |
| **USV** | headerless delimited rows, many records per file | high-volume homogeneous records; the bulk format for WAL segments and index shards |
| **JSON file-per-object** | one record per file | records written atomically by concurrent producers (queue items, leases, inbox cells, pointer files) |
| **Markdown + YAML frontmatter** | one record per file, human-authored body | records humans read and edit in place (tasks, decisions, docs-as-records) |

### 1.1 USV

- Encoding is UTF-8. Field delimiter is `U+001F` (UNIT SEPARATOR). Record delimiter is
  `\n` (LF). Files are **headerless**.
- Field values MUST NOT contain `U+001F` or LF. Writers MUST reject or sanitize offending
  values at write time; readers MAY treat a violation as file corruption.
- Column order and column meaning are defined **solely** by the station's schema sidecar
  (§1.4). There is no in-band self-description; a USV file separated from its sidecar is
  not interpretable, by design.

### 1.2 JSON file-per-object

- One JSON document per file, UTF-8. The file is written whole and replaced whole — no
  in-place patching (a transform is a whole-record operation; GLOSSARY § Transform).

### 1.3 Markdown + frontmatter

- YAML frontmatter carries the typed fields; the body is free-form content. The
  frontmatter fields are the record for schema purposes; the body is an opaque payload.

### 1.4 Schema sidecar

- Every station whose format is USV MUST have a [Frictionless Data](https://frictionlessdata.io)
  `datapackage.json` at the station root (or nearest ancestor governing multiple sibling
  stations), whose resource `path` glob matches the station's data files.
- The sidecar's field list is normative for column order (P1). Any change to the field
  list — add, remove, reorder, retype — is a **schema version change**. Version transition
  policy is deferred to a future SCHEMA-EVOLUTION spec; until then the v1 rule is:
  a writer MUST NOT change the field list of a station that has live readers.

## 2. Identity and file naming

- Every record has a stable **identity**: either a natural key declared in the schema
  (e.g. `place_id`, `domain`) or a content hash of declared identity fields.
- Where a record is stored file-per-object, its filename MUST be derived from its
  identity — never from a mutable attribute (a title, a status). This is what makes
  duplicate writes idempotent: writing the same record twice produces the same path (P2).
- Identity is what records use to reference each other across stations
  (GLOSSARY § Cross-repo referencing). A path encodes current station membership only.

## 3. Common directory discipline

- **No partially visible files.** A file MUST NOT be observable at its final path in a
  partially written state. Locally: write to a `tmp/` sibling (or `.tmp` suffix) on the
  *same filesystem*, fsync, then atomic-rename into place — the maildir discipline. On S3:
  a PUT is already all-or-nothing, so direct PUT is conforming (P3).
- **`tmp/` is dead on arrival.** Any file under a station's `tmp/` belongs to no one after
  a crash. Recovery MAY delete any tmp file older than a small grace period; no reader may
  ever read from `tmp/` (P4).
- A directory's role (queue/WAL/index) is a per-consumer edge declaration, not a physical
  property — but the layouts below are the standard physical shapes those roles take.

## 4. Queue station layout

```
{queue}/
├── datapackage.json            # schema of the item payload (if USV) or JSON schema note
├── tmp/                        # enqueue staging (local backends)
├── pending/
│   ├── {shard}/                # optional sharding, §7
│   │   ├── {item-id}.json      # the work item payload
│   │   └── {item-id}.lease     # present only while claimed — see CONCURRENCY §2
├── completed/
│   └── {shard}/{item-id}.json  # terminal: item + result, moved here exactly once
└── failed/
    └── {shard}/{item-id}.json  # terminal: item + error record
```

- An item is **enqueued** by appearing in `pending/` (via §3 atomic placement).
- An item is **claimed** by the existence of a valid lease record beside it
  (`{item-id}.lease`); lease record contents and validity are specified in
  CONCURRENCY §2. The claim marker sits *beside* the item rather than moving it, because
  S3 has no atomic rename; the marker style is the one primitive that works on both
  backends (P5).
- An item reaches a **terminal state** by being written to `completed/` or `failed/` and
  then removed from `pending/` — in that order, so a crash between the two operations
  leaves a duplicate (safe, detectable by identity) rather than a lost item (P6).
- Deleting a queue loses pending work but no history (GLOSSARY trichotomy).

## 5. WAL station layout

Two conforming physical shapes, chosen by write concurrency:

**Shape A — segment files** (one writer appends to its own segment):

```
{wal}/
├── datapackage.json
└── {period}_{writer-id}.usv    # e.g. 20260318_worker1.usv; append-only
```

**Shape B — file-per-record** (many concurrent writers, no shared file):

```
{wal}/
├── datapackage.json
└── {shard}/{record-id}.usv     # one record per file; maximally sharded segments
```

- A WAL file is **append-only**: a writer MUST NOT modify or reorder previously written
  bytes. In Shape A, exactly one writer may append to a given segment (its name embeds the
  writer identity); in Shape B, per-file atomicity (§3) does the same job (P7).
- Records MUST carry the fields the fold needs for deterministic merge — at minimum the
  identity key and a monotonic version stamp (e.g. `updated_at`) for last-write-wins (P8).
- WAL segments are retired **only** by compaction (CONCURRENCY §3), never edited.
- Some logs are declared **retained** (never deleted; e.g. a discovery log kept for
  traceability). Retention is a station-level declaration and changes the compaction mode
  (CONCURRENCY §3.4); it does not change this layout.

## 6. Index station layout

The layered write-back shape (an LSM tree over paths — cocli ADR-013):

```
{index}/
├── datapackage.json
├── CURRENT                     # the commit pointer — the single atomic truth (§6.1)
├── inbox/                      # L1: high-concurrency write intake (a WAL, Shape B)
│   └── {shard}/{record-id}.usv
├── shards/                     # L2: high-density folded base
│   └── {shard}.usv
└── checkpoint.{gen}.usv        # optional single-file consolidated form
```

Not every index needs every layer: a small index may be just `CURRENT` + a checkpoint
file; a large one uses inbox + shards. The contract is the same either way.

### 6.1 The commit pointer (`CURRENT`)

A small JSON file naming the current committed generation of the index. It is the **only**
file whose update constitutes a commit; everything else is either immutable once written
(generation files) or an un-committed write intake (inbox).

```json
{
  "generation": 42,
  "checkpoint": "checkpoint.000042.usv",
  "created_at": "2026-07-17T18:04:11Z",
  "compactor_id": "cocli5x0/pid-2211",
  "mode": "consuming",
  "folded": null,
  "content_hash": "sha256:9f2c…"
}
```

- Generation data files (`checkpoint.{gen}.usv`, or a generation-stamped shard set) are
  written completely, then `CURRENT` is swung to reference them: atomic rename locally,
  conditional PUT (`If-Match` on the prior ETag) on S3 (P9). This imports the
  LevelDB/RocksDB `CURRENT`/MANIFEST pattern — one tiny file is the commit point, so
  multi-file index states never need multi-file atomicity.
- A generation file not referenced by `CURRENT` is garbage: recovery MAY delete it,
  readers MUST NOT trust it (P10).

### 6.2 Watermark

The watermark states how much of the source log is folded into the committed generation
(GLOSSARY § Watermark). Its physical form depends on compaction mode:

- **Consuming mode** (`"mode": "consuming"`, sources deleted after fold): the watermark is
  *implicit* — any segment still present in the source station is not yet folded, because
  folded segments are removed only after commit (CONCURRENCY §3). `"folded"` is `null`.
- **Retained mode** (`"mode": "retained"`, sources kept): `"folded"` MUST record the folded
  frontier explicitly — either the list of folded segment names or a per-writer
  high-water segment name. File mtimes MUST NOT be the correctness mechanism for
  freshness; they MAY be used as an over-approximating heuristic only (P11).

### 6.3 Hybrid reads

A reader wanting current state loads the committed generation, then merges any not-yet-
folded source records (inbox files; segments beyond the watermark) using the same
deterministic fold the compactor uses. Because the fold is idempotent (CONCURRENCY C2),
**over-reading is safe and under-reading is not**: a freshness scan MAY include already-
folded records but MUST NOT miss unfolded ones (P12).

- An index without a readable `CURRENT` is not trustworthy as "current"; the reader's
  options are rebuild-by-replay or fail (GLOSSARY § Watermark).
- Deleting an index loses only time — it is always rebuildable by replaying the retained
  logs (trichotomy). If an index would *not* survive this test, it is independent state
  mislabeled as an index (METHOD anti-patterns) and this layout does not apply.

## 7. Sharding

Sharding is a physical partitioning strategy orthogonal to role (DESCRIPTION thesis). The
v1 scheme, where used: `shard = sha256(identity)[:2]` — 256 buckets, hex-named. The shard
function MUST be deterministic from identity alone, and MUST be declared alongside the
schema so independent writers compute the same placement (P13).

## 8. Invariants (summary)

| # | Invariant |
| :--- | :--- |
| P1 | USV column order is defined solely by the schema sidecar; changing the field list is a schema version change |
| P2 | File-per-object names derive from immutable identity; duplicate writes are idempotent |
| P3 | No file is observable at its final path partially written (tmp+rename locally; whole PUT on S3) |
| P4 | `tmp/` contents are never read and may be reaped after crash |
| P5 | Queue claims are marker-style (lease beside item) — the one primitive portable across FS and S3 |
| P6 | Terminal-state write precedes pending-state removal; crashes duplicate, never lose |
| P7 | WAL bytes are append-only; one writer per Shape-A segment |
| P8 | WAL records carry identity + monotonic version stamp sufficient for deterministic merge |
| P9 | `CURRENT` is the sole commit point; updated atomically (rename / conditional PUT) |
| P10 | Generation files unreferenced by `CURRENT` are garbage |
| P11 | Retained-mode watermarks are explicit in the commit record; mtime is never load-bearing |
| P12 | Freshness scans may over-approximate, never under-approximate |
| P13 | Shard placement is a declared deterministic function of identity |

## What this spec deliberately does not fix

- **Binary codecs.** USV + JSON + Markdown are the v1 codecs; the layouts above are a
  logical contract a future codec could satisfy behind the same `CURRENT`/watermark
  semantics (DESCRIPTION § What we deliberately do NOT build).
- **Schema migration policy** — deferred to SCHEMA-EVOLUTION (stub pending); v1 rule in §1.4.
- **The identity registry** — identity *format* is fixed here (§2); resolution
  infrastructure is GLOSSARY § Cross-repo referencing, deferred.
