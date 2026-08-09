"""
Tests del ensamblado del informe HTML (src/report/generator.py).
"""

from pathlib import Path

import markupsafe

from src.pipeline import run_scenario
from src.report.generator import generate_report_html, save_report
from src.simulation.scenario import load_scenario

_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def _result():
    scenario = load_scenario(_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml")
    return run_scenario(scenario)


def test_report_starts_with_doctype_and_is_well_formed_shell():
    html = generate_report_html(_result())

    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "</html>" in html


def test_report_contains_scenario_name_and_description():
    result = _result()
    html = generate_report_html(result)

    assert result.scenario.name in html
    assert result.scenario.description.strip().split("\n")[0][:20] in html


def test_report_contains_every_priority_entry_and_its_components():
    result = _result()
    html = generate_report_html(result)

    for entry in result.priority:
        assert entry.score.track_id in html
        assert entry.score.asset_id in html
        for component in entry.score.components:
            # El desglose se renderiza con autoescape (comillas/acentos se
            # convierten en entidades HTML), asi que se compara la version
            # escapada, no el texto literal.
            assert str(markupsafe.escape(component.rationale)) in html


def test_report_contains_tier_tags():
    result = _result()
    html = generate_report_html(result)

    seen_tiers = {entry.score.tier.value for entry in result.priority}
    for tier_value in seen_tiers:
        assert f"tag-{tier_value}" in html


def test_report_includes_the_ethical_scope_footer():
    html = generate_report_html(_result())

    assert "sintéticos" in html
    assert "neutralización" in html


def test_save_report_writes_the_file(tmp_path):
    output_path = tmp_path / "report.html"

    returned_path = save_report(_result(), output_path)

    assert returned_path == output_path
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
