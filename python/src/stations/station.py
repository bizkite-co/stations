"""Concrete Station declaration used by @transform and ApplicationBuilder.

Satisfies :class:`stations.protocols.Station` structurally. Consumers bind a
record model + path template; the declaration is a noun only — edge role is
declared on the edge, not here (GLOSSARY § Edge role).
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any, Generic, Optional, Type, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class StationDecl(Generic[T]):
    """Typed path binding: path template + model + schema version + codec."""

    name: str
    path_template: str
    model: Type[T]
    schema_version: str = "1"
    serialization: str = "json-file"  # "usv" | "json-file" | "md-frontmatter"
    datapackage_path: Optional[str] = None

    def resolve(self, **params: str) -> str:
        """Render path_template with parameters into a backend path/prefix."""
        required = {
            fname
            for _, fname, _, _ in Formatter().parse(self.path_template)
            if fname is not None
        }
        missing = required - set(params)
        if missing:
            raise ValueError(
                f"station {self.name!r}: missing path params {sorted(missing)}"
            )
        return self.path_template.format(**params)

    def __post_init__(self) -> None:
        if self.serialization == "usv" and not self.datapackage_path:
            raise ValueError(
                f"station {self.name!r}: serialization='usv' requires datapackage_path (P1)"
            )


# Alias used in decorator signatures / docs
StationLike = StationDecl[Any]
