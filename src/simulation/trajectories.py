"""
Generador de trayectorias "verdad fundamental" (ground truth) para cada
arquetipo de amenaza de un escenario.

Importante: nada aguas abajo de este modulo (seguimiento, clasificacion,
puntuacion) debe importarlo ni conocer el arquetipo de una amenaza. Estas
funciones existen solo para producir la trayectoria real que
src/simulation/detections.py convierte en detecciones ruidosas -- el resto
del pipeline razona exclusivamente sobre esas detecciones, igual que un
sistema C-UAS real no conoce de antemano que es cada contacto.
"""

import math
import random

from src.model import Position, TrackState, Velocity
from src.simulation.scenario import Scenario, ThreatArchetype, ThreatSpec


def build_ground_truth(spec: ThreatSpec, scenario: Scenario, rng: random.Random) -> list[TrackState]:
    """Genera la secuencia completa de estados verdaderos de una amenaza,
    desde su instante de aparicion (`spec.spawn_time_s`) hasta el final del
    escenario, con paso `scenario.timestep_s`. La amenaza permanece activa
    hasta el final del escenario (no desaparece antes) -- una
    simplificacion deliberada; escenarios que quieran que una amenaza
    "termine" antes deben ajustar `duration_s`."""
    if spec.archetype == ThreatArchetype.FPV_ATTACK:
        return _build_fpv_attack(spec, scenario)
    if spec.archetype == ThreatArchetype.ISR_LOITER:
        return _build_isr_loiter(spec, scenario)
    if spec.archetype == ThreatArchetype.COMMERCIAL_WANDER:
        return _build_commercial_wander(spec, scenario, rng)
    if spec.archetype == ThreatArchetype.BIRD_CLUTTER:
        return _build_bird_clutter(spec, scenario, rng)
    raise ValueError(f"arquetipo sin generador de trayectoria: {spec.archetype}")  # pragma: no cover


def _timestamps(spec: ThreatSpec, scenario: Scenario) -> list[float]:
    timestamps = []
    t = spec.spawn_time_s
    while t <= scenario.duration_s:
        timestamps.append(t)
        t += scenario.timestep_s
    return timestamps


def _require(spec: ThreatSpec, field_name: str, value: float | str | None) -> float | str:
    if value is None:
        raise ValueError(f"la amenaza '{spec.track_id}' ({spec.archetype}) necesita el campo '{field_name}'")
    return value


def _target_position(spec: ThreatSpec, scenario: Scenario) -> Position:
    asset_id = _require(spec, "target_asset_id", spec.target_asset_id)
    return scenario.asset_by_id(str(asset_id)).position


def _build_fpv_attack(spec: ThreatSpec, scenario: Scenario) -> list[TrackState]:
    """Linea recta a velocidad constante desde `start_position` hacia el
    activo objetivo, sin correccion de rumbo posterior: una aproximacion
    directa "de manual", que es precisamente la firma que se quiere poder
    distinguir de un loitering o de una deriva erratica en la
    clasificacion. La altitud se mantiene constante durante todo el
    trayecto (no se modela descenso hacia el impacto)."""
    target = _target_position(spec, scenario)
    dx = target.east_m - spec.start_position.east_m
    dy = target.north_m - spec.start_position.north_m
    horizontal_distance = math.hypot(dx, dy)
    direction = (dx / horizontal_distance, dy / horizontal_distance) if horizontal_distance > 0.0 else (0.0, 0.0)
    velocity = Velocity(east_mps=direction[0] * spec.speed_mps, north_mps=direction[1] * spec.speed_mps, up_mps=0.0)

    states = []
    for t in _timestamps(spec, scenario):
        elapsed = t - spec.spawn_time_s
        position = Position(
            east_m=spec.start_position.east_m + velocity.east_mps * elapsed,
            north_m=spec.start_position.north_m + velocity.north_mps * elapsed,
            up_m=spec.start_position.up_m,
        )
        states.append(TrackState(timestamp_s=t, position=position, velocity=velocity))
    return states


