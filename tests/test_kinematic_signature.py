"""
Tests de la clasificacion por firma cinematica
(src/classification/kinematic_signature.py).
"""

import math

import pytest

from src.classification.kinematic_signature import (
    _WARMUP_SAMPLES_TO_SKIP,
    classify,
    compute_kinematic_signature,
)
from src.model import DroneClass, Position, Track, TrackState, TrackStatus, Velocity

_ORIGIN = Position(east_m=0.0, north_m=0.0, up_m=0.0)


def _velocity(speed_mps: float, heading_deg: float) -> Velocity:
    heading_rad = math.radians(heading_deg)
    return Velocity(east_mps=speed_mps * math.sin(heading_rad), north_mps=speed_mps * math.cos(heading_rad), up_mps=0.0)


def _track(velocities: list[tuple[float, float]], dt: float = 1.0) -> Track:
    """`velocities` es una lista de (speed_mps, heading_deg). La posicion no
    interviene en la clasificacion, asi que todos los estados comparten el
    mismo origen arbitrario."""
    history = [
        TrackState(timestamp_s=i * dt, position=_ORIGIN, velocity=_velocity(speed, heading))
        for i, (speed, heading) in enumerate(velocities)
    ]
    return Track(track_id="TRK-TEST", status=TrackStatus.CONFIRMED, history=history)


# --- compute_kinematic_signature --------------------------------------------


def test_signature_of_empty_history_is_all_zero():
    track = Track(track_id="TRK-TEST", status=TrackStatus.TENTATIVE)
    signature = compute_kinematic_signature(track)

    assert signature.num_samples == 0
    assert signature.avg_speed_mps == 0.0
    assert signature.mean_turn_rate_dps == 0.0
    assert signature.turn_rate_std_dps == 0.0


def test_signature_of_straight_line_has_near_zero_turn_rate():
    track = _track([(30.0, 90.0)] * 5)
    signature = compute_kinematic_signature(track)

    assert signature.avg_speed_mps == pytest.approx(30.0)
    assert signature.mean_turn_rate_dps == pytest.approx(0.0)
    assert signature.turn_rate_std_dps == pytest.approx(0.0)


def test_signature_of_constant_turn_has_consistent_nonzero_turn_rate():
    headings = [0.0, 3.0, 6.0, 9.0, 12.0]
    track = _track([(12.0, h) for h in headings])
    signature = compute_kinematic_signature(track)

    assert signature.mean_turn_rate_dps == pytest.approx(3.0)
    assert signature.turn_rate_std_dps == pytest.approx(0.0, abs=1e-9)


def test_signature_of_erratic_heading_has_high_turn_rate_std():
    headings = [0.0, 170.0, 20.0, 190.0, 10.0]
    track = _track([(6.0, h) for h in headings])
    signature = compute_kinematic_signature(track)

    assert signature.turn_rate_std_dps > 5.0


def test_signature_skips_heading_pairs_below_min_speed():
    # La primera velocidad esta por debajo de _MIN_SPEED_FOR_HEADING_MPS: su
    # rumbo (0.0 por convencion) no debe contaminar el ritmo de giro.
    track = _track([(0.1, 0.0), (30.0, 90.0), (30.0, 90.0)])
    signature = compute_kinematic_signature(track)

    assert signature.mean_turn_rate_dps == pytest.approx(0.0)


def test_signature_is_zero_when_every_pair_has_a_slow_endpoint():
    # La segunda velocidad de cada par consecutivo esta por debajo de
    # _MIN_SPEED_FOR_HEADING_MPS: no queda ningun par valido del que sacar
    # un ritmo de giro, asi que debe devolver 0.0 en vez de fallar.
    track = _track([(30.0, 90.0), (0.1, 0.0)])
    signature = compute_kinematic_signature(track)

    assert signature.num_samples == 2
    assert signature.mean_turn_rate_dps == 0.0
    assert signature.turn_rate_std_dps == 0.0


def test_signature_discards_startup_transient_when_history_is_long_enough():
    # Un unico salto de rumbo al nacer la traza (transitorio de convergencia
    # del filtro), seguido de una linea recta consistente. Con historial
    # suficiente, ese arranque no debe contaminar la firma.
    velocities = [(30.0, 0.0)] + [(30.0, 90.0)] * 9
    track = _track(velocities)
    signature = compute_kinematic_signature(track)

    assert signature.num_samples == len(velocities) - _WARMUP_SAMPLES_TO_SKIP
    assert signature.mean_turn_rate_dps == pytest.approx(0.0)
    assert signature.turn_rate_std_dps == pytest.approx(0.0)


# --- classify -----------------------------------------------------------


def test_classify_insufficient_history_returns_unknown():
    track = _track([(30.0, 90.0), (30.0, 90.0)])
    result = classify(track)

    assert result.drone_class == DroneClass.UNKNOWN
    assert result.confidence == pytest.approx(0.2)
    assert "insuficiente" in result.rationale


def test_classify_slow_track_is_bird_clutter():
    track = _track([(1.0, 45.0), (1.5, 200.0), (0.8, 10.0), (1.2, 300.0)])
    result = classify(track)

    assert result.drone_class == DroneClass.BIRD_CLUTTER
    assert 0.5 <= result.confidence <= 0.95


def test_classify_erratic_moderate_speed_is_commercial():
    headings = [0.0, 170.0, 20.0, 190.0, 10.0, 250.0]
    track = _track([(6.0, h) for h in headings])
    result = classify(track)

    assert result.drone_class == DroneClass.COMMERCIAL
    assert 0.5 <= result.confidence <= 0.95


def test_classify_fast_straight_track_is_fpv_attack():
    track = _track([(35.0, 90.0)] * 6)
    result = classify(track)

    assert result.drone_class == DroneClass.FPV_ATTACK
    assert 0.5 <= result.confidence <= 0.95


def test_classify_slow_straight_track_is_unknown_not_attack():
    """Recto y consistente, pero demasiado lento para llamarlo con
    confianza una aproximacion hostil (ver _ATTACK_MIN_SPEED_MPS)."""
    track = _track([(8.0, 90.0)] * 6)
    result = classify(track)

    assert result.drone_class == DroneClass.UNKNOWN
    assert result.confidence == pytest.approx(0.3)


def test_classify_steady_turn_is_isr_fixed_wing():
    headings = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0]
    track = _track([(12.0, h) for h in headings])
    result = classify(track)

    assert result.drone_class == DroneClass.ISR_FIXED_WING
    assert 0.5 <= result.confidence <= 0.95


def test_classify_confidence_increases_with_margin():
    barely_straight = _track([(35.0, h) for h in [0.0, 0.4, 0.8, 1.2, 1.6]])
    clearly_straight = _track([(35.0, 90.0)] * 5)

    barely_result = classify(barely_straight)
    clearly_result = classify(clearly_straight)

    assert barely_result.drone_class == DroneClass.FPV_ATTACK
    assert clearly_result.drone_class == DroneClass.FPV_ATTACK
    assert clearly_result.confidence > barely_result.confidence
