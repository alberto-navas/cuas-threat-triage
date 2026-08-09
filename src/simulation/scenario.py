"""
Definicion de un escenario simulado: activos protegidos, sensores de
deteccion y arquetipos de amenaza. Se carga desde un fichero YAML (ver
data/scenarios/*.yaml) para poder describir un caso de prueba sin tocar
codigo.

No existe ningun dataset publico de trazas C-UAS fusionadas -- es
informacion sensible en cualquier sistema operativo real. Todo el dato de
este proyecto es sintetico, generado a partir de estas definiciones.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from src.model import Position, ProtectedAsset, SensorType


class ThreatArchetype(StrEnum):
    """Patron de comportamiento cinematico que sigue una amenaza simulada.

    No es la clasificacion del pipeline (`src.model.DroneClass`): es la
    'verdad fundamental' con la que se genera la trayectoria en
    src/simulation/trajectories.py. La etapa de clasificacion nunca ve el
    arquetipo -- solo las detecciones ruidosas resultantes, igual que en un
    sistema real donde nadie le dice al clasificador que tipo de dron es."""

    FPV_ATTACK = "fpv_attack"  # aproximacion directa y sostenida hacia un activo
    ISR_LOITER = "isr_loiter"  # orbita a radio constante alrededor de un activo
    COMMERCIAL_WANDER = "commercial_wander"  # deriva erratica de baja velocidad, sin objetivo
    BIRD_CLUTTER = "bird_clutter"  # jitter de muy corto alcance, velocidad casi nula


@dataclass(frozen=True)
class SensorSpec:
    """Sensor simulado. En cada instante activo, con probabilidad
    `detection_probability`, produce una deteccion ruidosa de cada amenaza
    que este dentro de `max_range_m`. El ruido de posicion es gaussiano
    isotropico (misma desviacion en las 3 componentes) -- una
    simplificacion frente a la elipse de error real de un radar (que
    depende de rango/acimut), pero suficiente para ejercitar el
    seguimiento con datos no perfectos. Tampoco se modela enmascaramiento
    por terreno/linea de vision: el alcance es un corte duro en distancia."""

    sensor_id: str
    sensor_type: SensorType
    position: Position
    noise_std_m: float
    detection_probability: float  # 0.0-1.0
    max_range_m: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.detection_probability <= 1.0:
            raise ValueError(f"detection_probability debe estar en [0, 1], recibido {self.detection_probability}")


@dataclass(frozen=True)
class ThreatSpec:
    """Una amenaza a simular.

    `speed_mps` es la velocidad caracteristica del arquetipo (velocidad de
    aproximacion en FPV_ATTACK, velocidad tangencial en ISR_LOITER,
    velocidad maxima de deriva en COMMERCIAL_WANDER/BIRD_CLUTTER). Los
    demas campos son especificos de un subconjunto de arquetipos y quedan
    en None cuando no aplican; el generador de trayectorias
    (src/simulation/trajectories.py) valida que esten presentes para el
    arquetipo que los necesita y falla con un mensaje claro si falta
    alguno, en vez de tener una subclase distinta por arquetipo.
    """

    track_id: str
    archetype: ThreatArchetype
    spawn_time_s: float
    start_position: Position
    speed_mps: float
    target_asset_id: str | None = None  # FPV_ATTACK, ISR_LOITER
    loiter_radius_m: float | None = None  # ISR_LOITER
    heading_volatility_dps: float | None = None  # COMMERCIAL_WANDER


@dataclass(frozen=True)
class Scenario:
    """Escenario completo, listo para generar trayectorias y detecciones
    (src/simulation/trajectories.py, src/simulation/detections.py).
    `random_seed` fija toda la aleatoriedad del escenario (deriva de
    COMMERCIAL_WANDER/BIRD_CLUTTER y sorteos de deteccion/ruido de sensor),
    para que el mismo escenario produzca siempre el mismo resultado."""

    name: str
    description: str
    duration_s: float
    timestep_s: float
    random_seed: int
    assets: tuple[ProtectedAsset, ...]
    sensors: tuple[SensorSpec, ...]
    threats: tuple[ThreatSpec, ...]

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError(f"duration_s debe ser positivo, recibido {self.duration_s}")
        if self.timestep_s <= 0:
            raise ValueError(f"timestep_s debe ser positivo, recibido {self.timestep_s}")

        asset_ids = [asset.asset_id for asset in self.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("hay ids de activo duplicados en el escenario")

        track_ids = [threat.track_id for threat in self.threats]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("hay ids de traza duplicados en el escenario")

        asset_id_set = set(asset_ids)
        for threat in self.threats:
            if threat.target_asset_id is not None and threat.target_asset_id not in asset_id_set:
                raise ValueError(
                    f"la amenaza '{threat.track_id}' referencia el activo desconocido '{threat.target_asset_id}'"
                )

    def asset_by_id(self, asset_id: str) -> ProtectedAsset:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                return asset
        raise KeyError(f"el escenario no tiene ningun activo con id '{asset_id}'")


def _position_from_dict(raw: dict) -> Position:
    return Position(east_m=float(raw["east_m"]), north_m=float(raw["north_m"]), up_m=float(raw["up_m"]))


def _optional_float(value: float | int | str | None) -> float | None:
    return None if value is None else float(value)


def _parse_asset(raw: dict) -> ProtectedAsset:
    return ProtectedAsset(
        asset_id=raw["asset_id"],
        position=_position_from_dict(raw["position"]),
        criticality=int(raw["criticality"]),
        ring_radii_m={str(name): float(radius) for name, radius in raw.get("rings_m", {}).items()},
    )


def _parse_sensor(raw: dict) -> SensorSpec:
    return SensorSpec(
        sensor_id=raw["sensor_id"],
        sensor_type=SensorType(raw["sensor_type"]),
        position=_position_from_dict(raw["position"]),
        noise_std_m=float(raw["noise_std_m"]),
        detection_probability=float(raw["detection_probability"]),
        max_range_m=float(raw["max_range_m"]),
    )


def _parse_threat(raw: dict) -> ThreatSpec:
    return ThreatSpec(
        track_id=raw["track_id"],
        archetype=ThreatArchetype(raw["archetype"]),
        spawn_time_s=float(raw.get("spawn_time_s", 0.0)),
        start_position=_position_from_dict(raw["start_position"]),
        speed_mps=float(raw["speed_mps"]),
        target_asset_id=raw.get("target_asset_id"),
        loiter_radius_m=_optional_float(raw.get("loiter_radius_m")),
        heading_volatility_dps=_optional_float(raw.get("heading_volatility_dps")),
    )


def parse_scenario_yaml(text: str) -> Scenario:
    """Parsea y valida un escenario a partir de texto YAML ya en memoria
    (sin tocar disco) -- lo que permite validar un YAML subido por HTTP
    (src/web/app.py) sin necesidad de escribirlo primero a un fichero
    temporal. Las referencias cruzadas (p.ej. una amenaza que apunta a un
    activo inexistente) y las demas invariantes se comprueban en
    `Scenario.__post_init__`, asi que valen tanto para escenarios cargados
    desde YAML como construidos a mano en tests."""
    raw = yaml.safe_load(text)

    return Scenario(
        name=raw["name"],
        description=raw.get("description", ""),
        duration_s=float(raw["duration_s"]),
        timestep_s=float(raw["timestep_s"]),
        random_seed=int(raw.get("random_seed", 0)),
        assets=tuple(_parse_asset(a) for a in raw["assets"]),
        sensors=tuple(_parse_sensor(s) for s in raw["sensors"]),
        threats=tuple(_parse_threat(t) for t in raw["threats"]),
    )


def load_scenario(path: str | Path) -> Scenario:
    """Carga y valida un escenario desde un fichero YAML en disco."""
    return parse_scenario_yaml(Path(path).read_text(encoding="utf-8"))
