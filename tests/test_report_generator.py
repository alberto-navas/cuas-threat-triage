"""
Tests del ensamblado del informe HTML (src/report/generator.py), incluida
la traduccion a los 3 idiomas soportados.
"""

from pathlib import Path

import markupsafe
import pytest

from src.pipeline import run_scenario
from src.report.generator import generate_report_html, save_report
from src.report.i18n import SUPPORTED_LANGUAGES, translate_component
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


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_report_contains_every_priority_entry_and_its_translated_components(lang):
    result = _result()
    html = generate_report_html(result, lang=lang)

    for entry in result.priority:
        assert entry.score.track_id in html
        assert entry.score.asset_id in html
        for component in entry.score.components:
            translated = translate_component(component.message_key, component.message_params, component.rationale, lang)
            # El desglose se renderiza con autoescape (comillas/acentos se
            # convierten en entidades HTML), asi que se compara la version
            # escapada, no el texto literal.
            assert str(markupsafe.escape(translated)) in html


def test_report_contains_tier_tags():
    result = _result()
    html = generate_report_html(result)

    seen_tiers = {entry.score.tier.value for entry in result.priority}
    for tier_value in seen_tiers:
        assert f"tag-{tier_value}" in html


def test_report_default_language_is_spanish():
    html = generate_report_html(_result())

    assert 'lang="es"' in html
    assert "Informe de amenazas" in html


def test_report_in_english_translates_headings_and_html_lang_attribute():
    html = generate_report_html(_result(), lang="en")

    assert 'lang="en"' in html
    assert "Threat report" in html
    assert "Tactical map" in html
    assert "Response priority" in html


def test_report_in_german_translates_headings_and_html_lang_attribute():
    html = generate_report_html(_result(), lang="de")

    assert 'lang="de"' in html
    assert "Bedrohungsbericht" in html
    assert "Taktische Karte" in html
    assert "Reaktionspriorität" in html


def test_report_unsupported_language_falls_back_to_spanish():
    html = generate_report_html(_result(), lang="fr")

    assert 'lang="es"' in html
    assert "Informe de amenazas" in html


def test_report_scenario_description_is_not_translated():
    """El nombre/descripcion del escenario es texto del propio YAML, no de
    la interfaz: debe viajar igual en cualquier idioma del informe (ver
    src/report/i18n.py)."""
    result = _result()
    description_fragment = result.scenario.description.strip().split("\n")[0][:20]

    for lang in SUPPORTED_LANGUAGES:
        html = generate_report_html(result, lang=lang)
        assert description_fragment in html


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


def test_save_report_respects_lang(tmp_path):
    output_path = tmp_path / "report_en.html"

    save_report(_result(), output_path, lang="en")

    assert "Threat report" in output_path.read_text(encoding="utf-8")
