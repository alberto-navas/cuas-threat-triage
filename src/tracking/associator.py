"""
Asociacion vecino-mas-cercano (Global Nearest Neighbor) con puerta de
distancia, entre las posiciones predichas de las trazas activas y las
detecciones de un mismo instante.

Es una version simplificada de lo que hace un tracker GNN/JPDA real: asigna
cada deteccion a la traza mas cercana dentro de la puerta, de forma golosa
(la pareja mas corta primero), sin optimizar el conjunto de asignaciones en
global (eso seria un problema de asignacion optima, p.ej. el algoritmo
Hungaro) ni razonar sobre probabilidades de asociacion multiples. Con
puertas de distancia razonables y trazas suficientemente separadas -- el
caso tipico de los escenarios de este proyecto -- el resultado goloso
coincide con el optimo; el caso conocido donde puede no coincidir es el de
dos trazas que se cruzan muy cerca la una de la otra (ver limitacion
documentada en tracker.py).
"""

import math

from src.model import Detection, Position


def _distance_m(a: Position, b: Position) -> float:
    return math.sqrt((a.east_m - b.east_m) ** 2 + (a.north_m - b.north_m) ** 2 + (a.up_m - b.up_m) ** 2)


def associate(
    predicted_positions: dict[str, Position], detections: list[Detection], gate_distance_m: float
) -> tuple[dict[str, Detection], list[Detection]]:
    """Empareja detecciones con trazas por distancia minima, sin superar
    `gate_distance_m`. Devuelve (asignaciones track_id -> Detection, lista
    de detecciones que quedan sin asignar). Cada traza recibe como mucho
    una deteccion y cada deteccion se asigna como mucho a una traza."""
    candidates = []
    for track_id, position in predicted_positions.items():
        for detection in detections:
            distance = _distance_m(position, detection.position)
            if distance <= gate_distance_m:
                candidates.append((distance, track_id, detection))
    candidates.sort(key=lambda candidate: candidate[0])

    assignments: dict[str, Detection] = {}
    assigned_detection_ids: set[int] = set()

    for _distance, track_id, detection in candidates:
        if track_id in assignments or id(detection) in assigned_detection_ids:
            continue
        assignments[track_id] = detection
        assigned_detection_ids.add(id(detection))

    unassigned = [detection for detection in detections if id(detection) not in assigned_detection_ids]
    return assignments, unassigned
