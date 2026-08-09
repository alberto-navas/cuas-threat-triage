"""
Mapa tactico del escenario: activos protegidos con sus anillos de
proximidad y las trayectorias de las trazas, coloreadas por nivel de
amenaza. Coordenadas ENU locales (metros), no geograficas -- ver el
modulo docstring de src/model.py -- asi que es un grafico de dispersion
con ejes en metros y aspecto 1:1, no un mapa de calles.
"""

import math

import plotly.graph_objects as go

from src.decision.prioritizer import PriorityEntry
from src.model import ProtectedAsset, ThreatTier, Track, TrackStatus

_TIER_COLORS: dict[ThreatTier, str] = {
    ThreatTier.CRITICAL: "#d32f2f",
    ThreatTier.HIGH: "#f57c00",
    ThreatTier.MEDIUM: "#fbc02d",
    ThreatTier.LOW: "#388e3c",
}
_UNSCORED_COLOR = "#9e9e9e"  # trazas sin entrada en el ranking (p.ej. DROPPED tempranas)

_RING_POINTS = 64


def _circle_xy(center_east_m: float, center_north_m: float, radius_m: float) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for i in range(_RING_POINTS + 1):
        angle = 2.0 * math.pi * i / _RING_POINTS
        xs.append(center_east_m + radius_m * math.cos(angle))
        ys.append(center_north_m + radius_m * math.sin(angle))
    return xs, ys


def _add_asset(fig: go.Figure, asset: ProtectedAsset) -> None:
    for ring_name, radius_m in sorted(asset.ring_radii_m.items(), key=lambda item: item[1]):
        xs, ys = _circle_xy(asset.position.east_m, asset.position.north_m, radius_m)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line={"color": "#616161", "dash": "dot", "width": 1},
                name=f"{asset.asset_id} · {ring_name} ({radius_m:.0f} m)",
                hoverinfo="name",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[asset.position.east_m],
            y=[asset.position.north_m],
            mode="markers+text",
            marker={"symbol": "square", "size": 14, "color": "#212121"},
            text=[asset.asset_id],
            textposition="bottom center",
            name=asset.asset_id,
            hovertemplate=f"Activo: {asset.asset_id}<br>Criticidad: {asset.criticality}/5<extra></extra>",
        )
    )


def _add_track(fig: go.Figure, track: Track, tier: ThreatTier | None) -> None:
    xs = [state.position.east_m for state in track.history]
    ys = [state.position.north_m for state in track.history]
    color = _TIER_COLORS.get(tier) if tier is not None else _UNSCORED_COLOR
    label = f"{track.track_id} ({tier.value.upper()})" if tier is not None else f"{track.track_id} (sin puntuar)"

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines+markers",
            line={"color": color, "width": 2},
            marker={"size": 4, "color": color},
            name=label,
            hovertemplate=f"{track.track_id}<br>este=%{{x:.0f}} m<br>norte=%{{y:.0f}} m<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[xs[-1]],
            y=[ys[-1]],
            mode="markers",
            marker={"size": 10, "color": color, "symbol": "triangle-up"},
            showlegend=False,
            hoverinfo="skip",
        )
    )


def build_tactical_map_html(assets: list[ProtectedAsset], tracks: list[Track], priority: list[PriorityEntry]) -> str:
    """Devuelve el `<div>` HTML del mapa (plotly con JS incrustado, sin
    dependencias externas), listo para insertar en la plantilla del
    informe."""
    tier_by_track_id = {entry.score.track_id: entry.score.tier for entry in priority}

    fig = go.Figure()
    for asset in assets:
        _add_asset(fig, asset)
    for track in tracks:
        if not track.history:
            continue
        if track.status == TrackStatus.DROPPED and track.track_id not in tier_by_track_id:
            continue  # trazas fantasma efimeras (ver src/tracking/tracker.py): ruido visual, no aportan
        _add_track(fig, track, tier_by_track_id.get(track.track_id))

    fig.update_layout(
        xaxis_title="Este (m)",
        yaxis_title="Norte (m)",
        yaxis={"scaleanchor": "x", "scaleratio": 1},
        template="plotly_white",
        height=650,
        margin={"l": 40, "r": 20, "t": 20, "b": 40},
        legend={"orientation": "v"},
    )
    return fig.to_html(include_plotlyjs="inline", full_html=False, config={"displaylogo": False})
