"""@transform decorator and ApplicationBuilder validation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from stations import (
    ApplicationBuilder,
    GraphValidationError,
    StationDecl,
    TransformRegistrationError,
    get_transform,
    transform,
)
from stations.transform import clear_registry


@dataclass
class InItem:
    id: str


@dataclass
class OutItem:
    id: str
    ok: bool


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    clear_registry()
    yield
    clear_registry()


def test_decorator_registers_and_preserves_callable() -> None:
    src = StationDecl("in", "q/pending", model=InItem)
    dst = StationDecl("out", "q/completed", model=OutItem)

    @transform(from_station=src, to_station=dst)
    def promote(item: InItem) -> OutItem:
        return OutItem(id=item.id, ok=True)

    result = promote(InItem(id="a"))
    assert result == OutItem(id="a", ok=True)

    spec = get_transform("promote")
    assert spec is not None
    assert spec.from_station is src
    assert spec.to_station is dst
    assert spec.func is promote


def test_builder_validates_happy_path() -> None:
    src = StationDecl("in", "q/pending", model=InItem)
    dst = StationDecl("out", "q/completed", model=OutItem)

    @transform(from_station=src, to_station=dst)
    def promote(item: InItem) -> OutItem:
        return OutItem(id=item.id, ok=True)

    app = (
        ApplicationBuilder()
        .with_station(src)
        .with_station(dst)
        .with_transform(promote)
        .build()
    )
    assert "in" in app.stations
    assert len(app.transforms) == 1


def test_builder_rejects_missing_station() -> None:
    src = StationDecl("in", "q/pending", model=InItem)
    dst = StationDecl("out", "q/completed", model=OutItem)

    @transform(from_station=src, to_station=dst)
    def promote(item: InItem) -> OutItem:
        return OutItem(id=item.id, ok=True)

    with pytest.raises(GraphValidationError, match="not in builder"):
        ApplicationBuilder().with_station(src).with_transform(promote).build()


def test_builder_rejects_type_mismatch() -> None:
    src = StationDecl("in", "q/pending", model=InItem)
    dst = StationDecl("out", "q/completed", model=OutItem)

    @transform(from_station=src, to_station=dst)
    def promote(item: str) -> OutItem:  # wrong input type
        return OutItem(id=item, ok=True)

    with pytest.raises(GraphValidationError, match="param type"):
        (
            ApplicationBuilder()
            .with_station(src)
            .with_station(dst)
            .with_transform(promote)
            .build()
        )


def test_duplicate_registration_raises() -> None:
    src = StationDecl("in", "q/pending", model=InItem)
    dst = StationDecl("out", "q/completed", model=OutItem)

    @transform(from_station=src, to_station=dst, name="same")
    def a(item: InItem) -> OutItem:
        return OutItem(id=item.id, ok=True)

    with pytest.raises(TransformRegistrationError, match="already registered"):

        @transform(from_station=src, to_station=dst, name="same")
        def b(item: InItem) -> OutItem:
            return OutItem(id=item.id, ok=False)


def test_usv_station_requires_datapackage() -> None:
    with pytest.raises(ValueError, match="datapackage_path"):
        StationDecl("w", "wal/x", model=InItem, serialization="usv")
