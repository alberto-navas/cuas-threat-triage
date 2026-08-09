"""
Panel web: elegir un escenario de demostracion (o subir uno propio) y ver
el informe de priorizacion directamente en el navegador.

Es una capa fina sobre el mismo pipeline que usa la CLI (src/cli.py):
src/pipeline.py para la simulacion + tracking + priorizacion,
src/report/generator.py para el HTML. Esta app no reimplementa nada de
eso, solo adapta la entrada (seleccion o subida por HTTP en vez de una
ruta de archivo) y la salida (HTML servido directamente en vez de escrito
a disco).

Importante: esto es un REPLAY de un escenario simulado, no ingesta de
sensores reales en tiempo real -- ver el pie de cada informe generado y el
README del proyecto.
"""

from pathlib import Path

import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.pipeline import run_scenario
from src.report.generator import generate_report_html
from src.simulation.scenario import Scenario, parse_scenario_yaml

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEMO_SCENARIOS_DIR = Path(__file__).parent.parent.parent / "data" / "scenarios"

# Un escenario YAML de este proyecto es texto minusculo (activos, sensores,
# unas pocas amenazas): unos pocos KB. 1 MB es generoso para eso sin dejar
# la subida sin limite (una subida sin limite es una superficie de abuso
# trivial en cualquier server que acepte archivos).
_MAX_UPLOAD_SIZE_BYTES = 1024 * 1024

# Limite de peticiones por IP a /run: simula detecciones, construye trazas
# y las puntua -- no es gratis, y esta pensado para correr en un plan
# gratuito. 20/minuto es generoso para probar varios escenarios seguidos
# pero corta un bucle automatizado.
_RUN_RATE_LIMIT = "20/minute"

# Errores esperables al parsear un YAML que no tiene por que ser valido
# (subido por un usuario): YAML mal formado, campos obligatorios ausentes,
# o el propio fichero vacio (raw=None, cualquier raw[...] lanza TypeError).
# Se traducen a un 400 legible, nunca a un traceback de 500.
_SCENARIO_PARSE_ERRORS = (ValueError, KeyError, TypeError, yaml.YAMLError)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="C-UAS Threat Triage")
app.state.limiter = limiter
# El handler de slowapi tiene una firma mas especifica (RateLimitExceeded en
# vez de Exception generico) de la que espera el stub de Starlette; es el
# patron oficial de slowapi (ver su documentacion), no un error real.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _demo_scenario_options() -> list[dict[str, str]]:
    """Nombre de fichero + nombre + descripcion de cada escenario de demo
    versionado en data/scenarios/, para listarlos en el formulario. El
    nombre de fichero es tambien la unica forma valida de referenciar un
    escenario de demo en /run (ver la comprobacion de la lista blanca ahi)
    -- nunca se acepta una ruta arbitraria del cliente."""
    options = []
    for path in sorted(_DEMO_SCENARIOS_DIR.glob("*.yaml")):
        scenario = parse_scenario_yaml(path.read_text(encoding="utf-8"))
        options.append({"filename": path.name, "name": scenario.name, "description": scenario.description})
    return options


@app.get("/", response_class=HTMLResponse)
async def form(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(request, "form.html", {"demo_scenarios": _demo_scenario_options()})


def _load_scenario_text(demo_scenario: str, uploaded_bytes: bytes | None) -> str:
    if demo_scenario:
        valid_names = {option["filename"] for option in _demo_scenario_options()}
        if demo_scenario not in valid_names:
            raise HTTPException(status_code=400, detail=f"Escenario de demostracion desconocido: '{demo_scenario}'.")
        return (_DEMO_SCENARIOS_DIR / demo_scenario).read_text(encoding="utf-8")

    assert uploaded_bytes is not None  # garantizado por el XOR comprobado en run()
    return uploaded_bytes.decode("utf-8", errors="replace")


def _parse_scenario(text: str) -> Scenario:
    try:
        return parse_scenario_yaml(text)
    except _SCENARIO_PARSE_ERRORS as exc:
        raise HTTPException(status_code=400, detail=f"Escenario invalido: {exc}") from exc


@app.post("/run", response_class=HTMLResponse)
@limiter.limit(_RUN_RATE_LIMIT)
async def run(
    request: Request,  # requerido por @limiter.limit para identificar al cliente (IP), no se usa directamente aqui
    demo_scenario: str = Form(""),
    scenario_file: UploadFile | None = File(None),  # noqa: B008 — patron estandar de FastAPI, no una llamada real en cada request
) -> HTMLResponse:
    has_upload = scenario_file is not None and bool(scenario_file.filename)
    if bool(demo_scenario) == has_upload:
        raise HTTPException(
            status_code=400, detail="Elige un escenario de demostracion o sube un YAML propio, no ambos ni ninguno."
        )

    uploaded_bytes = None
    if has_upload:
        assert scenario_file is not None
        uploaded_bytes = await scenario_file.read()
        if len(uploaded_bytes) > _MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413, detail=f"El fichero supera el limite de {_MAX_UPLOAD_SIZE_BYTES // 1024} KB."
            )

    scenario_text = _load_scenario_text(demo_scenario, uploaded_bytes)
    scenario = _parse_scenario(scenario_text)

    result = run_scenario(scenario)
    return HTMLResponse(generate_report_html(result))
