# Stations

A pattern language for typed state machines where the states are portable file paths.

This is not a library (yet). It is the vocabulary and method that fell out of building
three independent systems the same way — a plain-text CRM/scraper platform (`cocli`), a
task tracker (`task-agent`), and a video pipeline — and noticing they'd all reinvented the
same substrate without naming it. This repo names it, so the next system starts from the
name instead of reinventing it a fourth time.

## The one-line idea

**Storage layout *is* the state machine.** A directory tree is bound to typed records; code
only moves things between directories. There is no broker, scheduler, or server —
concurrency is handled by storage semantics themselves (POSIX atomic rename locally, S3
conditional writes remotely), and any process (or a human with `ls`, or DuckDB with a glob)
can inspect mid-flight state without the framework being present.

This inverts the usual relationship. In mainstream workflow frameworks the state machine
lives in code and storage is a serialization detail. Here the storage layout is the state
machine, and code is just what moves things between states.

## Start here

- **[GLOSSARY.md](./GLOSSARY.md)** — the canonical definition of every term (station,
  transform, edge role, trichotomy, portable task, emission edge, single-writer rule, ...).
  Link here, don't redefine elsewhere.
- **[METHOD.md](./METHOD.md)** — the Station Map procedure: how to point this vocabulary at
  an arbitrary existing system and have it produce its own conformance gap list.
- **[spec/](./spec/)** — the on-disk contract and its Python projection:
  [PHYSICAL-CONTRACT.md](./spec/PHYSICAL-CONTRACT.md) (bytes on disk),
  [CONCURRENCY.md](./spec/CONCURRENCY.md) (leases, compaction, crash recovery),
  [PROTOCOLS.md](./spec/PROTOCOLS.md) (Python `typing.Protocol` surface for the
  reference implementation). The glossary names concepts; the spec pins them down.
- **[decisions/](./decisions/)** — an append-only log of concept decisions (this repo eats
  its own dog food: decisions are a WAL, this README is a fold of it). Key decisions:
  emission edges (0001), cross-repo identity (0002), packaging (0005), strangler from
  cocli (0006), disposition of overlapping WASI/protocol tasks (0007).
- **[consumers/](./consumers/)** — one thin onramp doc per system that adopts this
  vocabulary. Each onramp *links back* here rather than copying definitions — station
  membership is path-encoded and changes as records move, so identity beats path (see
  GLOSSARY.md § Cross-repo referencing).

## Status

Pre-library. Pattern language + on-disk contract + Protocol surface are drafted; two
systems (`cocli`, `task-agent`) dogfood the vocabulary. No runtime package extracted yet
— packaging layout is decided (`python/`, [0005](./decisions/0005-packaging-and-reference-implementation.md));
implementation follows the strangler plan ([0006](./decisions/0006-strangler-migration-from-cocli.md)).
Decisions 0005–0007 ratified by the maintainer 2026-07-18.

## Provenance

Distilled 2026-07 from design work on `cocli`'s CLI-consolidation epic and the
`design-spec-for-reusable-typed-file-path-queue-transformer-library-extracted-from-cocli`
task. See `cocli`'s `docs/DESCRIPTION.md` for the original, product-coupled telling of this
same story — this repo is that document with the product stripped out.
