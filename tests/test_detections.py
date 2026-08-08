"""
Tests de la simulacion de detecciones ruidosas (src/simulation/detections.py).
"""

import random

from src.model import ProtectedAsset, SensorType
from src.simulation.detections import simulate_detections
from src.simulation.scenario import Scenario, SensorSpec, ThreatArchetype, ThreatSpec, load_scenario
from src.simulation.trajectories import build_ground_truth


def test_simulate_detections_matches_ground_truth_with_full_probability_and_no_noise(fixtures_dir):
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")
    detections = simulate_detections(scenario)

    expected_states = build_ground_truth(scenario.threats[0], scenario, random.Random(scenario.random_seed))

    assert len(detections) == len(expected_states)
    detected_positions = sorted((d.timestamp_s, d.position) for d in detections)
    expected_positions = sorted((s.timestamp_s, s.position) for s in expected_states)
    assert detected_positions == expected_positions


def test_simulate_detections_respects_max_range(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    far_sensor = SensorSpec(
        sensor_id="s1",
        sensor_type=SensorType.RADAR,
        position=position_factory(east_m=100_000.0, north_m=100_000.0),
        noise_std_m=0.0,
        detection_probability=1.0,
        max_range_m=100.0,
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=1000.0),
        speed_mps=20.0,
        target_asset_id="a1",
    )
    scenario = Scenario(
        name="test",
        description="",
        duration_s=5.0,
        timestep_s=1.0,
        random_seed=0,
        assets=(asset,),
        sensors=(far_sensor,),
        threats=(threat,),
    )

    assert simulate_detections(scenario) == []


def test_simulate_detections_zero_probability_produces_no_detections(position_factory):
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    silent_sensor = SensorSpec(
        sensor_id="s1",
        sensor_type=SensorType.RADAR,
        position=position_factory(),
        noise_std_m=0.0,
        detection_probability=0.0,
        max_range_m=10_000.0,
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=1000.0),
        speed_mps=20.0,
        target_asset_id="a1",
    )
    scenario = Scenario(
        name="test",
        description="",
        duration_s=5.0,
        timestep_s=1.0,
        random_seed=0,
        assets=(asset,),
        sensors=(silent_sensor,),
        threats=(threat,),
    )

    assert simulate_detections(scenario) == []


def _partial_visibility_scenario(position_factory, random_seed: int) -> Scenario:
    asset = ProtectedAsset(asset_id="a1", position=position_factory(), criticality=1, ring_radii_m={})
    sensor = SensorSpec(
        sensor_id="s1",
        sensor_type=SensorType.RADAR,
        position=position_factory(),
        noise_std_m=10.0,
        detection_probability=0.5,
        max_range_m=10_000.0,
    )
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(east_m=1000.0),
        speed_mps=20.0,
        target_asset_id="a1",
    )
    return Scenario(
        name="test",
        description="",
        duration_s=30.0,
        timestep_s=1.0,
        random_seed=random_seed,
        assets=(asset,),
        sensors=(sensor,),
        threats=(threat,),
    )


def test_simulate_detections_is_reproducible_with_same_seed(position_factory):
    scenario = _partial_visibility_scenario(position_factory, random_seed=123)

    assert simulate_detections(scenario) == simulate_detections(scenario)


def test_simulate_detections_differs_with_different_seed(position_factory):
    detections_a = simulate_detections(_partial_visibility_scenario(position_factory, random_seed=1))
    detections_b = simulate_detections(_partial_visibility_scenario(position_factory, random_seed=2))

    assert detections_a != detections_b
