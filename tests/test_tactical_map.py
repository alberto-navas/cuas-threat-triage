"""
Tests del mapa tactico (src/report/tactical_map.py).
"""

from pathlib import Path

from src.model import Track, TrackStatus
from src.pipeline import run_scenario
from src.report.tactical_map import build_tactical_map_html
from src.simulation.scenario import load_scenario

_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def test_map_html_includes_every_asset_and_prioritized_track():
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")
    result = run_scenario(scenario)

    html = build_tactical_map_html(list(result.scenario.assets), result.tracks, result.priority)

    for asset in result.scenario.assets:
        assert asset.asset_id in html
    for entry in result.priority:
        assert entry.score.track_id in html


def test_map_html_is_self_contained_with_no_external_script_src():
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")
    result = run_scenario(scenario)

    html = build_tactical_map_html(list(result.scenario.assets), result.tracks, result.priority)

    assert "plotly" in html.lower()
    assert "<script src=" not in html.lower()


def test_map_html_skips_ephemeral_ghost_tracks(position_factory, track_state_factory):
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")
    result = run_scenario(scenario)

    ghost = Track(
        track_id="TRK-GHOST",
        status=TrackStatus.DROPPED,
        history=[track_state_factory(position=position_factory())],
    )

    html = build_tactical_map_html(list(result.scenario.assets), [*result.tracks, ghost], result.priority)

    assert "TRK-GHOST" not in html


def test_map_html_skips_tracks_without_history(position_factory):
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")
    result = run_scenario(scenario)

    empty_track = Track(track_id="TRK-EMPTY", status=TrackStatus.TENTATIVE, history=[])

    html = build_tactical_map_html(list(result.scenario.assets), [*result.tracks, empty_track], result.priority)

    assert "TRK-EMPTY" not in html
