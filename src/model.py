"""
Modelo de datos comun del pipeline.

Cada etapa (simulacion, seguimiento, clasificacion, puntuacion, decision)
lee y escribe estos tipos, asi que viven aqui en vez de en cualquiera de los
paquetes de una etapa concreta -- son el "vocabulario" compartido que hace
que ninguna etapa necesite conocer los detalles internos de la anterior.

Las posiciones y velocidades usan un sistema cartesiano local ENU
(este/norte/altura) en metros, relativo al origen del escenario. No son
coordenadas geograficas (lat/lon): lo que importa aqui es la proximidad a un
punto fijo (el activo protegido), no la localizacion absoluta en el globo.
"""

import math
from dataclasses import dataclass, field
from enum import StrEnum


class SensorType(StrEnum):
    """Modalidad de sensor que genero una deteccion. Se guarda para que el
    seguimiento pueda aplicar una puerta de asociacion (gating) distinta
    segun la precision tipica de cada modalidad."""

    RADAR = "radar"
    RF_DF = "rf_df"  # radiogoniometria del enlace de radiocontrol del dron
    EO_IR = "eo_ir"  # camara electro-optica/infrarroja


@dataclass(frozen=True)
class Position:
    """Coordenadas ENU en metros, relativas al origen del escenario.
    `up_m` es la altura sobre el plano de referencia del escenario, no sobre
    el nivel del mar."""

    east_m: float
    north_m: float
    up_m: float


@dataclass(frozen=True)
class Velocity:
    """Componentes de velocidad en el mismo sistema ENU, en m/s."""

    east_mps: float
    north_mps: float
    up_mps: float

    @property
    def speed_mps(self) -> float:
        return math.sqrt(self.east_mps**2 + self.north_mps**2 + self.up_mps**2)

    @property
    def heading_deg(self) -> float:
        """Rumbo sobre el plano horizontal en grados respecto al norte
        (0=N, 90=E, 180=S, 270=O). 0.0 por convencion cuando no hay
        componente horizontal de velocidad (p.ej. un dron en vuelo
        estacionario puramente vertical)."""
        if self.east_mps == 0.0 and self.north_mps == 0.0:
            return 0.0
        return math.degrees(math.atan2(self.east_mps, self.north_mps)) % 360.0


@dataclass(frozen=True)
class Detection:
    """Observacion cruda de un sensor en un instante concreto: lo que 've'
    un sensor, no lo que 'sabe' el sistema. No tiene identidad persistente
    entre instantes -- eso es responsabilidad del seguimiento (tracking),
    que asocia detecciones consecutivas para formar una traza."""

    sensor_id: str
    sensor_type: SensorType
    timestamp_s: float  # segundos desde el inicio del escenario
    position: Position


@dataclass(frozen=True)
class TrackState:
    """Estado filtrado de una traza en un instante concreto: la salida del
    filtro de seguimiento (posicion/velocidad suavizadas), no una medicion
    cruda de sensor."""

    timestamp_s: float
    position: Position
    velocity: Velocity


class TrackStatus(StrEnum):
    """Ciclo de vida de una traza en el tracker, segun la logica de
    confirmacion M-de-N: TENTATIVE hasta acumular suficientes hits
    consecutivos, COASTING mientras se predice sin medicion asociada, y
    DROPPED tras demasiadas perdidas consecutivas seguidas."""

    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    COASTING = "coasting"
    DROPPED = "dropped"


@dataclass
class Track:
    """Traza: identidad persistente de un contacto a lo largo del tiempo.
    `history` guarda el estado en cada instante (mas reciente al final)
    para poder razonar sobre el patron de vuelo completo -- p.ej.
    aproximacion directa sostenida frente a loitering -- no solo el punto
    actual. `consecutive_hits`/`consecutive_misses` son el contador que usa
    el tracker para las transiciones de `status`."""

    track_id: str
    status: TrackStatus
    history: list[TrackState] = field(default_factory=list)
    consecutive_hits: int = 0
    consecutive_misses: int = 0

    @property
    def current_state(self) -> TrackState:
        if not self.history:
            raise ValueError(f"la traza {self.track_id} todavia no tiene ningun estado en su historial")
        return self.history[-1]


class DroneClass(StrEnum):
    """Tipo de dron asignado por la clasificacion. Ver
    src/classification/kinematic_signature.py para las reglas concretas que
    llevan a cada valor."""

    COMMERCIAL = "commercial"
    FPV_ATTACK = "fpv_attack"
    ISR_FIXED_WING = "isr_fixed_wing"
    BIRD_CLUTTER = "bird_clutter"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Classification:
    """Clasificacion de tipo de dron para una traza. `rationale` es texto
    libre en español pensado para el informe: siempre debe explicar que
    caracteristica cinematica motivo el resultado, nunca ser una caja
    negra."""

    track_id: str
    drone_class: DroneClass
    confidence: float  # 0.0-1.0
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence debe estar en [0, 1], recibido {self.confidence}")


@dataclass(frozen=True)
class ProtectedAsset:
    """Activo a proteger: posicion fija + criticidad + anillos de
    proximidad concentricos. `ring_radii_m` mapea el nombre del anillo a su
    radio en metros, p.ej. {"vigilancia": 3000, "aviso": 1000, "critico": 300}."""

    asset_id: str
    position: Position
    criticality: int  # 1 (baja) - 5 (critica)
    ring_radii_m: dict[str, float]

    def __post_init__(self) -> None:
        if not 1 <= self.criticality <= 5:
            raise ValueError(f"criticality debe estar en [1, 5], recibido {self.criticality}")


class ThreatTier(StrEnum):
    """Nivel de prioridad derivado del score total, para agrupar en el
    informe y en el panel web sin tener que repetir umbrales en cada sitio
    que los consume."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ScoreComponent:
    """Sub-puntuacion de un aspecto concreto de la amenaza (cinematica,
    zona, clasificacion, comportamiento), con su propia justificacion. Es
    lo que hace que el score final sea auditable componente a componente
    en vez de un unico numero sin explicacion."""

    name: str
    value: float  # 0.0-100.0
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 100.0:
            raise ValueError(f"value debe estar en [0, 100], recibido {self.value}")


@dataclass(frozen=True)
class ThreatScore:
    """Puntuacion de amenaza de una traza respecto a un activo protegido
    concreto, con el desglose de componentes que la justifica."""

    track_id: str
    asset_id: str
    components: tuple[ScoreComponent, ...]
    total: float  # 0.0-100.0
    tier: ThreatTier

    def __post_init__(self) -> None:
        if not 0.0 <= self.total <= 100.0:
            raise ValueError(f"total debe estar en [0, 100], recibido {self.total}")
