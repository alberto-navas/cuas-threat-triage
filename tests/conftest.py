"""Fixtures compartidas por toda la suite de tests."""

import pytest

from src.model import Position, TrackState, Velocity


@pytest.fixture
def position_factory():
    """Fabrica de Position con valores por defecto, para tests a los que
    solo les importa un campo concreto y no quieren repetir los otros dos
    en cada llamada."""

    def _make(east_m: float = 0.0, north_m: float = 0.0, up_m: float = 0.0) -> Position:
        return Position(east_m=east_m, north_m=north_m, up_m=up_m)

    return _make


@pytest.fixture
def velocity_factory():
    def _make(east_mps: float = 0.0, north_mps: float = 0.0, up_mps: float = 0.0) -> Velocity:
        return Velocity(east_mps=east_mps, north_mps=north_mps, up_mps=up_mps)

    return _make


@pytest.fixture
def track_state_factory(position_factory, velocity_factory):
    def _make(
        timestamp_s: float = 0.0, position: Position | None = None, velocity: Velocity | None = None
    ) -> TrackState:
        return TrackState(
            timestamp_s=timestamp_s,
            position=position if position is not None else position_factory(),
            velocity=velocity if velocity is not None else velocity_factory(),
        )

    return _make
