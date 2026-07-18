# stations (Python reference package)

Language-facing surface for the [stations](../) pattern language.

## Status

**Phase 1 — Protocols only.** `stations.protocols` is a pure `typing.Protocol`
surface transcribed from [`../spec/PROTOCOLS.md`](../spec/PROTOCOLS.md). No
runtime engines yet (backends, queue, transform come later per decision 0005).

## Install (consumers)

Until PyPI publish, depend by path or git:

```toml
# pyproject.toml
dependencies = [
  "stations @ file:///absolute/path/to/stations/python",
]
```

or:

```bash
uv add --editable /path/to/stations/python
```

## Layout

```
python/
├── pyproject.toml
├── README.md
└── src/stations/
    ├── __init__.py
    └── protocols.py    # only module in v0.1
```
