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

from src.decision.prioritizer import PriorityEntry
from src.pipeline import PipelineResult
from src.report.i18n import COMPONENT_NAME_LABELS, TIER_LABELS, labels_for, normalize_lang, translate_component, ui
from src.report.tactical_map import build_tactical_map_html

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(_TEMPLATE_DIR), autoescape=True)


def _build_entries(priority: list[PriorityEntry], lang: str) -> list[dict]:
    """Convierte cada `PriorityEntry` en un dict plano ya traducido a
    `lang`, listo para la plantilla -- construir el texto traducido aqui
    (en Python) en vez de en Jinja2 mantiene la logica de traduccion en un
    solo sitio (src/report/i18n.py), igual que hace el proyecto hermano."""
    component_labels = labels_for(COMPONENT_NAME_LABELS, lang)

    entries = []
    for entry in priority:
        components = [
            {
                "name": component.name,
                "name_label": component_labels.get(component.name, component.name),
                "value": component.value,
                "rationale": translate_component(
                    component.message_key, component.message_params, component.rationale, lang
                ),
            }
            for component in entry.score.components
        ]
        entries.append(
            {
                "rank": entry.rank,
                "track_id": entry.score.track_id,
                "asset_id": entry.score.asset_id,
                "total": entry.score.total,
                "tier": entry.score.tier.value,
                "components": components,
            }
        )
    return entries


def generate_report_html(result: PipelineResult, lang: str = "es") -> str:
    lang = normalize_lang(lang)
    map_html = build_tactical_map_html(list(result.scenario.assets), result.tracks, result.priority, lang=lang)
    template = _ENV.get_template("report.html")
    return template.render(
        lang=lang,
        scenario=result.scenario,
        entries=_build_entries(result.priority, lang),
        map_html=map_html,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        ui=ui(lang),
        tier_labels=labels_for(TIER_LABELS, lang),
    )


def save_report(result: PipelineResult, output_path: str | Path, lang: str = "es") -> Path:
    """Genera el informe y lo escribe en `output_path`. Devuelve la ruta
    como `Path`, para que quien la llame no tenga que volver a convertirla."""
    output_path = Path(output_path)
    output_path.write_text(generate_report_html(result, lang=lang), encoding="utf-8")
    return output_path
