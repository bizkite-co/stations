# Concurrency Contract: leases, compaction, crash recovery

Status: draft v0 (2026-07-17). Normative keywords MUST / SHOULD / MAY per RFC 2119. Terms
are defined in [GLOSSARY.md](../GLOSSARY.md); physical layouts and invariants `P1…` are
defined in [PHYSICAL-CONTRACT.md](./PHYSICAL-CONTRACT.md). Invariants here are numbered
`C1…`.

This is the **dynamic half** of the on-disk contract: the state machines that let multiple
unreliable workers coordinate through storage alone. Everything in this document reduces to
two ideas: (1) every multi-step operation has exactly one atomic commit point, and
(2) every crash window on either side of that point is made safe by idempotence, not by
cleanup that must succeed.

Provenance: cocli ADR-010 (local lease lifecycle), ADR-011 (S3 conditional leases),
ADR-013 COMPILER.md (distributed compiler and locking), `wal-strategy.md`.

## 1. Backend primitives

The whole contract is built on the atomic test-and-set / atomic swap each backend provides:

| Primitive | Local filesystem | S3-class object store |
| :--- | :--- | :--- |
| Create-if-absent (test-and-set) | `open(O_CREAT \| O_EXCL)` | `PutObject` + `If-None-Match: "*"` → 412 on loss |
| Replace-if-unchanged (CAS) | atomic `rename(2)` over prior file | `PutObject` + `If-Match: <etag>` → 412 on loss |
| Whole-file visibility | write tmp → fsync → rename (P3) | single PUT is all-or-nothing |
| Delete | `unlink` | `DeleteObject` |

- A conforming implementation MUST express every coordination step as one of these
  primitives. No step may depend on two storage operations happening together (C1).
- Network filesystems: NFSv4 and SMB support atomic exclusive create; NFSv2/v3 and
  S3-over-FUSE do not and are non-conforming backends for claims (cocli ADR-010
  compatibility matrix).
- Clocks: lease expiry compares timestamps written by one machine against another's clock.
  Implementations SHOULD prefer storage-authored times (S3 `LastModified`) over
  writer-authored times where available, and MUST tolerate skew of at least the lease TTL
  safety margin (§2.3).

## 2. The lease protocol (queues)

### 2.1 Item states

An item in a queue station (P-contract §4) is in exactly one of:

```
            enqueue                claim                 complete
  (absent) ────────▶ AVAILABLE ────────────▶ LEASED ───────────────▶ TERMINAL
                        ▲                      │                (completed/ or failed/)
                        └──────────────────────┘
                             lease expiry
```

Observable on disk:

| State | Files present |
| :--- | :--- |
| AVAILABLE | `pending/{shard}/{id}.json` |
| LEASED | `pending/{shard}/{id}.json` + `pending/{shard}/{id}.lease` (valid) |
| LEASED (expired) | same, but lease record's expiry has passed — equivalent to AVAILABLE |
| TERMINAL | `completed/…/{id}.json` or `failed/…/{id}.json`; nothing under `pending/` |

### 2.2 Claim

1. **Discover**: list `pending/` (or a random shard of it); shuffle candidates so
   concurrent workers spread out rather than racing head-of-line.
2. **Claim**: attempt create-if-absent of `{id}.lease`. Success = ownership; failure
   (EEXIST / 412) = someone else owns it; skip to the next candidate. This is the only
   claim mechanism — a directory listing is never a claim (C2).
3. The lease record MUST contain at least: `worker_id`, `claimed_at`, `expires_at`, and
   an `attempt` counter.

### 2.3 Expiry and reclaim

