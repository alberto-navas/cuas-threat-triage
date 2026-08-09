"""
Punto de entrada de linea de comandos: escenario YAML -> informe HTML.

Ejemplo de uso:
    python -m src.cli data/scenarios/demo_mixed_threats.yaml
    python -m src.cli data/scenarios/demo_mixed_threats.yaml --output output/demo.html

Con varios escenarios a la vez, cada uno genera su propio informe dentro de
un directorio de salida:
    python -m src.cli data/scenarios/*.yaml --output output/
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from src.model import TrackStatus
from src.pipeline import PipelineResult, run_scenario
from src.report.generator import save_report
from src.report.i18n import SUPPORTED_LANGUAGES
from src.simulation.scenario import load_scenario
from src.tracking.tracker import MultiTargetTracker


def _run_and_report(
    scenario_path: Path, output_path: Path, tracker_kwargs: dict[str, Any], lang: str
) -> PipelineResult:
    """Procesa un unico escenario de principio a fin. Construye un
    `MultiTargetTracker` nuevo por cada llamada -- es un objeto con
    estado (acumula trazas en cada `run()`), asi que compartir una misma
    instancia entre varios escenarios mezclaria las trazas de uno con las
    del otro."""
    print(f"Cargando escenario {scenario_path}...")
    scenario = load_scenario(scenario_path)
    print(
        f"  {len(scenario.assets)} activo(s), {len(scenario.sensors)} sensor(es), "
        f"{len(scenario.threats)} amenaza(s) definida(s)."
    )

    tracker = MultiTargetTracker(**tracker_kwargs)
    result = run_scenario(scenario, tracker=tracker)
    confirmed = sum(1 for track in result.tracks if track.status == TrackStatus.CONFIRMED)
    print(
        f"  {len(result.tracks)} traza(s) construida(s) ({confirmed} confirmada(s)), "
        f"{len(result.priority)} evaluada(s) en el ranking de prioridad."
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_report(result, output_path, lang=lang)
    print(f"  Informe en {output_path}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simula un escenario C-UAS y genera un informe HTML con el ranking de prioridad de amenaza."
    )
    parser.add_argument(
        "scenarios",
        type=Path,
        nargs="+",
        help=(
            "Ruta a uno o varios escenarios YAML (ver data/scenarios/). Con varios, cada uno genera su propio informe."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Con un solo escenario: ruta del informe HTML (por defecto output/<nombre>.html). "
            "Con varios: directorio donde se genera un informe por escenario (por defecto output/)."
        ),
    )
    parser.add_argument(
        "--gate-distance-m",
        type=float,
        default=None,
        help="Puerta de asociacion del tracker, en metros (por defecto la de MultiTargetTracker: 150).",
    )
    parser.add_argument(
        "--confirm-hits",
        type=int,
        default=None,
        help="Aciertos consecutivos para confirmar una traza (por defecto 3).",
    )
    parser.add_argument(
        "--drop-misses",
        type=int,
        default=None,
        help="Fallos consecutivos para descartar una traza (por defecto 3).",
    )
    parser.add_argument(
        "--lang",
        choices=list(SUPPORTED_LANGUAGES),
        default="es",
        help="Idioma del informe HTML generado (por defecto: es).",
    )
    args = parser.parse_args(argv)

    for scenario_path in args.scenarios:
        if not scenario_path.exists():
            raise SystemExit(f"No existe el escenario: {scenario_path}")

    tracker_kwargs: dict[str, Any] = {}
    if args.gate_distance_m is not None:
        tracker_kwargs["gate_distance_m"] = args.gate_distance_m
    if args.confirm_hits is not None:
        tracker_kwargs["confirm_hits"] = args.confirm_hits
    if args.drop_misses is not None:
        tracker_kwargs["drop_misses"] = args.drop_misses

    if len(args.scenarios) == 1:
        scenario_path = args.scenarios[0]
        output_path = args.output or (Path("output") / f"{scenario_path.stem}.html")
        _run_and_report(scenario_path, output_path, tracker_kwargs, args.lang)
    else:
        output_dir = args.output or Path("output")
        for scenario_path in args.scenarios:
            output_path = output_dir / f"{scenario_path.stem}.html"
            _run_and_report(scenario_path, output_path, tracker_kwargs, args.lang)

    print("Listo.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
