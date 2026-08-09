"""
Tests de la agregacion y el ranking de prioridad
(src/decision/prioritizer.py).
"""

import pytest

from src.decision.prioritizer import (
    _WEIGHTS_BY_COMPONENT,
    _tier_from_total,
    prioritize,
    score_track_against_asset,
)
from src.model import Classification, DroneClass, ProtectedAsset, ThreatTier, Track, TrackStatus

_RINGS = {"critico": 300.0, "vigilancia": 3000.0}


def _asset(position_factory, asset_id: str = "a1", criticality: int = 3, east_m: float = 0.0) -> ProtectedAsset:
    return ProtectedAsset(
        asset_id=asset_id, position=position_factory(east_m=east_m), criticality=criticality, ring_radii_m=_RINGS
    )


def _classification(confidence: float = 0.9, drone_class: DroneClass = DroneClass.FPV_ATTACK) -> Classification:
    return Classification(track_id="TRK-1", drone_class=drone_class, confidence=confidence, rationale="")


def _approaching_track(position_factory, velocity_factory, track_state_factory, track_id: str = "TRK-A") -> Track:
    """Recta, rapida, sostenida hacia el origen: suficiente historial para
    que la clasificacion cinematica la marque como FPV_ATTACK."""
    history = [
        track_state_factory(
            timestamp_s=float(i),
            position=position_factory(east_m=1000.0 - i * 30.0),
            velocity=velocity_factory(east_mps=-30.0),
        )
        for i in range(10)
    ]
    return Track(track_id=track_id, status=TrackStatus.CONFIRMED, history=history)


def _far_wandering_track(position_factory, velocity_factory, track_state_factory, track_id: str = "TRK-B") -> Track:
    """Lejos del activo, casi sin velocidad: debe quedar como BIRD_CLUTTER
    y con todos los componentes de scoring bajos."""
    history = [
        track_state_factory(
            timestamp_s=float(i),
            position=position_factory(east_m=20_000.0, north_m=20_000.0),
            velocity=velocity_factory(east_mps=0.3),
        )
        for i in range(10)
    ]
    return Track(track_id=track_id, status=TrackStatus.CONFIRMED, history=history)


# --- score_track_against_asset -------------------------------------------


def test_total_matches_documented_weighted_sum(position_factory, velocity_factory, track_state_factory):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)
    asset = _asset(position_factory)

    result = score_track_against_asset(track, _classification(), asset)

    expected = sum(component.value * _WEIGHTS_BY_COMPONENT[component.name] for component in result.components)
    assert result.total == pytest.approx(expected)


def test_weights_sum_to_one():
    assert sum(_WEIGHTS_BY_COMPONENT.values()) == pytest.approx(1.0)


def test_score_has_all_five_named_components(position_factory, velocity_factory, track_state_factory):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)
    asset = _asset(position_factory)

    result = score_track_against_asset(track, _classification(), asset)

    assert {component.name for component in result.components} == {
        "cinematica",
        "zona",
        "clasificacion",
        "comportamiento",
        "criticidad_activo",
    }


def test_asset_criticality_component_scales_linearly(position_factory, velocity_factory, track_state_factory):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)

    low = score_track_against_asset(track, _classification(), _asset(position_factory, criticality=1))
    mid = score_track_against_asset(track, _classification(), _asset(position_factory, criticality=3))
    high = score_track_against_asset(track, _classification(), _asset(position_factory, criticality=5))

    def _criticality_value(score):
        return next(c.value for c in score.components if c.name == "criticidad_activo")

    assert _criticality_value(low) == pytest.approx(0.0)
    assert _criticality_value(mid) == pytest.approx(50.0)
    assert _criticality_value(high) == pytest.approx(100.0)


# --- _tier_from_total ------------------------------------------------------


@pytest.mark.parametrize(
    "total,expected_tier",
    [
        (100.0, ThreatTier.CRITICAL),
        (80.0, ThreatTier.CRITICAL),
        (79.9, ThreatTier.HIGH),
        (60.0, ThreatTier.HIGH),
        (59.9, ThreatTier.MEDIUM),
        (35.0, ThreatTier.MEDIUM),
        (34.9, ThreatTier.LOW),
        (0.0, ThreatTier.LOW),
    ],
)
def test_tier_thresholds(total, expected_tier):
    assert _tier_from_total(total) == expected_tier


# --- prioritize --------------------------------------------------------


def test_prioritize_raises_without_assets(position_factory, velocity_factory, track_state_factory):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)
    with pytest.raises(ValueError, match="activo"):
        prioritize([track], [])


def test_prioritize_excludes_dropped_tracks(position_factory, velocity_factory, track_state_factory):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)
    dropped = Track(track_id="TRK-DROPPED", status=TrackStatus.DROPPED, history=track.history)

    entries = prioritize([track, dropped], [_asset(position_factory)])

    assert {entry.score.track_id for entry in entries} == {"TRK-A"}


def test_prioritize_orders_hostile_track_above_benign_one(position_factory, velocity_factory, track_state_factory):
    hostile = _approaching_track(position_factory, velocity_factory, track_state_factory, track_id="TRK-A")
    benign = _far_wandering_track(position_factory, velocity_factory, track_state_factory, track_id="TRK-B")

    entries = prioritize([hostile, benign], [_asset(position_factory)])

    assert [entry.score.track_id for entry in entries] == ["TRK-A", "TRK-B"]
    assert entries[0].rank == 1
    assert entries[1].rank == 2
    assert entries[0].score.total > entries[1].score.total


def test_prioritize_selects_the_most_threatened_asset_per_track(
    position_factory, velocity_factory, track_state_factory
):
    track = _approaching_track(position_factory, velocity_factory, track_state_factory)
    far_asset = _asset(position_factory, asset_id="far", east_m=50_000.0)
    targeted_asset = _asset(position_factory, asset_id="targeted", east_m=0.0)

    entries = prioritize([track], [far_asset, targeted_asset])

    assert len(entries) == 1
    assert entries[0].score.asset_id == "targeted"


def test_prioritize_returns_empty_list_for_no_tracks(position_factory):
    assert prioritize([], [_asset(position_factory)]) == []
