"""
Filtro alpha-beta (g-h) de velocidad constante.

Se elige sobre un filtro de Kalman completo porque no necesita mantener ni
razonar sobre una matriz de covarianza: dos constantes (alpha, beta) con un
significado directo -- cuanto se desplaza la posicion corregida hacia la
medicion nueva, cuanto se ajusta la velocidad a partir del mismo residuo --
bastan para un modelo de velocidad constante, y son mas faciles de
justificar y depurar que un Kalman completo en un proyecto donde la
explicabilidad es una prioridad de diseno.
"""

from src.model import Position, TrackState, Velocity


def predict(state: TrackState, dt: float) -> TrackState:
    """Propaga el estado `dt` segundos hacia delante asumiendo velocidad
    constante, sin ninguna medicion nueva."""
    if dt <= 0.0:
        raise ValueError(f"dt debe ser positivo, recibido {dt}")
    position = Position(
        east_m=state.position.east_m + state.velocity.east_mps * dt,
        north_m=state.position.north_m + state.velocity.north_mps * dt,
        up_m=state.position.up_m + state.velocity.up_mps * dt,
    )
    return TrackState(timestamp_s=state.timestamp_s + dt, position=position, velocity=state.velocity)


def update(predicted: TrackState, measured_position: Position, alpha: float, beta: float, dt: float) -> TrackState:
    """Corrige un estado predicho con una medicion nueva. `alpha` pesa
    cuanto se desplaza la posicion corregida hacia la medicion; `beta` pesa
    cuanto se ajusta la velocidad a partir del mismo residuo, repartido en
    el tiempo transcurrido `dt` desde el estado anterior."""
    if dt <= 0.0:
        raise ValueError(f"dt debe ser positivo, recibido {dt}")
    residual = Position(
        east_m=measured_position.east_m - predicted.position.east_m,
        north_m=measured_position.north_m - predicted.position.north_m,
        up_m=measured_position.up_m - predicted.position.up_m,
    )
    position = Position(
        east_m=predicted.position.east_m + alpha * residual.east_m,
        north_m=predicted.position.north_m + alpha * residual.north_m,
        up_m=predicted.position.up_m + alpha * residual.up_m,
    )
    velocity = Velocity(
        east_mps=predicted.velocity.east_mps + (beta / dt) * residual.east_m,
        north_mps=predicted.velocity.north_mps + (beta / dt) * residual.north_m,
        up_mps=predicted.velocity.up_mps + (beta / dt) * residual.up_m,
    )
    return TrackState(timestamp_s=predicted.timestamp_s, position=position, velocity=velocity)
