"""
Tests del panel web (src/web/app.py), usando el TestClient de FastAPI (no
levanta un servidor real, invoca la app directamente en el mismo proceso).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from src.web.app import app, limiter

client = TestClient(app)

_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent / "data" / "scenarios"


def test_form_renders_with_demo_scenarios():
    response = client.get("/")

    assert response.status_code == 200
    assert "<form" in response.text
    assert "demo_mixed_threats.yaml" in response.text
    assert "demo_swarm_multi_asset.yaml" in response.text


def test_run_with_demo_scenario_returns_report():
    response = client.post("/run", data={"demo_scenario": "demo_mixed_threats.yaml"})

    assert response.status_code == 200
    assert "demo_mixed_threats" in response.text
    assert "<!DOCTYPE html>" in response.text


def test_run_with_uploaded_scenario_returns_report():
    content = (_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml").read_bytes()

    response = client.post(
        "/run",
        data={"demo_scenario": ""},
        files={"scenario_file": ("mi_escenario.yaml", content, "application/x-yaml")},
    )

    assert response.status_code == 200
    assert "demo_mixed_threats" in response.text


def test_run_without_any_selection_returns_400():
    response = client.post("/run", data={"demo_scenario": ""})

    assert response.status_code == 400
    assert "ambos ni ninguno" in response.json()["detail"]


def test_run_with_both_demo_and_upload_returns_400():
    content = (_DEMO_SCENARIOS_DIR / "demo_mixed_threats.yaml").read_bytes()

    response = client.post(
        "/run",
        data={"demo_scenario": "demo_mixed_threats.yaml"},
        files={"scenario_file": ("mi_escenario.yaml", content, "application/x-yaml")},
    )

    assert response.status_code == 400


def test_run_with_unknown_demo_scenario_name_returns_400():
    response = client.post("/run", data={"demo_scenario": "no_existe.yaml"})

    assert response.status_code == 400
    assert "desconocido" in response.json()["detail"]


def test_run_with_path_traversal_demo_scenario_name_returns_400():
    response = client.post("/run", data={"demo_scenario": "../../../pyproject.toml"})

    assert response.status_code == 400


def test_run_with_malformed_yaml_returns_400():
    response = client.post(
        "/run",
        data={"demo_scenario": ""},
        files={"scenario_file": ("roto.yaml", b"esto: [no es, valido", "application/x-yaml")},
    )

    assert response.status_code == 400
    assert "invalido" in response.json()["detail"].lower()


def test_run_with_incomplete_yaml_returns_400_not_500():
    """Un YAML sintacticamente valido pero sin las claves obligatorias
    (KeyError al construir el escenario) tambien debe traducirse a 400."""
    response = client.post(
        "/run",
        data={"demo_scenario": ""},
        files={"scenario_file": ("incompleto.yaml", b"name: solo_esto", "application/x-yaml")},
    )

    assert response.status_code == 400


def test_run_with_oversized_upload_returns_413():
    oversized = b"x" * (1024 * 1024 + 1)

    response = client.post(
        "/run",
        data={"demo_scenario": ""},
        files={"scenario_file": ("grande.yaml", oversized, "application/x-yaml")},
    )

    assert response.status_code == 413


def test_run_with_lang_translates_the_report():
    response = client.post("/run", data={"demo_scenario": "demo_mixed_threats.yaml", "lang": "en"})

    assert response.status_code == 200
    assert 'lang="en"' in response.text
    assert "Threat report" in response.text


def test_run_with_unsupported_lang_falls_back_to_spanish():
    """`lang` llega de un <input type="hidden"> controlado por el JS de
    form.html, pero nada impide que alguien lo mande a mano con un valor
    fuera de es/en/de. normalize_lang() debe caer a "es" en vez de romper
    la peticion."""
    response = client.post("/run", data={"demo_scenario": "demo_mixed_threats.yaml", "lang": "fr"})

    assert response.status_code == 200
    assert 'lang="es"' in response.text


def test_form_has_language_switcher_with_all_three_languages():
    response = client.get("/")
    html = response.text

    for lang in ("es", "en", "de"):
        assert f'data-lang="{lang}"' in html

    assert "Generar informe" in html  # es
    assert "Generate report" in html  # en
    assert "Bericht erstellen" in html  # de


def test_run_is_rate_limited_per_ip():
    limiter.reset()
    try:
        statuses = [
            client.post("/run", data={"demo_scenario": "demo_mixed_threats.yaml"}).status_code for _ in range(25)
        ]

        assert statuses.count(200) == 20  # el limite configurado, ver _RUN_RATE_LIMIT en app.py
        assert statuses.count(429) == 5
    finally:
        limiter.reset()  # no dejar la cuota consumida para tests que se ejecuten despues


def test_main_module_is_importable():
    """
    src/web/__main__.py solo se ejecuta con `python -m src.web`, nunca se
    importa desde el resto del codigo. Este test solo confirma que el
    modulo en si (sus imports a nivel de archivo) no tiene errores -- el
    `if __name__ == "__main__":` no se ejecuta al importarlo asi.
    """
    import src.web.__main__  # noqa: F401
