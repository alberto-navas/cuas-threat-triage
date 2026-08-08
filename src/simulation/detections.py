"""
Generacion de detecciones ruidosas de sensor a partir de las trayectorias
"verdad fundamental" de src/simulation/trajectories.py.

Cada sensor, en cada instante en que una amenaza esta activa, tiene una
probabilidad `detection_probability` de detectarla si esta dentro de
`max_range_m`; cuando la detecta, la posicion registrada lleva ruido
gaussiano de desviacion `noise_std_m` en cada componente. El resultado es
la unica entrada que ve el resto del pipeline (seguimiento en adelante):
ni el arquetipo ni la posicion verdadera son visibles aguas abajo.
"""

import math
import random

from src.model import Detection, Position
from src.simulation.scenario import Scenario
from src.simulation.trajectories import build_ground_truth


def _distance_m(a: Position, b: Position) -> float:
    return math.sqrt((a.east_m - b.east_m) ** 2 + (a.north_m - b.north_m) ** 2 + (a.up_m - b.up_m) ** 2)


def _noisy_position(true_position: Position, noise_std_m: float, rng: random.Random) -> Position:
    return Position(
        east_m=true_position.east_m + rng.gauss(0.0, noise_std_m),
        north_m=true_position.north_m + rng.gauss(0.0, noise_std_m),
        up_m=true_position.up_m + rng.gauss(0.0, noise_std_m),
    )


def simulate_detections(scenario: Scenario) -> list[Detection]:
    """Simula el escenario completo: genera la trayectoria verdadera de
    cada amenaza (src.simulation.trajectories.build_ground_truth) y, para
    cada sensor y cada instante en que la amenaza esta dentro de alcance,
    sortea si se detecta y con que ruido. Toda la aleatoriedad (deriva de
    trayectorias + sorteos de deteccion/ruido) sale de un unico generador
    sembrado con `scenario.random_seed`, asi que el mismo escenario
    siempre produce la misma lista de detecciones.

    El orden de las detecciones devueltas no esta garantizado -- quien las
    consuma (seguimiento) debe ordenarlas por `timestamp_s` si lo
    necesita."""
    rng = random.Random(scenario.random_seed)
    ground_truth = {threat.track_id: build_ground_truth(threat, scenario, rng) for threat in scenario.threats}

    detections: list[Detection] = []
    for states in ground_truth.values():
        for state in states:
            for sensor in scenario.sensors:
                if _distance_m(state.position, sensor.position) > sensor.max_range_m:
                    continue
                if rng.random() > sensor.detection_probability:
                    continue
                detections.append(
                    Detection(
                        sensor_id=sensor.sensor_id,
                        sensor_type=sensor.sensor_type,
                        timestamp_s=state.timestamp_s,
                        position=_noisy_position(state.position, sensor.noise_std_m, rng),
                    )
                )
    return detections
