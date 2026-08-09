"""
Tests del pipeline completo (src/pipeline.py): escenario -> detecciones ->
trazas -> ranking de prioridad, encadenado de punta a punta.
"""

from pathlib import Path

from src.model import DroneClass, ThreatTier, TrackStatus
from src.pipeline import run_scenario
from src.simulation.scenario import load_scenario
from src.tracking.tracker import MultiTargetTracker

_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def test_run_scenario_minimal_produces_one_confirmed_track_and_priority_entry(fixtures_dir):
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")

    result = run_scenario(scenario)

    assert result.scenario is scenario
    assert len(result.tracks) == 1
    assert result.tracks[0].status == TrackStatus.CONFIRMED
    assert len(result.priority) == 1
    assert result.priority[0].rank == 1


def test_run_scenario_accepts_a_custom_tracker(fixtures_dir):
    # gate_distance_m debe superar el desplazamiento entre pasos del
    # objetivo (20 m/s x 1.0 s = 20 m) para que la asociacion funcione.
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")
    custom_tracker = MultiTargetTracker(gate_distance_m=60.0, confirm_hits=1, drop_misses=1)

    result = run_scenario(scenario, tracker=custom_tracker)

    assert len(result.tracks) == 1
    assert result.tracks[0].status == TrackStatus.CONFIRMED


def test_run_scenario_demo_mixed_threats_ranks_the_direct_attack_first():
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")

    result = run_scenario(scenario)

    assert len(result.priority) == 4
    top = result.priority[0]
    assert top.rank == 1
    assert top.score.tier == ThreatTier.CRITICAL

    classification_component = next(c for c in top.score.components if c.name == "clasificacion")
    assert DroneClass.FPV_ATTACK.value in classification_component.rationale
