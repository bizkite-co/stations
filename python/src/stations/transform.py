"""@transform decorator and builder-validated graph assembly (Burr lesson).

Registers plain functions as :class:`~stations.protocols.Transform` against
typed stations. Does **not** fork Transform semantics — the wrapped callable
remains a pure ``(src: T_in, /) -> T_out``. Validation runs at
:meth:`ApplicationBuilder.build` time (assembly), not at decoration time.

See decisions/0008-burr-telemetry-and-transform-ergonomics.md.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    get_type_hints,
)

from stations.station import StationDecl, StationLike

T_in = TypeVar("T_in")
T_out = TypeVar("T_out")

# Module-level registry of decorated transforms (name -> spec)
_REGISTRY: Dict[str, "TransformSpec[Any, Any]"] = {}


@dataclass(frozen=True)
class TransformSpec(Generic[T_in, T_out]):
    """Registered transform metadata. The function itself is still a Transform."""

    name: str
    func: Callable[[T_in], T_out]
    from_station: StationDecl[T_in]
    to_station: StationDecl[T_out]


class TransformRegistrationError(ValueError):
    """Raised when a @transform registration is invalid."""


class GraphValidationError(ValueError):
    """Raised when ApplicationBuilder.build() fails validation."""


def transform(
    *,
    from_station: StationLike,
    to_station: StationLike,
    name: Optional[str] = None,
) -> Callable[[Callable[[T_in], T_out]], Callable[[T_in], T_out]]:
    """Decorator: register a pure model-to-model function against two stations.

    The decorated function is returned unchanged (still a structural Transform).
    Metadata is stored for :class:`ApplicationBuilder` assembly-time checks.

    Example::

        @transform(from_station=pending, to_station=completed)
        def promote(item: PendingItem) -> CompletedItem:
            return CompletedItem(...)
    """

    def decorator(fn: Callable[[T_in], T_out]) -> Callable[[T_in], T_out]:
        if not callable(fn):
            raise TransformRegistrationError("@transform target must be callable")
        reg_name = name or getattr(fn, "__name__", None) or repr(fn)
        if reg_name in _REGISTRY:
            raise TransformRegistrationError(
                f"transform {reg_name!r} already registered"
            )
        # Light checks at decorate time (existence of stations as objects)
        if from_station is None or to_station is None:
            raise TransformRegistrationError("from_station and to_station are required")
        if not getattr(from_station, "name", None) or not getattr(
            to_station, "name", None
        ):
            raise TransformRegistrationError(
                "stations must have a non-empty name (StationDecl)"
            )
        spec = TransformSpec(
            name=reg_name,
            func=fn,
            from_station=from_station,
            to_station=to_station,
        )
        _REGISTRY[reg_name] = spec
        # Annotate function for discovery without re-wrapping
        setattr(fn, "__stations_transform__", spec)
        return fn

    return decorator


def get_transform(name: str) -> Optional[TransformSpec[Any, Any]]:
    return _REGISTRY.get(name)


def registered_transforms() -> Dict[str, TransformSpec[Any, Any]]:
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Test helper: wipe the module registry."""
    _REGISTRY.clear()


def _annotation_origin(hint: Any) -> Any:
    return getattr(hint, "__origin__", None) or hint


def _types_compatible(declared: Type[Any], annotated: Any) -> bool:
    """Loose structural match: exact type, subclass, or Any/empty annotation."""
    if annotated is inspect.Parameter.empty or annotated is None:
        return True
    if annotated is Any:
        return True
    try:
        if declared is annotated:
            return True
        if isinstance(annotated, type) and isinstance(declared, type):
            return issubclass(declared, annotated) or issubclass(annotated, declared)
    except TypeError:
        pass
    # string annotations / forward refs — accept if names match
    return str(declared) == str(annotated) or getattr(declared, "__name__", None) == str(
        annotated
    )


@dataclass
class Application:
    """Validated transform graph (assembly product; no runtime engine)."""

    stations: Dict[str, StationDecl[Any]]
    transforms: List[TransformSpec[Any, Any]]


class ApplicationBuilder:
    """Builder-validated graph assembly (Burr ApplicationBuilder lesson).

    Stations and transforms are declared; :meth:`build` checks that every
    transform's stations are registered and that type annotations line up
    with station models when annotations are present.
    """

    def __init__(self) -> None:
        self._stations: Dict[str, StationDecl[Any]] = {}
        self._transforms: List[TransformSpec[Any, Any]] = []

    def with_station(self, station: StationDecl[Any]) -> "ApplicationBuilder":
        if station.name in self._stations:
            raise GraphValidationError(f"duplicate station name {station.name!r}")
        self._stations[station.name] = station
        return self

    def with_transform(
        self, fn_or_name: Callable[..., Any] | str
    ) -> "ApplicationBuilder":
        if isinstance(fn_or_name, str):
            spec = _REGISTRY.get(fn_or_name)
            if spec is None:
                raise GraphValidationError(f"unknown transform {fn_or_name!r}")
        else:
            attached = getattr(fn_or_name, "__stations_transform__", None)
            if attached is not None:
                spec = attached
            else:
                # look up by function identity
                spec = next(
                    (s for s in _REGISTRY.values() if s.func is fn_or_name), None
                )
            if spec is None:
                raise GraphValidationError(
                    f"{getattr(fn_or_name, '__name__', fn_or_name)!r} is not a "
                    f"@transform-registered function"
                )
        self._transforms.append(spec)
        return self

    def build(self) -> Application:
        errors: List[str] = []
        for spec in self._transforms:
            fs, ts = spec.from_station, spec.to_station
            if fs.name not in self._stations:
                errors.append(
                    f"transform {spec.name!r}: from_station {fs.name!r} not in builder"
                )
            elif self._stations[fs.name] is not fs and self._stations[fs.name] != fs:
                # same name but different object — still OK if equal by value
                if self._stations[fs.name] != fs:
                    errors.append(
                        f"transform {spec.name!r}: from_station {fs.name!r} "
                        f"differs from builder registration"
                    )
            if ts.name not in self._stations:
                errors.append(
                    f"transform {spec.name!r}: to_station {ts.name!r} not in builder"
                )

            # Type lineup against annotations when available
            try:
                hints = get_type_hints(spec.func)
            except Exception:
                hints = {}
            sig = inspect.signature(spec.func)
            params = [
                p
                for p in sig.parameters.values()
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            if len(params) != 1:
                errors.append(
                    f"transform {spec.name!r}: must take exactly one positional "
                    f"parameter (got {len(params)})"
                )
            elif params:
                ann = hints.get(params[0].name, params[0].annotation)
                if not _types_compatible(fs.model, ann):
                    errors.append(
                        f"transform {spec.name!r}: param type {ann!r} does not "
                        f"match from_station model {fs.model!r}"
                    )
            ret = hints.get("return", sig.return_annotation)
            if ret is not inspect.Signature.empty and not _types_compatible(
                ts.model, ret
            ):
                errors.append(
                    f"transform {spec.name!r}: return type {ret!r} does not "
                    f"match to_station model {ts.model!r}"
                )

        if errors:
            raise GraphValidationError(
                "ApplicationBuilder validation failed:\n  - " + "\n  - ".join(errors)
            )
        return Application(
            stations=dict(self._stations), transforms=list(self._transforms)
        )
