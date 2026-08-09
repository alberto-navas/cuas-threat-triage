"""
Puntuacion de amenaza por comportamiento: cuanto apunta la traza, de forma
sostenida, hacia el activo protegido en concreto.

Complementa al componente cinematico (src/scoring/kinematics.py), no lo
duplica: TCPA/DCPA es una proyeccion fisica a partir del estado ACTUAL
asumiendo velocidad constante, mientras que este componente mira el
historial reciente para distinguir una alineacion sostenida y deliberada
de una alineacion momentanea. Tambien es el unico componente que distingue,
para una traza en linea recta hacia algun sitio (la clasificacion por
firma cinematica no sabe nada de activos, ver
src/classification/kinematic_signature.py), si ese sitio es EL activo que
se esta evaluando o alguno distinto -- relevante en escenarios
multi-activo, donde una traza "con pinta de ataque" puede simplemente
dirigirse a otro objetivo.
"""

import math

from src.model import Position, ProtectedAsset, ScoreComponent, Track

# Puntos mas recientes del historial usados para la alineacion. Una ventana
# corta, no todo el historial: interesa el comportamiento reciente, no
# diluirlo con como se comportaba la traza hace varios minutos.
_ALIGNMENT_WINDOW = 10

# Igual que en src/classification/kinematic_signature.py: por debajo de
# esta velocidad, el rumbo no es fiable (ver la convencion de
# src.model.Velocity.heading_deg).
_MIN_SPEED_FOR_BEARING_MPS = 0.5


def _bearing_deg(from_position: Position, to_position: Position) -> float:
    """Rumbo desde `from_position` hacia `to_position`, en grados respecto
    al norte (0=N, 90=E), sobre el plano horizontal."""
    dx = to_position.east_m - from_position.east_m
    dy = to_position.north_m - from_position.north_m
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _angle_diff_deg(a_deg: float, b_deg: float) -> float:
    """Diferencia angular absoluta minima entre dos rumbos, en [0, 180]."""
    return abs((a_deg - b_deg + 180.0) % 360.0 - 180.0)


def score_behavior(track: Track, asset: ProtectedAsset) -> ScoreComponent:
    """100 si el rumbo ha apuntado en promedio directamente al activo en
    la ventana reciente, 0 si ha apuntado en promedio directamente en
    direccion opuesta, escala lineal entre medias -- p.ej. una orbita
    (rumbo tangencial, ~90 grados de desalineacion) puntua alrededor de 50:
    ni acercandose ni alejandose de forma neta."""
    recent = [
        state for state in track.history[-_ALIGNMENT_WINDOW:] if state.velocity.speed_mps >= _MIN_SPEED_FOR_BEARING_MPS
    ]
    if not recent:
        return ScoreComponent(
            name="comportamiento",
            value=0.0,
            rationale="Sin velocidad significativa reciente: no hay rumbo del que evaluar la alineacion con el activo.",
        )

    misalignments_deg = [
        _angle_diff_deg(state.velocity.heading_deg, _bearing_deg(state.position, asset.position)) for state in recent
    ]
    mean_misalignment_deg = sum(misalignments_deg) / len(misalignments_deg)
    score = max(0.0, 100.0 * (1.0 - mean_misalignment_deg / 180.0))

    return ScoreComponent(
        name="comportamiento",
        value=score,
        rationale=(
            f"Desalineacion media de {mean_misalignment_deg:.0f} grados entre el rumbo y el activo "
            f"'{asset.asset_id}' en los ultimos {len(recent)} puntos "
            "(0 grados = apuntando directamente, 180 = alejandose en linea recta)."
        ),
    )
