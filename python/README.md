# stations (Python reference package)

Language-facing surface for the [stations](../) pattern language.

## Status

- **Protocols** — pure `typing.Protocol` surface (`stations.protocols`).
- **LocalPathBackend + S3PathBackend** — PathBackend with claim CAS primitives
  (`create_if_absent`, `replace_if_match`) and `stations.backends.claim` helpers
  (decision 0006 Phase 2).
- **`@transform` + ApplicationBuilder** — decorator ergonomics and assembly-time
  graph validation (decision 0008 / Burr lesson).
- **`stations inspect`** — read-only terminal inspector for conforming station roots.

Engines (`TransformEngine`, `Compactor`) arrive in strangler Phase 3 (decision 0006).

## Install (consumers)

Until PyPI publish, depend by path or git:

```toml
# pyproject.toml
dependencies = [
  "stations @ git+https://github.com/bizkite-co/stations.git#subdirectory=python",
]
```

or for local hacking:

```bash
uv add --editable /path/to/stations/python
```

## CLI

```bash
stations inspect /path/to/station-or-queues-root
stations inspect --plain --no-leases ./queues/gm-list
python -m stations inspect .
```

## Decorator

```python
from stations import StationDecl, transform, ApplicationBuilder

pending = StationDecl("pending", "queues/x/pending", model=InModel)
done = StationDecl("completed", "queues/x/completed", model=OutModel)

@transform(from_station=pending, to_station=done)
def promote(item: InModel) -> OutModel:
    return OutModel(...)

app = (
    ApplicationBuilder()
    .with_station(pending)
    .with_station(done)
    .with_transform(promote)
    .build()
)
```

## Layout

```
python/
├── pyproject.toml
├── README.md
└── src/stations/
    ├── __init__.py
    ├── protocols.py
    ├── station.py          # StationDecl
    ├── transform.py        # @transform + ApplicationBuilder
    ├── inspect.py          # read-only aggregation + render
    ├── cli.py              # stations inspect
    └── backends/
        └── local.py        # LocalPathBackend
```

## Normative docs (repo root)

- `../GLOSSARY.md`, `../spec/*`, `../decisions/0005`, `../decisions/0008`
