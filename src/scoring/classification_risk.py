"""
Puntuacion de amenaza por clasificacion: cuanto riesgo implica el tipo de
dron asignado por src/classification/kinematic_signature.py, ponderado por
la confianza de esa clasificacion.

Una clasificacion de baja confianza no debe empujar el score hacia el
extremo de su clase (ni hacia 100 ni hacia 0): se pondera hacia un valor
neutro de precaucion en proporcion a la incertidumbre, para no tratar una
conjetura poco fiable como si fuera una certeza.
"""

from src.model import Classification, DroneClass, ScoreComponent

# Riesgo base por tipo, en ausencia total de incertidumbre. UNKNOWN vale
# expresamente lo mismo que _NEUTRAL_RISK (precaucion media, ni alarma ni
# descarte) porque "no se pudo clasificar" no es evidencia de nada en
# ninguna direccion.
_BASE_RISK_BY_CLASS: dict[DroneClass, float] = {
    DroneClass.FPV_ATTACK: 100.0,
    DroneClass.ISR_FIXED_WING: 60.0,
    DroneClass.COMMERCIAL: 25.0,
    DroneClass.BIRD_CLUTTER: 5.0,
    DroneClass.UNKNOWN: 50.0,
}

_NEUTRAL_RISK = 50.0


def score_classification_risk(classification: Classification) -> ScoreComponent:
    base_risk = _BASE_RISK_BY_CLASS[classification.drone_class]
    weighted = classification.confidence * base_risk + (1.0 - classification.confidence) * _NEUTRAL_RISK

    return ScoreComponent(
        name="clasificacion",
        value=weighted,
        rationale=(
            f"Clasificada como {classification.drone_class.value} con confianza "
            f"{classification.confidence:.0%} (riesgo base {base_risk:.0f}/100 para ese tipo); "
            f"ponderado hacia el valor neutro ({_NEUTRAL_RISK:.0f}/100) en proporcion "
            "a la incertidumbre de la clasificacion."
        ),
    )
