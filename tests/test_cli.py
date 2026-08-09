"""Tests de extremo a extremo del CLI (src/cli.py)."""

from pathlib import Path

import pytest

from src.cli import main

_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"
_MIXED_THREATS = _DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml"
_SWARM = _DEMO_SCENARIOS_DIR / "demo_swarm_multi_asset.yaml"


def test_single_scenario_generates_report(tmp_path):
    output_path = tmp_path / "report.html"

    exit_code = main([str(_MIXED_THREATS), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()
    html = output_path.read_text(encoding="utf-8")
    assert "demo_mixed_threats" in html
    assert "<!DOCTYPE html>" in html


def test_multiple_scenarios_generate_one_report_each(tmp_path):
    exit_code = main([str(_MIXED_THREATS), str(_SWARM), "--output", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "demo_mixed_threats.html").exists()
    assert (tmp_path / "demo_swarm_multi_asset.html").exists()


def test_missing_scenario_file_exits_with_error(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main([str(tmp_path / "no_existe.yaml")])
    assert exc_info.value.code != 0


def test_tracker_tuning_flags_are_accepted(tmp_path, fixtures_dir):
    output_path = tmp_path / "report.html"

    exit_code = main(
        [
            str(fixtures_dir / "minimal_scenario.yaml"),
            "--output",
            str(output_path),
            "--gate-distance-m",
            "60",
            "--confirm-hits",
            "1",
            "--drop-misses",
            "1",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()


def test_default_output_path_is_output_dir_with_scenario_stem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main([str(_MIXED_THREATS)])

    assert exit_code == 0
    assert (tmp_path / "output" / "demo_mixed_threats.html").exists()


def test_default_output_dir_for_multiple_scenarios(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main([str(_MIXED_THREATS), str(_SWARM)])

    assert exit_code == 0
    assert (tmp_path / "output" / "demo_mixed_threats.html").exists()
    assert (tmp_path / "output" / "demo_swarm_multi_asset.html").exists()
