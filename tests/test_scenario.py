"""
Tests de carga y validacion de escenarios (src/simulation/scenario.py).
"""

from pathlib import Path

import pytest

from src.model import ProtectedAsset, SensorType
from src.simulation.scenario import (
    Scenario,
    SensorSpec,
    ThreatArchetype,
    ThreatSpec,
    load_scenario,
    parse_scenario_yaml,
)


def test_load_scenario_parses_assets_sensors_and_threats(fixtures_dir):
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")

    assert scenario.name == "minimal_test_scenario"
    assert len(scenario.assets) == 1
    assert scenario.assets[0].asset_id == "asset_1"
    assert len(scenario.sensors) == 1
    assert scenario.sensors[0].sensor_type == SensorType.RADAR
    assert len(scenario.threats) == 1
    assert scenario.threats[0].archetype == ThreatArchetype.FPV_ATTACK
    assert scenario.threats[0].target_asset_id == "asset_1"


def test_parse_scenario_yaml_matches_load_scenario_from_the_same_text(fixtures_dir):
    text = (fixtures_dir / "minimal_scenario.yaml").read_text(encoding="utf-8")

    scenario = parse_scenario_yaml(text)

    assert scenario.name == "minimal_test_scenario"
    assert scenario.assets[0].asset_id == "asset_1"


def test_load_scenario_rejects_unknown_target_asset(fixtures_dir):
    with pytest.raises(ValueError, match="asset_desconocido"):
        load_scenario(fixtures_dir / "invalid_scenario_unknown_asset.yaml")


def test_asset_by_id_returns_matching_asset(fixtures_dir):
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")
    assert scenario.asset_by_id("asset_1").asset_id == "asset_1"


def test_asset_by_id_raises_for_unknown_id(fixtures_dir):
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")
    with pytest.raises(KeyError):
        scenario.asset_by_id("no_existe")


def _minimal_asset(position_factory, asset_id: str = "a1") -> ProtectedAsset:
    return ProtectedAsset(asset_id=asset_id, position=position_factory(), criticality=1, ring_radii_m={})


def _minimal_sensor(position_factory, sensor_id: str = "s1") -> SensorSpec:
    return SensorSpec(
        sensor_id=sensor_id,
        sensor_type=SensorType.RADAR,
        position=position_factory(),
        noise_std_m=0.0,
        detection_probability=1.0,
        max_range_m=1000.0,
    )


def test_scenario_rejects_non_positive_duration(position_factory):
    with pytest.raises(ValueError, match="duration_s"):
        Scenario(
            name="x",
            description="",
            duration_s=0.0,
            timestep_s=1.0,
            random_seed=0,
            assets=(_minimal_asset(position_factory),),
            sensors=(),
            threats=(),
        )


def test_scenario_rejects_non_positive_timestep(position_factory):
    with pytest.raises(ValueError, match="timestep_s"):
        Scenario(
            name="x",
            description="",
            duration_s=10.0,
            timestep_s=0.0,
            random_seed=0,
            assets=(_minimal_asset(position_factory),),
            sensors=(),
            threats=(),
        )


def test_scenario_rejects_duplicate_asset_ids(position_factory):
    with pytest.raises(ValueError, match="activo duplicad"):
        Scenario(
            name="x",
            description="",
            duration_s=10.0,
            timestep_s=1.0,
            random_seed=0,
            assets=(_minimal_asset(position_factory, "a1"), _minimal_asset(position_factory, "a1")),
            sensors=(),
            threats=(),
        )


def test_scenario_rejects_duplicate_track_ids(position_factory):
    asset = _minimal_asset(position_factory)
    threat = ThreatSpec(
        track_id="T-1",
        archetype=ThreatArchetype.FPV_ATTACK,
        spawn_time_s=0.0,
        start_position=position_factory(),
        speed_mps=10.0,
        target_asset_id=asset.asset_id,
    )
    with pytest.raises(ValueError, match="traza duplicad"):
        Scenario(
            name="x",
            description="",
            duration_s=10.0,
            timestep_s=1.0,
            random_seed=0,
            assets=(asset,),
            sensors=(),
            threats=(threat, threat),
        )


DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


@pytest.mark.parametrize(
    "scenario_file",
    ["demo_mixed_threats.yaml", "demo_swarm_multi_asset.yaml"],
)
def test_demo_scenarios_load_without_error(scenario_file):
    """Los escenarios de demostracion versionados en data/scenarios/ deben
    seguir siendo validos a medida que evoluciona el esquema -- este test
    los ejercita igual que a cualquier fixture, para detectar erratas."""
    scenario = load_scenario(DEMO_SCENARIOS_DIR / scenario_file)
    assert len(scenario.threats) > 0
    assert len(scenario.assets) > 0


def test_sensor_spec_rejects_detection_probability_out_of_range(position_factory):
    with pytest.raises(ValueError, match="detection_probability"):
        SensorSpec(
            sensor_id="s1",
            sensor_type=SensorType.RADAR,
            position=position_factory(),
            noise_std_m=0.0,
            detection_probability=1.5,
            max_range_m=1000.0,
        )
