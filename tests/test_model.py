"""
Tests del modelo de datos comun (src/model.py).

Se centran en el comportamiento no trivial: el calculo de rumbo/velocidad
a partir de componentes ENU, y la validacion en los limites del pipeline
(confidence, criticality, scores) que evita que un bug en una etapa
posterior produzca un objeto con un valor sin sentido (p.ej. un score de
150/100) en vez de fallar de inmediato en el punto donde se construye.
"""

import pytest

from src.model import (
    Classification,
    DroneClass,
    ProtectedAsset,
    ScoreComponent,
    ThreatScore,
    ThreatTier,
    Track,
    TrackStatus,
    Velocity,
)


def test_velocity_speed_is_euclidean_norm():
    v = Velocity(east_mps=3.0, north_mps=4.0, up_mps=0.0)
    assert v.speed_mps == pytest.approx(5.0)


@pytest.mark.parametrize(
    "east_mps,north_mps,expected_heading_deg",
    [
        (0.0, 1.0, 0.0),  # norte
        (1.0, 0.0, 90.0),  # este
        (0.0, -1.0, 180.0),  # sur
        (-1.0, 0.0, 270.0),  # oeste
    ],
)
def test_velocity_heading_matches_compass_bearing(east_mps, north_mps, expected_heading_deg):
    v = Velocity(east_mps=east_mps, north_mps=north_mps, up_mps=0.0)
    assert v.heading_deg == pytest.approx(expected_heading_deg)


def test_velocity_heading_is_zero_by_convention_without_horizontal_component():
    v = Velocity(east_mps=0.0, north_mps=0.0, up_mps=5.0)
    assert v.heading_deg == 0.0


def test_track_current_state_raises_without_history():
    track = Track(track_id="T-001", status=TrackStatus.TENTATIVE)
    with pytest.raises(ValueError):
        _ = track.current_state


def test_track_current_state_returns_most_recent_entry(track_state_factory):
    older = track_state_factory(timestamp_s=0.0)
    newer = track_state_factory(timestamp_s=1.0)
    track = Track(track_id="T-001", status=TrackStatus.CONFIRMED, history=[older, newer])

    assert track.current_state is newer


def test_classification_rejects_confidence_out_of_range():
    with pytest.raises(ValueError):
        Classification(track_id="T-001", drone_class=DroneClass.UNKNOWN, confidence=1.5, rationale="")


def test_classification_accepts_boundary_confidence_values():
    Classification(track_id="T-001", drone_class=DroneClass.UNKNOWN, confidence=0.0, rationale="")
    Classification(track_id="T-001", drone_class=DroneClass.UNKNOWN, confidence=1.0, rationale="")


def test_protected_asset_rejects_criticality_out_of_range(position_factory):
    with pytest.raises(ValueError):
        ProtectedAsset(asset_id="A-1", position=position_factory(), criticality=6, ring_radii_m={})


def test_score_component_rejects_value_out_of_range():
    with pytest.raises(ValueError):
        ScoreComponent(name="cinematica", value=101.0, rationale="")


def test_threat_score_rejects_total_out_of_range():
    with pytest.raises(ValueError):
        ThreatScore(
            track_id="T-001",
            asset_id="A-1",
            components=(),
            total=-1.0,
            tier=ThreatTier.LOW,
        )
