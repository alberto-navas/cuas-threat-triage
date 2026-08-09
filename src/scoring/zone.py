"""
Puntuacion de amenaza por zona: en que anillo de proximidad del activo
protegido esta la traza ahora mismo.

Los anillos son bandas discretas (p.ej. "vigilancia" > "aviso" > "critico"),
no una escala continua: se puntua por banda, igual que en un sistema real
un operador ve "el contacto esta en zona de aviso", no "el contacto tiene
una puntuacion de zona de 63.4". `ring_radii_m` es un diccionario libre
(ver src.model.ProtectedAsset): este modulo no asume nombres concretos de
anillo, solo los ordena por radio.
"""

import math

from src.model import Position, ProtectedAsset, ScoreComponent, Track


def _distance_m(a: Position, b: Position) -> float:
    return math.sqrt((a.east_m - b.east_m) ** 2 + (a.north_m - b.north_m) ** 2 + (a.up_m - b.up_m) ** 2)


def _rings_by_radius(asset: ProtectedAsset) -> list[tuple[str, float]]:
    if not asset.ring_radii_m:
        raise ValueError(f"el activo '{asset.asset_id}' no tiene ningun anillo de proximidad definido")
    return sorted(asset.ring_radii_m.items(), key=lambda item: item[1])


def min_ring_radius_m(asset: ProtectedAsset) -> float:
    """Radio del anillo mas interior (el mas critico)."""
    return _rings_by_radius(asset)[0][1]


def max_ring_radius_m(asset: ProtectedAsset) -> float:
    """Radio del anillo mas exterior (el limite de vigilancia)."""
    return _rings_by_radius(asset)[-1][1]


def score_zone(track: Track, asset: ProtectedAsset) -> ScoreComponent:
    """100 dentro del anillo mas interior, decreciendo por banda hasta 0
    fuera de todos los anillos. Con N anillos, cada banda vale 100/N menos
    que la anterior -- una escala deliberadamente escalonada, no continua."""
    rings = _rings_by_radius(asset)
    distance = _distance_m(track.current_state.position, asset.position)
    num_rings = len(rings)

    for band_index, (ring_name, radius) in enumerate(rings):
        if distance <= radius:
            score = 100.0 * (num_rings - band_index) / num_rings
            return ScoreComponent(
                name="zona",
                value=score,
                rationale=(
                    f"A {distance:.0f} m de '{asset.asset_id}', dentro del anillo '{ring_name}' (radio {radius:.0f} m)."
                ),
                message_key="zone_inside_ring",
                message_params={
                    "asset_id": asset.asset_id,
                    "distance": distance,
                    "ring_name": ring_name,
                    "radius": radius,
                },
            )

    outer_name, outer_radius = rings[-1]
    return ScoreComponent(
        name="zona",
        value=0.0,
        rationale=(
            f"A {distance:.0f} m de '{asset.asset_id}', fuera de todos los anillos de proximidad "
            f"(el mas amplio, '{outer_name}', tiene {outer_radius:.0f} m de radio)."
        ),
        message_key="zone_outside_all_rings",
        message_params={
            "asset_id": asset.asset_id,
            "distance": distance,
            "outer_name": outer_name,
            "outer_radius": outer_radius,
        },
    )
