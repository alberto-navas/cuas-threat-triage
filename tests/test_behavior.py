"""
Tests de la puntuacion por comportamiento / alineacion de rumbo
(src/scoring/behavior.py).
"""

import pytest

from src.model import ProtectedAsset, Track, TrackStatus
from src.scoring.behavior import score_behavior


def _asset(position_factory) -> ProtectedAsset:
    return ProtectedAsset(asset_id="a1", position=position_factory(), criticality=3, ring_radii_m={"critico": 300.0})


def test_direct_approach_scores_near_100(position_factory, velocity_factory, track_state_factory):
    # Activo en el origen; la traza esta al este y se mueve directo hacia el oeste (heading=270).
    history = [
        track_state_factory(position=position_factory(east_m=e), velocity=velocity_factory(east_mps=-10.0))
        for e in (500.0, 400.0, 300.0)
    ]
    track = Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=history)

    result = score_behavior(track, _asset(position_factory))

    assert result.value == pytest.approx(100.0, abs=1e-6)


def test_receding_scores_near_zero(position_factory, velocity_factory, track_state_factory):
    # Misma geometria, pero alejandose hacia el este (heading=90): apunta en direccion opuesta al activo.
    history = [
        track_state_factory(position=position_factory(east_m=e), velocity=velocity_factory(east_mps=10.0))
        for e in (300.0, 400.0, 500.0)
    ]
    track = Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=history)

    result = score_behavior(track, _asset(position_factory))

    assert result.value == pytest.approx(0.0, abs=1e-6)


def test_tangential_movement_scores_near_50(position_factory, velocity_factory, track_state_factory):
    # La traza esta al este del activo (rumbo al activo = 270) pero se mueve
    # hacia el norte (heading=0): exactamente perpendicular. La posicion se
    # mantiene fija en la ventana para aislar la alineacion instantanea, sin
    # que el propio desplazamiento haga rotar el rumbo hacia el activo.
    history = [
        track_state_factory(position=position_factory(east_m=500.0), velocity=velocity_factory(north_mps=10.0))
        for _ in range(3)
    ]
    track = Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=history)

    result = score_behavior(track, _asset(position_factory))

    assert result.value == pytest.approx(50.0, abs=1e-6)


def test_no_recent_significant_speed_scores_zero(position_factory, velocity_factory, track_state_factory):
    history = [
        track_state_factory(position=position_factory(east_m=500.0), velocity=velocity_factory(east_mps=0.01))
        for _ in range(3)
    ]
    track = Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=history)

    result = score_behavior(track, _asset(position_factory))

    assert result.value == pytest.approx(0.0)
    assert "sin rumbo" in result.rationale.lower() or "velocidad" in result.rationale.lower()


def test_only_recent_window_is_considered(position_factory, velocity_factory, track_state_factory):
    """Un comportamiento antiguo (alejandose) no debe pesar si las
    posiciones recientes muestran una aproximacion directa."""
    old_receding = [
        track_state_factory(position=position_factory(east_m=e), velocity=velocity_factory(east_mps=10.0))
        for e in (100.0, 200.0, 300.0)
    ]
    recent_approaching = [
        track_state_factory(position=position_factory(east_m=e), velocity=velocity_factory(east_mps=-10.0))
        for e in (900.0, 800.0, 700.0, 600.0, 500.0, 400.0, 300.0, 200.0, 100.0, 50.0)
    ]
    track = Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=old_receding + recent_approaching)

    result = score_behavior(track, _asset(position_factory))

    assert result.value == pytest.approx(100.0, abs=1e-6)
