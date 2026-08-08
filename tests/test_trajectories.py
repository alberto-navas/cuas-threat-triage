"""
Tests de los generadores de trayectoria "verdad fundamental"
(src/simulation/trajectories.py). Se comprueban propiedades geometricas
(velocidad constante, radio constante, reproducibilidad con semilla fija)
en vez de valores exactos punto a punto, salvo donde el resultado es
trivial de calcular a mano (p.ej. la posicion inicial).
"""

import math
import random

import pytest

from src.model import ProtectedAsset
from src.simulation.scenario import Scenario, ThreatArchetype, ThreatSpec
from src.simulation.trajectories import build_ground_truth


def _scenario(asset: ProtectedAsset, threat: ThreatSpec, duration_s: float = 10.0, timestep_s: float = 1.0):
    return Scenario(
        name="test",
        description="",
        duration_s=duration_s,
        timestep_s=timestep_s,
        random_seed=1,
        assets=(asset,),
        sensors=(),
        threats=(threat,),
    )


def test_fpv_attack_starts_exactly_at_start_position(position_factory):
    target_asset = ProtectedAsset(
        asset_id="a1", position=position_factory(east_m=1000.0), criticality=1, ring_radii_m={}
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=0.0),
        speed_mps=10.0,
        target_asset_id="a1",
    )
    states = build_ground_truth(threat, _scenario(target_asset, threat), random.Random(0))

    assert states[0].position.east_m == pytest.approx(0.0)
    assert states[0].timestamp_s == 0.0


def test_fpv_attack_moves_monotonically_closer_to_target(position_factory):
    target_asset = ProtectedAsset(
        asset_id="a1", position=position_factory(east_m=1000.0), criticality=1, ring_radii_m={}
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=0.0),
        speed_mps=10.0,
        target_asset_id="a1",
    )
    states = build_ground_truth(threat, _scenario(target_asset, threat), random.Random(0))

    distances = [1000.0 - s.position.east_m for s in states]
    assert distances == sorted(distances, reverse=True)


def test_fpv_attack_speed_is_constant_and_matches_spec(position_factory):
    target_asset = ProtectedAsset(
        asset_id="a1", position=position_factory(east_m=500.0, north_m=500.0), criticality=1, ring_radii_m={}
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=15.0,
        target_asset_id="a1",
    )
    states = build_ground_truth(threat, _scenario(target_asset, threat), random.Random(0))

    for state in states:
        assert state.velocity.speed_mps == pytest.approx(15.0)


def test_isr_loiter_maintains_constant_radius_from_target(position_factory):
    target_asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.ISR_LOITER,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=500.0),
        speed_mps=10.0,
        target_asset_id="a1",
        loiter_radius_m=500.0,
    )
    states = build_ground_truth(threat, _scenario(target_asset, threat, duration_s=60.0), random.Random(0))

    for state in states:
        radius = math.hypot(state.position.east_m, state.position.north_m)
        assert radius == pytest.approx(500.0, abs=1e-6)


def test_isr_loiter_speed_is_constant_and_matches_spec(position_factory):
    target_asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.ISR_LOITER,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=500.0),
        speed_mps=10.0,
        target_asset_id="a1",
        loiter_radius_m=500.0,
    )
    states = build_ground_truth(threat, _scenario(target_asset, threat, duration_s=60.0), random.Random(0))

    for state in states:
        assert state.velocity.speed_mps == pytest.approx(10.0)


def test_isr_loiter_rejects_non_positive_radius(position_factory):
    target_asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.ISR_LOITER,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=500.0),
        speed_mps=10.0,
        target_asset_id="a1",
        loiter_radius_m=0.0,
    )
    with pytest.raises(ValueError, match="loiter_radius_m"):
        build_ground_truth(threat, _scenario(target_asset, threat), random.Random(0))


def test_fpv_attack_without_target_asset_id_raises(position_factory):
    target_asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=10.0,
        target_asset_id=None,
    )
    with pytest.raises(ValueError, match="target_asset_id"):
        build_ground_truth(threat, _scenario(target_asset, threat), random.Random(0))


def test_commercial_wander_speed_magnitude_is_constant(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.COMMERCIAL_WANDER,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=6.0,
        heading_volatility_dps=25.0,
    )
    states = build_ground_truth(threat, _scenario(asset, threat), random.Random(0))

    for state in states:
        assert state.velocity.speed_mps == pytest.approx(6.0)


def test_commercial_wander_is_reproducible_with_same_seed(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.COMMERCIAL_WANDER,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=6.0,
        heading_volatility_dps=25.0,
    )
    scenario = _scenario(asset, threat)

    states_a = build_ground_truth(threat, scenario, random.Random(99))
    states_b = build_ground_truth(threat, scenario, random.Random(99))

    assert [s.position for s in states_a] == [s.position for s in states_b]


def test_commercial_wander_differs_with_different_seed(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.COMMERCIAL_WANDER,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=6.0,
        heading_volatility_dps=25.0,
    )
    scenario = _scenario(asset, threat)

    states_a = build_ground_truth(threat, scenario, random.Random(1))
    states_b = build_ground_truth(threat, scenario, random.Random(2))

    assert [s.position for s in states_a] != [s.position for s in states_b]


def test_bird_clutter_step_never_exceeds_speed_bound(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.BIRD_CLUTTER,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=100.0, north_m=100.0),
        speed_mps=2.0,
    )
    scenario = _scenario(asset, threat, duration_s=20.0)
    states = build_ground_truth(threat, scenario, random.Random(0))

    max_step = threat.speed_mps * scenario.timestep_s
    for previous, current in zip(states, states[1:], strict=False):
        step = math.hypot(
            current.position.east_m - previous.position.east_m,
            current.position.north_m - previous.position.north_m,
        )
        assert step <= max_step * math.sqrt(2) + 1e-9
