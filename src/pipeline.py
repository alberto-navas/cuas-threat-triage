"""
Orquestacion del pipeline completo: escenario -> detecciones -> trazas ->
ranking de prioridad. Punto de entrada compartido por la CLI (src/cli.py) y
el panel web (src/web/), para que ninguno de los dos tenga que conocer el
orden de las etapas ni repetirlo.
"""

from dataclasses import dataclass

from src.decision.prioritizer import PriorityEntry, prioritize
from src.model import Track
from src.simulation.detections import simulate_detections
from src.simulation.scenario import Scenario
from src.tracking.tracker import MultiTargetTracker


@dataclass(frozen=True)
class PipelineResult:
    """Todo lo que necesita el informe (src/report/) para renderizar un
    escenario: el propio escenario (assets, sensores, duracion), las trazas
    que construyo el tracker (para el mapa tactico) y el ranking de
    prioridad ya calculado (para la tabla)."""

    scenario: Scenario
    tracks: list[Track]
    priority: list[PriorityEntry]


def run_scenario(scenario: Scenario, tracker: MultiTargetTracker | None = None) -> PipelineResult:
    """Simula el escenario, construye las trazas y calcula el ranking de
    prioridad. `tracker` es inyectable para que los tests (o un ajuste fino
    futuro de sus parametros) no tengan que duplicar esta funcion; por
    defecto usa la configuracion por defecto de `MultiTargetTracker`."""
    if tracker is None:
        tracker = MultiTargetTracker()

    detections = simulate_detections(scenario)
    num_steps = int(scenario.duration_s / scenario.timestep_s) + 1
    timestamps = [scenario.timestep_s * i for i in range(num_steps)]
    tracks = tracker.run(detections, timestamps=timestamps)

    priority = prioritize(tracks, list(scenario.assets))

    return PipelineResult(scenario=scenario, tracks=tracks, priority=priority)