- A lease with `expires_at` in the past is dead. Any worker MAY reclaim the item by
  **CAS-replacing** the expired lease record with its own (rename-over locally,
  `If-Match` on the dead lease's ETag on S3) — never by delete-then-create, which has a
  race window between the two operations (C3).
- A worker still running past its own lease expiry MUST assume it has lost ownership: it
  MAY finish its local computation but MUST NOT write terminal state (C4).
- Consequence: delivery is **at least once**. Item processing MUST be idempotent —
  identity-derived output paths (P2) make duplicate completions converge (C5).
- Long tasks SHOULD renew (`CAS` the lease with a later `expires_at`) before expiry rather
  than requesting long TTLs up front.

### 2.4 Completion

1. Write the terminal record to `completed/` (or `failed/`) via P3 atomic placement.
2. Remove `pending/{id}.json`, then the lease file.

Ordering is normative (P6): terminal-write first, pending-delete second.

### 2.5 Crash matrix (lease)

| Crash point | State found later | Recovery | Loses anything? |
| :--- | :--- | :--- | :--- |
| after claim, before/during work | valid-then-expiring lease beside item | lease expires; item reclaimed | no (at-least-once) |
| after terminal write, before pending delete | item in both `completed/` and `pending/` | any worker re-claims, sees terminal record exists (identity match), deletes pending copy | no — duplicate, not loss |
| after pending delete, before lease delete | orphan `.lease` with no item | reaper deletes leases with no sibling item | no |

## 3. The compaction protocol (WAL → index)

One compactor folds source segments into a new index generation and commits it by swinging
`CURRENT` (P9). The protocol is written for the layered layout (P-contract §6) but applies
identically to the simplest checkpoint-only index.

### 3.1 Preconditions

- The compactor holds the compactor role for this index (§4). There is never more than one
  *committing* compactor per index — that is the single-writer rule made operational.
- Inputs are only files that (a) live in the declared source station(s) and (b) conform to
  the declared schema. A non-conforming file MUST be skipped and reported, never folded,
  never deleted (C6).

### 3.2 The fold

- The fold MUST be **deterministic** (same input set → byte-identical output) and
  **idempotent** (re-folding an already-folded record changes nothing). The v1 fold is:
  group by identity key, keep the record with the greatest version stamp
  (last-write-wins), ties broken deterministically (e.g. lexicographic on content) (C7).
- C7 is the load-bearing invariant of the whole document: it is what makes every crash
  window below safe, and what makes hybrid reads (P12) consistent with committed state.

### 3.3 Steps

```
1. Read CURRENT           → current generation G, watermark
2. Enumerate sources      → segments/inbox cells beyond the watermark, schema-conforming
3. Fold                   → write generation G+1 files completely (tmp → rename, or PUT)
4. COMMIT: swing CURRENT  → CAS: rename locally / If-Match(ETag of CURRENT@G) on S3
5. Delete folded sources  → only segments enumerated in step 2   (consuming mode)
6. GC old generations     → delete files referenced by neither CURRENT nor a grace window
```

- Step 4 is the **only** commit point. Before it, nothing observable changed (new
  generation files are unreferenced garbage per P10). After it, the new state is fully
  committed and everything remaining is idempotent cleanup (C8).
- Step 5 MUST happen only after step 4's success is confirmed, and MUST delete only the
  exact segment set enumerated in step 2 — segments that arrived during the fold are the
  next cycle's input, not this one's cleanup (C9).
- If the CAS in step 4 fails (another committer won), the compactor MUST abandon: delete
  its G+1 files, delete nothing else, and retry from step 1 (C10).

### 3.4 Consuming vs retained sources

- **Consuming** (default): step 5 deletes folded segments; the pending set is exactly what
  remains (implicit watermark, P-contract §6.2). The not-yet-compacted segment set is a
  queue whose only consumer is the compactor (GLOSSARY trichotomy, subtlety 1).
- **Retained** (declared per station, e.g. a discovery log kept for traceability): step 5
  is skipped; step 4's commit record MUST carry the explicit folded frontier (P11), and
  step 2 enumerates strictly beyond it.

### 3.5 Crash matrix (compaction)

| Crash point | State found on restart | Recovery | Loses anything? |
| :--- | :--- | :--- | :--- |
| during steps 1–3 | `CURRENT`→G; orphan G+1 partials | GC orphans (P10); rerun from step 1 | no |
| after step 3, before commit | `CURRENT`→G; complete-but-unreferenced G+1 | same — unreferenced means uncommitted | no |
| **after commit, before step 5** | `CURRENT`→G+1; folded segments still present | consuming: fold them again — C7 makes re-fold a no-op — or detect via generation stamps and just delete; retained: frontier already recorded, they're simply ≤ watermark | no — duplicates converge |
| during step 5 (partial delete) | `CURRENT`→G+1; some folded segments remain | same as above | no |
| after step 5, before GC | old generation files linger | GC anytime | no |

The table is the point: **there is no crash window that requires repair-before-reuse.**
Every state is either "not committed, garbage-collect and redo" or "committed, finish
idempotent cleanup lazily." A restarted compactor runs the same six steps unconditionally —
recovery is not a special mode (C11).

## 4. Single-writer enforcement

Two mechanisms, layered — liveness by lock, safety by CAS:

1. **Advisory lock (liveness).** Before folding, acquire `{index}/compactor.lock` via
   create-if-absent, with the same record shape and TTL/expiry/CAS-reclaim semantics as a
   queue lease (§2.2–2.3 apply verbatim — the lock *is* a lease on the compactor role).
   Its job is to stop two compactors wasting work, not to guarantee safety.
2. **CAS commit (safety).** Even if the lock fails (skew, bugs, split brain), step 4's
   conditional swing of `CURRENT` ensures at most one of two racing compactors commits;
   the loser abandons per C10. Correctness never rests on the lock (C12).
3. **Only the committer deletes.** A compactor that did not succeed at step 4 MUST NOT
   delete any source segment. Source deletion authority derives from a successful commit,
   never from lock ownership (C13).

## 5. The minimal compactor contract

The compactor is deliberately the most constrained process in the system — a candidate for
a sealed, separately-packaged binary. Its complete authority:

| May | Must not |
| :--- | :--- |
| read `CURRENT` and committed generation files of **its one index** | read any other station |
| read schema-conforming segments of its **declared source station(s)** | fold or delete non-conforming files (C6) |
| write new generation files and swing `CURRENT` (steps 3–4) | write anywhere else, ever |
| delete exactly the folded segment set, after commit (C9, C13) | delete anything before commit |

- The fold is a pure function of (committed generation, enumerated segment set) — no
  clock, no network, no environment beyond its two stations (C14). Anything runtime-shaped
  (scheduling, credentials, S3 transport) belongs to the host invoking it, not the fold.
- The index SHOULD be write-protected against every principal except the compactor's
  (e.g. POSIX ownership/permissions locally; bucket policy on S3). This enforces the
  single-writer rule mechanically rather than by convention.
- This section is the requirements reduction that motivated the spec: a compactor
  satisfying it can be reimplemented, sandboxed (e.g. WASI preopens = exactly the two
  station roots), or formally checked without touching the rest of the system — and two
  independent implementations cannot diverge in observable behavior, because every
  observable behavior is pinned above.

## 6. Invariants (summary)

| # | Invariant |
| :--- | :--- |
| C1 | Every coordination step is a single backend primitive; nothing depends on two storage ops being atomic together |
| C2 | The only claim is a successful create-if-absent of the lease; listing is never claiming |
| C3 | Expired leases are taken over by CAS-replace, never delete-then-create |
| C4 | A worker past its lease expiry must not write terminal state |
| C5 | Delivery is at-least-once; item effects must be idempotent |
| C6 | Non-conforming input files are skipped and reported — never folded, never deleted |
| C7 | The fold is deterministic and idempotent (LWW by version stamp, deterministic ties) |
| C8 | Swinging `CURRENT` is the sole commit point; before it nothing observable changed, after it only idempotent cleanup remains |
| C9 | Source deletion happens only post-commit and only for the enumerated fold set |
| C10 | A failed commit CAS means abandon own work, delete nothing else, retry |
| C11 | Recovery is not a special mode: the normal protocol run from any crash state converges |
| C12 | The advisory lock provides liveness only; safety rests on the commit CAS |
| C13 | Deletion authority derives from a successful commit, never from lock ownership |
| C14 | The fold is a pure function of its two stations — no clock, network, or ambient environment |

## What this spec deliberately does not fix

- **Scheduling** — when/how often compaction runs (cron, threshold, manual) is a host
  concern; the protocol is correct at any cadence, including concurrent accidental runs.
- **The done_check execution model** for portable tasks — pending its own spec; §2's lease
  semantics apply to task queues unchanged.
- **Multi-index transactions.** There are none: each index commits independently via its
  own `CURRENT`. A workflow needing cross-index consistency must express it as another
  fold, not expect atomicity across commit points.
