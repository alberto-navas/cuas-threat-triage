"""
Tests de la puntuacion por zona (src/scoring/zone.py).
"""

import pytest

from src.model import ProtectedAsset, Track, TrackStatus
from src.scoring.zone import max_ring_radius_m, min_ring_radius_m, score_zone

_RINGS = {"vigilancia": 3000.0, "aviso": 1000.0, "critico": 300.0}


def _asset(position_factory, ring_radii_m: dict[str, float] = _RINGS) -> ProtectedAsset:
    return ProtectedAsset(asset_id="a1", position=position_factory(), criticality=3, ring_radii_m=ring_radii_m)


def _track_at(position_factory, track_state_factory, east_m: float) -> Track:
    state = track_state_factory(position=position_factory(east_m=east_m))
    return Track(track_id="TRK-1", status=TrackStatus.CONFIRMED, history=[state])


def test_score_zone_inside_innermost_ring_is_100(position_factory, track_state_factory):
    asset = _asset(position_factory)
    track = _track_at(position_factory, track_state_factory, east_m=100.0)

    result = score_zone(track, asset)

    assert result.value == pytest.approx(100.0)
    assert "critico" in result.rationale


def test_score_zone_outside_all_rings_is_zero(position_factory, track_state_factory):
    asset = _asset(position_factory)
    track = _track_at(position_factory, track_state_factory, east_m=5000.0)

    result = score_zone(track, asset)

    assert result.value == pytest.approx(0.0)
    assert "fuera de todos los anillos" in result.rationale


def test_score_zone_middle_band_is_between_extremes(position_factory, track_state_factory):
    asset = _asset(position_factory)
    track = _track_at(position_factory, track_state_factory, east_m=2000.0)  # entre aviso y vigilancia

    result = score_zone(track, asset)

    assert result.value == pytest.approx(100.0 / 3.0)
    assert "vigilancia" in result.rationale


def test_score_zone_exactly_on_ring_boundary_counts_as_inside(position_factory, track_state_factory):
    asset = _asset(position_factory)
    track = _track_at(position_factory, track_state_factory, east_m=300.0)

    result = score_zone(track, asset)

    assert result.value == pytest.approx(100.0)


def test_score_zone_raises_for_asset_without_rings(position_factory, track_state_factory):
    asset = _asset(position_factory, ring_radii_m={})
    track = _track_at(position_factory, track_state_factory, east_m=100.0)

    with pytest.raises(ValueError, match="anillo de proximidad"):
        score_zone(track, asset)


def test_min_and_max_ring_radius(position_factory):
    asset = _asset(position_factory)

    assert min_ring_radius_m(asset) == pytest.approx(300.0)
    assert max_ring_radius_m(asset) == pytest.approx(3000.0)
