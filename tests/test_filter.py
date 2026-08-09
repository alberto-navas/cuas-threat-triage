"""
Tests del filtro alpha-beta (src/tracking/filter.py).
"""

import pytest

from src.tracking.filter import predict, update


def test_predict_moves_position_by_velocity_times_dt(position_factory, velocity_factory, track_state_factory):
    state = track_state_factory(
        timestamp_s=0.0, position=position_factory(east_m=0.0), velocity=velocity_factory(east_mps=10.0)
    )

    predicted = predict(state, dt=2.0)

    assert predicted.position.east_m == pytest.approx(20.0)
    assert predicted.timestamp_s == pytest.approx(2.0)


def test_predict_preserves_velocity(track_state_factory, velocity_factory):
    state = track_state_factory(velocity=velocity_factory(east_mps=5.0, north_mps=-3.0))

    predicted = predict(state, dt=1.0)

    assert predicted.velocity.east_mps == pytest.approx(5.0)
    assert predicted.velocity.north_mps == pytest.approx(-3.0)


def test_predict_rejects_non_positive_dt(track_state_factory):
    state = track_state_factory()
    with pytest.raises(ValueError):
        predict(state, dt=0.0)


def test_update_moves_position_partway_toward_measurement(track_state_factory, position_factory):
    predicted = track_state_factory(position=position_factory(east_m=0.0))
    measured = position_factory(east_m=10.0)

    corrected = update(predicted, measured, alpha=0.5, beta=0.2, dt=1.0)

    assert corrected.position.east_m == pytest.approx(5.0)


def test_update_full_alpha_snaps_to_measurement(track_state_factory, position_factory):
    predicted = track_state_factory(position=position_factory(east_m=0.0))
    measured = position_factory(east_m=10.0)

    corrected = update(predicted, measured, alpha=1.0, beta=0.0, dt=1.0)

    assert corrected.position.east_m == pytest.approx(10.0)


def test_update_adjusts_velocity_from_residual(track_state_factory, position_factory, velocity_factory):
    predicted = track_state_factory(position=position_factory(east_m=0.0), velocity=velocity_factory(east_mps=0.0))
    measured = position_factory(east_m=10.0)

    corrected = update(predicted, measured, alpha=0.0, beta=0.5, dt=2.0)

    # beta=0.5, residuo=10, dt=2 -> ajuste de velocidad = (0.5 / 2) * 10 = 2.5 m/s
    assert corrected.velocity.east_mps == pytest.approx(2.5)


def test_update_zero_residual_leaves_state_unchanged(track_state_factory, position_factory):
    predicted = track_state_factory(position=position_factory(east_m=7.0))

    corrected = update(predicted, position_factory(east_m=7.0), alpha=0.6, beta=0.2, dt=1.0)

    assert corrected.position.east_m == pytest.approx(7.0)
    assert corrected.velocity.east_mps == pytest.approx(0.0)


def test_update_rejects_non_positive_dt(track_state_factory, position_factory):
    predicted = track_state_factory()
    with pytest.raises(ValueError):
        update(predicted, position_factory(), alpha=0.5, beta=0.2, dt=0.0)
