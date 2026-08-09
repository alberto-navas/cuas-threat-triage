"""
Tests de la traduccion (src/report/i18n.py): normalizacion de idioma,
re-renderizado de componentes de puntuacion, y textos fijos de interfaz.
"""

import pytest

from src.report.i18n import (
    COMPONENT_NAME_LABELS,
    SUPPORTED_LANGUAGES,
    TIER_LABELS,
    labels_for,
    normalize_lang,
    translate_component,
    ui,
)


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_normalize_lang_returns_supported_language_unchanged(lang):
    assert normalize_lang(lang) == lang


def test_normalize_lang_falls_back_to_default_for_unsupported():
    assert normalize_lang("fr") == "es"


def test_normalize_lang_falls_back_to_default_for_none():
    assert normalize_lang(None) == "es"


def test_translate_component_returns_rationale_verbatim_without_message_key():
    result = translate_component(None, {}, "texto original", "en")
    assert result == "texto original"


def test_translate_component_returns_rationale_verbatim_for_unknown_key():
    result = translate_component("no_existe_esta_clave", {}, "texto original", "en")
    assert result == "texto original"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_translate_component_renders_asset_criticality_in_every_language(lang):
    result = translate_component("asset_criticality", {"asset_id": "puesto_1", "criticality": 4}, "fallback", lang)

    assert "puesto_1" in result
    assert "4" in result
    assert "5" in result


def test_translate_component_translates_the_drone_class_label():
    params = {"drone_class": "fpv_attack", "confidence": 0.8, "base_risk": 100.0, "neutral": 50.0}

    es_text = translate_component("classification_risk", params, "fallback", "es")
    en_text = translate_component("classification_risk", params, "fallback", "en")

    assert "ataque FPV" in es_text
    assert "FPV attack" in en_text
    # el identificador crudo se conserva entre parentesis en ambos, para trazabilidad
    assert "fpv_attack" in es_text
    assert "fpv_attack" in en_text


def test_translate_component_falls_back_to_raw_key_for_unknown_drone_class():
    params = {"drone_class": "algo_inventado", "confidence": 0.5, "base_risk": 50.0, "neutral": 50.0}

    result = translate_component("classification_risk", params, "fallback", "en")

    assert "algo_inventado" in result


def test_labels_for_flattens_tier_labels_for_a_language():
    labels = labels_for(TIER_LABELS, "de")

    assert labels["critical"] == "kritisch"
    assert labels["low"] == "niedrig"


def test_labels_for_flattens_component_name_labels_for_a_language():
    labels = labels_for(COMPONENT_NAME_LABELS, "en")

    assert labels["cinematica"] == "Kinematics"
    assert labels["criticidad_activo"] == "Asset criticality"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_ui_returns_the_same_keys_for_every_language(lang):
    es_keys = set(ui("es").keys())
    assert set(ui(lang).keys()) == es_keys


def test_ui_falls_back_to_spanish_for_unsupported_language():
    assert ui("fr") == ui("es")
