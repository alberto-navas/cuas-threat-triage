"""
Ensamblado del informe HTML autocontenido: cabecera con el resumen del
escenario, mapa tactico y tabla de prioridad con el desglose completo de
cada puntuacion. Un unico fichero, sin dependencias externas (el JS de
plotly va incrustado) -- se puede abrir con doble clic o compartir sin
depender de que ningun servidor este vivo.
"""

from datetime import UTC, datetime
from pathlib import Path

import jinja2

from src.pipeline import PipelineResult
from src.report.tactical_map import build_tactical_map_html

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def generate_report_html(result: PipelineResult) -> str:
    map_html = build_tactical_map_html(list(result.scenario.assets), result.tracks, result.priority)
    template = _ENV.get_template("report.html")
    return template.render(
        scenario=result.scenario,
        priority=result.priority,
        map_html=map_html,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )


def save_report(result: PipelineResult, output_path: str | Path) -> Path:
    """Genera el informe y lo escribe en `output_path`. Devuelve la ruta
    como `Path`, para que quien la llame no tenga que volver a convertirla."""
    output_path = Path(output_path)
    output_path.write_text(generate_report_html(result), encoding="utf-8")
    return output_path
