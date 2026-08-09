"""
Agregacion de los componentes de src/scoring/ (mas la criticidad del activo)
en una puntuacion de amenaza por (traza, activo), y el ranking de prioridad
global entre varias trazas y varios activos protegidos.

Los pesos son una suma ponderada explicita y documentada, no un modelo
aprendido: se puede leer directamente en el codigo por que un factor pesa
mas que otro, y ajustarlos no requiere reentrenar nada.

- **Cinematica (0.30)**: el peso mas alto. TCPA/DCPA es la senal mas
  directa de "esto va a llegar, y pronto" -- lo demas es contexto.
- **Clasificacion (0.25)**: que tipo de dron es cambia fundamentalmente la
  prioridad incluso con una cinematica parecida (un ave rondando el activo
  no es lo mismo que un FPV_ATTACK rondandolo).
- **Criticidad del activo (0.20)**: src.model.ProtectedAsset.criticality
  existe precisamente para esto -- una traza mediocre hacia el puesto de
  mando pesa mas que una identica hacia un deposito secundario. Se modela
  como un componente mas, visible y explicado en el desglose, en vez de
  como un multiplicador oculto aplicado solo al ordenar: todo lo que
  cambia la puntuacion final debe ser un ScoreComponent auditable.
- **Zona (0.15)**: la proximidad actual importa, pero esta correlacionada
  con el componente cinematico (DCPA ya mira distancia de aproximacion), asi
  que no se le da el mismo peso para no contar la distancia dos veces.
- **Comportamiento (0.10)**: el peso mas bajo -- es la senal mas ruidosa de
  las cinco (ventana corta de historial, sensible a maniobras recientes),
  util como corroboracion, no como base primaria de la decision.
"""

from dataclasses import dataclass

from src.classification.kinematic_signature import classify
from src.model import Classification, ProtectedAsset, ScoreComponent, ThreatScore, ThreatTier, Track, TrackStatus
from src.scoring.behavior import score_behavior
from src.scoring.classification_risk import score_classification_risk
from src.scoring.kinematics import score_kinematics
from src.scoring.zone import score_zone

_WEIGHT_KINEMATICS = 0.30
_WEIGHT_CLASSIFICATION = 0.25
_WEIGHT_ASSET_CRITICALITY = 0.20
_WEIGHT_ZONE = 0.15
_WEIGHT_BEHAVIOR = 0.10

_WEIGHTS_BY_COMPONENT = {
    "cinematica": _WEIGHT_KINEMATICS,
    "clasificacion": _WEIGHT_CLASSIFICATION,
    "criticidad_activo": _WEIGHT_ASSET_CRITICALITY,
    "zona": _WEIGHT_ZONE,
    "comportamiento": _WEIGHT_BEHAVIOR,
}

# Umbrales de la puntuacion total (0-100) que definen el nivel de prioridad.
# Igual que los anillos de zona, son bandas discretas pensadas para que un
# operador vea "CRITICO" o "ALTO", no un numero decimal que interpretar.
_CRITICAL_THRESHOLD = 80.0
_HIGH_THRESHOLD = 60.0
_MEDIUM_THRESHOLD = 35.0


def _tier_from_total(total: float) -> ThreatTier:
    if total >= _CRITICAL_THRESHOLD:
        return ThreatTier.CRITICAL
    if total >= _HIGH_THRESHOLD:
        return ThreatTier.HIGH
    if total >= _MEDIUM_THRESHOLD:
        return ThreatTier.MEDIUM
    return ThreatTier.LOW


def _score_asset_criticality(asset: ProtectedAsset) -> ScoreComponent:
    """Traduce la criticidad declarada del activo (entera, 1-5) a una
    escala 0-100 lineal, para que pese en la suma exactamente igual que
    cualquier otro componente."""
    value = (asset.criticality - 1) / 4.0 * 100.0
    return ScoreComponent(
        name="criticidad_activo",
        value=value,
        rationale=f"Activo '{asset.asset_id}' con criticidad declarada {asset.criticality}/5.",
        message_key="asset_criticality",
        message_params={"asset_id": asset.asset_id, "criticality": asset.criticality},
    )


def score_track_against_asset(track: Track, classification: Classification, asset: ProtectedAsset) -> ThreatScore:
    """Calcula la puntuacion de amenaza de una traza respecto a UN activo
    concreto, con los cinco componentes desglosados."""
    components: tuple[ScoreComponent, ...] = (
        score_kinematics(track, asset),
        score_zone(track, asset),
        score_classification_risk(classification),
        score_behavior(track, asset),
        _score_asset_criticality(asset),
    )
    total = sum(component.value * _WEIGHTS_BY_COMPONENT[component.name] for component in components)

    return ThreatScore(
        track_id=track.track_id,
        asset_id=asset.asset_id,
        components=components,
        total=total,
        tier=_tier_from_total(total),
    )


@dataclass(frozen=True)
class PriorityEntry:
    """Una linea del ranking de prioridad: la posicion (1 = mas urgente) y
    la puntuacion completa que la justifica."""

    rank: int
    score: ThreatScore


def _kinematics_value(score: ThreatScore) -> float:
    return next(component.value for component in score.components if component.name == "cinematica")


def prioritize(tracks: list[Track], assets: list[ProtectedAsset]) -> list[PriorityEntry]:
    """Clasifica y puntua cada traza activa, y devuelve el ranking global
    de mayor a menor amenaza.

    Las trazas DROPPED se excluyen: son contactos que el tracker ya perdio,
    y presentarlas en una cola de prioridad en vivo induciria a actuar
    sobre un contacto que ya no esta ahi. Para cada traza restante se
    calcula su puntuacion contra TODOS los activos y se conserva solo la
    del activo mas amenazado por esa traza -- el contexto que de verdad
    importa para decidir si esa traza es prioritaria. Los empates en la
    puntuacion total se resuelven por el sub-score cinematico (mas urgente
    primero), antes que por cualquier orden arbitrario de la lista de
    entrada.
    """
    if not assets:
        raise ValueError("prioritize() necesita al menos un activo protegido")

    best_scores = []
    for track in tracks:
        if track.status == TrackStatus.DROPPED:
            continue
        classification = classify(track)
        per_asset_scores = [score_track_against_asset(track, classification, asset) for asset in assets]
        best_scores.append(max(per_asset_scores, key=lambda score: score.total))

    ranked = sorted(best_scores, key=lambda score: (score.total, _kinematics_value(score)), reverse=True)

    return [PriorityEntry(rank=index + 1, score=score) for index, score in enumerate(ranked)]
