"""
Puntuacion de amenaza por cinematica: tiempo y distancia al punto de
maxima aproximacion (TCPA/DCPA) entre una traza y un activo protegido.

Es la misma matematica que usan la deteccion de colisiones en navegacion
maritima (COLREGS) y el control de trafico aereo: asumiendo que la traza
mantiene su velocidad actual y que el activo esta quieto, hay un unico
instante (pasado o futuro) en el que la distancia entre ambos es minima.
TCPA es cuando; DCPA es cuanto. Es una proyeccion lineal simple, no una
prediccion de intencion -- si la traza cambia de rumbo, deja de ser valida
y se recalcula en el siguiente instante con el nuevo estado.
"""

import math

from src.model import ProtectedAsset, ScoreComponent, Track, TrackState
from src.scoring.zone import max_ring_radius_m, min_ring_radius_m

# Por debajo de esta velocidad relativa, no hay suficiente movimiento para
# que TCPA/DCPA signifiquen nada (evita dividir por un numero casi nulo).
_MIN_CLOSING_SPEED_MPS = 0.1

# TCPA por debajo del cual la urgencia por tiempo es maxima, y por encima
# del cual (5 minutos) se considera que no hay urgencia temporal alguna.
_TCPA_URGENT_S = 30.0
_TCPA_NOT_URGENT_S = 300.0


def compute_cpa(track_state: TrackState, asset: ProtectedAsset) -> tuple[float | None, float]:
    """Devuelve (tcpa_s, dcpa_m) asumiendo velocidad constante de la traza
    y el activo inmovil. `tcpa_s` es `None` si la traza practicamente no se
    mueve respecto al activo (no hay aproximacion futura que calcular, y
    `dcpa_m` es entonces simplemente la distancia actual). Puede ser
    negativo: significa que el punto de maxima aproximacion ya quedo en el
    pasado -- la traza se esta alejando."""
    rel_east = track_state.position.east_m - asset.position.east_m
    rel_north = track_state.position.north_m - asset.position.north_m
    rel_up = track_state.position.up_m - asset.position.up_m

    vel = track_state.velocity
    speed_sq = vel.east_mps**2 + vel.north_mps**2 + vel.up_mps**2
    current_distance = math.sqrt(rel_east**2 + rel_north**2 + rel_up**2)

    if speed_sq < _MIN_CLOSING_SPEED_MPS**2:
        return None, current_distance

    tcpa_s = -(rel_east * vel.east_mps + rel_north * vel.north_mps + rel_up * vel.up_mps) / speed_sq

    closest_east = rel_east + vel.east_mps * tcpa_s
    closest_north = rel_north + vel.north_mps * tcpa_s
    closest_up = rel_up + vel.up_mps * tcpa_s
    dcpa_m = math.sqrt(closest_east**2 + closest_north**2 + closest_up**2)

    return tcpa_s, dcpa_m


def _urgency_from_tcpa(tcpa_s: float) -> float:
    if tcpa_s <= _TCPA_URGENT_S:
        return 100.0
    if tcpa_s >= _TCPA_NOT_URGENT_S:
        return 0.0
    return 100.0 * (_TCPA_NOT_URGENT_S - tcpa_s) / (_TCPA_NOT_URGENT_S - _TCPA_URGENT_S)


def _urgency_from_dcpa(dcpa_m: float, asset: ProtectedAsset) -> float:
    inner = min_ring_radius_m(asset)
    outer = max_ring_radius_m(asset)
    if dcpa_m <= inner:
        return 100.0
    if dcpa_m >= outer:
        return 0.0
    return 100.0 * (outer - dcpa_m) / (outer - inner)


def score_kinematics(track: Track, asset: ProtectedAsset) -> ScoreComponent:
    """El sub-score final es el MINIMO entre la urgencia por tiempo (TCPA)
    y por distancia (DCPA): una traza solo es cinematicamente urgente si va
    a pasar cerca Y eso va a ocurrir pronto -- una de las dos condiciones
    sin la otra no basta. Usar el minimo en vez de una media evita que una
    urgencia alta en un eje compense a una baja en el otro."""
    tcpa_s, dcpa_m = compute_cpa(track.current_state, asset)

    if tcpa_s is None:
        return ScoreComponent(
            name="cinematica",
            value=0.0,
            rationale=(
                f"Sin movimiento relativo significativo respecto a '{asset.asset_id}' "
                f"(a {dcpa_m:.0f} m): no hay dinamica de aproximacion que evaluar."
            ),
        )
    if tcpa_s <= 0.0:
        return ScoreComponent(
            name="cinematica",
            value=0.0,
            rationale=(
                f"Alejandose de '{asset.asset_id}': el punto de maxima aproximacion ya paso (hace {-tcpa_s:.0f} s)."
            ),
        )

    urgency_tcpa = _urgency_from_tcpa(tcpa_s)
    urgency_dcpa = _urgency_from_dcpa(dcpa_m, asset)
    score = min(urgency_tcpa, urgency_dcpa)

    return ScoreComponent(
        name="cinematica",
        value=score,
        rationale=(
            f"TCPA {tcpa_s:.0f} s, DCPA {dcpa_m:.0f} m respecto a '{asset.asset_id}' "
            f"(urgencia por tiempo {urgency_tcpa:.0f}/100, por distancia {urgency_dcpa:.0f}/100)."
        ),
    )
