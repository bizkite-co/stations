---
status: proposed
date: 2026-07-17
---

# 0005: Packaging layout and reference-implementation home

## Context

The design-spec task requires a packaging decision: where the Python reference
implementation lives, how consumers depend on it, and how that relates to the
language-agnostic on-disk contract. Earlier drafts considered a uv-workspace
member *inside* cocli; the `stations` repo now owns the pattern language, so
the implementation must not re-house the pattern under cocli.

## Decision

1. **This repo (`stations`) owns both the pattern and the reference implementation.**
   The on-disk contract lives in `spec/`; the Python package lives under
   `python/` (layout below). cocli, task-agent, and future apps are *external*
   dependents — never the other way around.
2. **Package name:** `stations` on PyPI (when published). Import path
   `stations.*`. Until first publish, consumers depend via path/git URL
   (`stations @ git+…` or a monorepo-external path).
3. **Layout:**

   ```
   stations/                          # this repo
   ├── GLOSSARY.md METHOD.md README.md
   ├── decisions/                     # WAL of concept decisions
   ├── spec/                          # language-agnostic contract
   │   ├── PHYSICAL-CONTRACT.md
   │   ├── CONCURRENCY.md
   │   └── PROTOCOLS.md               # Python Protocol projection
   ├── consumers/                     # onramps (cocli, task-agent, …)
   └── python/                        # reference implementation
       ├── pyproject.toml             # package name: stations
       ├── README.md
       └── src/stations/
           ├── __init__.py
           ├── protocols.py           # typing.Protocol surfaces (land first)
           ├── backends/              # PathBackend: local, s3
           ├── queue.py               # QueueEdge engines
           ├── log.py                 # LogEdge engines
           ├── index.py               # IndexEdge + Compactor
           ├── transform.py           # @transform decorator + TransformEngine
           └── inspect.py             # inspector CLI surface (later)
   ```

4. **Land order (strangler-friendly):**
   1. `protocols.py` only — pure type surface, zero runtime deps beyond
      typing/pydantic. cocli may type-hint against it immediately.
   2. `backends/` local + S3 claim primitives (the actual IP).
   3. Queue / log / index engines.
   4. `@transform` decorator + engine; inspector CLI last
      (task-agent `build-station-inspector-cli-…` is the prototype).
5. **No second language in v1.** The on-disk contract is the portable artifact;
   Python is the sole reference implementation. Other languages implement the
   contract, not a Python FFI.

## Consequences

- cocli does **not** gain a `stations` workspace member. Extraction is pull-based:
  cocli depends on `stations` and adapts existing `cocli.core.queue` /
  compactors to the Protocols (decision 0006).
- `spec/PROTOCOLS.md` is the design source; `python/src/stations/protocols.py`
  is the checked-in type surface once the package is scaffolded.
- Packaging layout is fixed; open only for first-publish mechanics (versioning
  scheme, CI, PyPI ownership).

## See also

- [spec/PROTOCOLS.md](../spec/PROTOCOLS.md)
- [0006-strangler-migration-from-cocli.md](./0006-strangler-migration-from-cocli.md)
- consumers: [cocli.md](../consumers/cocli.md), [task-agent.md](../consumers/task-agent.md)