def _build_isr_loiter(spec: ThreatSpec, scenario: Scenario) -> list[TrackState]:
    """Orbita circular de radio constante alrededor del activo objetivo, a
    velocidad tangencial constante. El angulo se calcula de forma analitica
    a partir del tiempo transcurrido (no por integracion paso a paso), para
    que el radio no derive con el tiempo por acumulacion de error
    numerico."""
    target = _target_position(spec, scenario)
    radius = float(_require(spec, "loiter_radius_m", spec.loiter_radius_m))
    if radius <= 0.0:
        raise ValueError(f"loiter_radius_m debe ser positivo, recibido {radius} en '{spec.track_id}'")

    initial_angle = math.atan2(spec.start_position.north_m - target.north_m, spec.start_position.east_m - target.east_m)
    angular_rate = spec.speed_mps / radius  # rad/s

    states = []
    for t in _timestamps(spec, scenario):
        elapsed = t - spec.spawn_time_s
        angle = initial_angle + angular_rate * elapsed
        position = Position(
            east_m=target.east_m + radius * math.cos(angle),
            north_m=target.north_m + radius * math.sin(angle),
            up_m=spec.start_position.up_m,
        )
        # Velocidad tangencial: derivada de la posicion respecto al angulo, por la velocidad angular.
        velocity = Velocity(
            east_mps=-radius * angular_rate * math.sin(angle),
            north_mps=radius * angular_rate * math.cos(angle),
            up_mps=0.0,
        )
        states.append(TrackState(timestamp_s=t, position=position, velocity=velocity))
    return states


def _build_commercial_wander(spec: ThreatSpec, scenario: Scenario, rng: random.Random) -> list[TrackState]:
    """Paseo aleatorio en rumbo: en cada paso el rumbo cambia una cantidad
    gaussiana de desviacion tipica `heading_volatility_dps * timestep_s`
    (aproximacion simple, no un proceso de difusion fisicamente riguroso) y
    la velocidad es constante a `speed_mps`. No apunta a ningun activo:
    representa un dron recreativo sin intencion hostil."""
    volatility = float(_require(spec, "heading_volatility_dps", spec.heading_volatility_dps))
    heading_deg = rng.uniform(0.0, 360.0)
    position = spec.start_position

    states = []
    for t in _timestamps(spec, scenario):
        heading_deg = (heading_deg + rng.gauss(0.0, volatility * scenario.timestep_s)) % 360.0
        heading_rad = math.radians(heading_deg)
        velocity = Velocity(
            east_mps=spec.speed_mps * math.sin(heading_rad),
            north_mps=spec.speed_mps * math.cos(heading_rad),
            up_mps=0.0,
        )
        states.append(TrackState(timestamp_s=t, position=position, velocity=velocity))
        position = Position(
            east_m=position.east_m + velocity.east_mps * scenario.timestep_s,
            north_m=position.north_m + velocity.north_mps * scenario.timestep_s,
            up_m=position.up_m,
        )
    return states


def _build_bird_clutter(spec: ThreatSpec, scenario: Scenario, rng: random.Random) -> list[TrackState]:
    """Jitter de corto alcance alrededor de `start_position`: un ave o un
    falso positivo de clutter no se desplaza de forma sostenida, solo
    fluctua. Se modela como un paseo aleatorio en posicion (no en rumbo),
    con un paso maximo de `speed_mps * timestep_s` en cada eje
    horizontal."""
    position = spec.start_position
    step = spec.speed_mps * scenario.timestep_s

    states = []
    for t in _timestamps(spec, scenario):
        east_delta = rng.uniform(-step, step)
        north_delta = rng.uniform(-step, step)
        velocity = Velocity(
            east_mps=east_delta / scenario.timestep_s, north_mps=north_delta / scenario.timestep_s, up_mps=0.0
        )
        position = Position(
            east_m=position.east_m + east_delta, north_m=position.north_m + north_delta, up_m=position.up_m
        )
        states.append(TrackState(timestamp_s=t, position=position, velocity=velocity))
    return states
