"""
Tests de la puntuacion cinematica TCPA/DCPA (src/scoring/kinematics.py).
"""

import pytest

from src.model import ProtectedAsset, Track, TrackStatus
from src.scoring.kinematics import compute_cpa, score_kinematics

_ASSET_RINGS = {"critico": 300.0, "vigilancia": 3000.0}


def _asset(position_factory) -> ProtectedAsset:
    return ProtectedAsset(asset_id="a1", position=position_factory(), criticality=3, ring_radii_m=_ASSET_RINGS)


def _track(track_state) -> Track:
    return Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=[track_state])


def test_compute_cpa_head_on_approach_reaches_target_exactly(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=1000.0), velocity=velocity_factory(east_mps=-10.0))
    asset = _asset(position_factory)

    tcpa_s, dcpa_m = compute_cpa(state, asset)

    assert tcpa_s == pytest.approx(100.0)
    assert dcpa_m == pytest.approx(0.0, abs=1e-9)


def test_compute_cpa_receding_track_has_negative_tcpa(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=1000.0), velocity=velocity_factory(east_mps=10.0))
    asset = _asset(position_factory)

    tcpa_s, _dcpa_m = compute_cpa(state, asset)

    assert tcpa_s == pytest.approx(-100.0)


def test_compute_cpa_stationary_track_has_no_tcpa(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=500.0), velocity=velocity_factory())
    asset = _asset(position_factory)

    tcpa_s, dcpa_m = compute_cpa(state, asset)

    assert tcpa_s is None
    assert dcpa_m == pytest.approx(500.0)


def test_score_kinematics_urgent_close_approach_scores_100(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=200.0), velocity=velocity_factory(east_mps=-20.0))
    asset = _asset(position_factory)

    result = score_kinematics(_track(state), asset)

    assert result.value == pytest.approx(100.0)


def test_score_kinematics_receding_scores_zero(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=200.0), velocity=velocity_factory(east_mps=20.0))
    asset = _asset(position_factory)

    result = score_kinematics(_track(state), asset)

    assert result.value == pytest.approx(0.0)
    assert "Alejandose" in result.rationale


def test_score_kinematics_stationary_scores_zero(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(position=position_factory(east_m=500.0), velocity=velocity_factory())
    asset = _asset(position_factory)

    result = score_kinematics(_track(state), asset)

    assert result.value == pytest.approx(0.0)
    assert "movimiento relativo" in result.rationale


def test_score_kinematics_distant_tcpa_scores_zero_despite_small_dcpa(
    position_factory, velocity_factory, track_state_factory
):
    # Se acerca directo (dcpa ~ 0) pero muy despacio: tardara mucho en llegar.
    state = track_state_factory(position=position_factory(east_m=10_000.0), velocity=velocity_factory(east_mps=-1.0))
    asset = _asset(position_factory)

    result = score_kinematics(_track(state), asset)

    assert result.value == pytest.approx(0.0)


def test_score_kinematics_huge_dcpa_scores_zero_despite_urgent_tcpa(
    position_factory, velocity_factory, track_state_factory
):
    # Va a pasar pronto (tcpa urgente) pero muy lejos (dcpa muy por encima del anillo exterior).
    state = track_state_factory(
        position=position_factory(east_m=5000.0, north_m=-100.0), velocity=velocity_factory(north_mps=10.0)
    )
    asset = _asset(position_factory)

    result = score_kinematics(_track(state), asset)

    assert result.value == pytest.approx(0.0)


def test_score_kinematics_interpolates_between_urgent_and_not_urgent(
    position_factory, velocity_factory, track_state_factory
):
    # tcpa=100s (entre 30 y 300) y dcpa=1000m (entre los anillos 300 y 3000):
    # ambos ejes a mitad de camino, en la misma proporcion por construccion.
    state = track_state_factory(
        position=position_factory(east_m=1000.0, north_m=-1000.0), velocity=velocity_factory(north_mps=10.0)
    )
    asset = _asset(position_factory)

    tcpa_s, dcpa_m = compute_cpa(state, asset)
    assert tcpa_s == pytest.approx(100.0)
    assert dcpa_m == pytest.approx(1000.0)

    result = score_kinematics(_track(state), asset)

    expected = 100.0 * (300.0 - 100.0) / (300.0 - 30.0)
    assert result.value == pytest.approx(expected)
    assert 0.0 < result.value < 100.0
