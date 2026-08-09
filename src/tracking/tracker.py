"""
Tracker multi-objetivo: consume las detecciones ruidosas de
src/simulation/detections.py y mantiene un conjunto de trazas mediante
prediccion (filtro alpha-beta) + asociacion vecino-mas-cercano (GNN) +
confirmacion M-de-N.

El tracker nunca ve el track_id "verdadero" del escenario (los objetos
Detection no lo llevan): cada traza que produce tiene un id propio, inventado
aqui, exactamente como en un sistema real donde nadie le dice al tracker que
contacto es cual de antemano.

Limitacion conocida: cuando dos o mas sensores detectan la misma amenaza en
el mismo instante, la asociacion goloza (src/tracking/associator.py) solo
empareja la deteccion mas cercana a cada traza existente; la deteccion
sobrante de otro sensor, al no encontrar traza libre cerca, arranca una
traza "fantasma" nueva. Con `confirm_hits >= 2` estas trazas fantasma casi
nunca llegan a confirmarse (les faltan detecciones propias en los pasos
siguientes) y se descartan solas tras `drop_misses` fallos, pero aparecen
brevemente como TENTATIVE en el resultado. No se ha implementado fusion de
detecciones simultaneas de varios sensores para evitarlo -- queda
documentado como limitacion conocida, no resuelto de forma optima.
"""

import itertools
from collections import defaultdict

from src.model import Detection, Track, TrackState, TrackStatus, Velocity
from src.tracking.associator import associate
from src.tracking.filter import predict, update


class MultiTargetTracker:
    """`gate_distance_m` debe ser mayor que el ruido de sensor esperado
    (`noise_std_m` del escenario) para que las detecciones legitimas caigan
    dentro de la puerta, pero lo bastante pequeno para no confundir trazas
    distintas que pasen cerca. `confirm_hits`/`drop_misses` controlan la
    velocidad de confirmacion/descarte: valores mas altos son mas
    resistentes a detecciones espurias pero tardan mas en confirmar una
    amenaza real."""

    def __init__(
        self,
        gate_distance_m: float = 150.0,
        confirm_hits: int = 3,
        drop_misses: int = 3,
        alpha: float = 0.6,
        beta: float = 0.2,
    ) -> None:
        self.gate_distance_m = gate_distance_m
        self.confirm_hits = confirm_hits
        self.drop_misses = drop_misses
        self.alpha = alpha
        self.beta = beta
        self._tracks: dict[str, Track] = {}
        self._id_counter = itertools.count(1)

    def run(self, detections: list[Detection], timestamps: list[float] | None = None) -> list[Track]:
        """Procesa las detecciones instante a instante y devuelve todas las
        trazas generadas (incluidas las DROPPED, para poder inspeccionar el
        historial completo).

        `timestamps` deberia ser la linea temporal completa del escenario
        (p.ej. cada paso entre 0 y `scenario.duration_s`), no solo los
        instantes con alguna deteccion: el tracker avanza su propio reloj
        en cada instante de `timestamps` independientemente de si hay
        deteccion o no, que es lo que permite que una traza pase a
        COASTING/DROPPED cuando un sensor deja de verla. Si se omite, por
        comodidad en tests aislados, se usan los instantes que si tienen
        alguna deteccion -- pero entonces una traza sin ninguna deteccion
        propia en pasos posteriores nunca llega a decaer, porque el reloj
        del tracker no avanza sin al menos una deteccion de otra traza en
        ese instante."""
        by_timestamp: dict[float, list[Detection]] = defaultdict(list)
        for detection in detections:
            by_timestamp[detection.timestamp_s].append(detection)

        if timestamps is None:
            timestamps = sorted(by_timestamp)

        for timestamp_s in sorted(timestamps):
            self._step(timestamp_s, by_timestamp.get(timestamp_s, []))

        return list(self._tracks.values())

    def _step(self, timestamp_s: float, detections: list[Detection]) -> None:
        active_tracks = {
            track_id: track for track_id, track in self._tracks.items() if track.status != TrackStatus.DROPPED
        }

        predicted: dict[str, TrackState] = {}
        dts: dict[str, float] = {}
        for track_id, track in active_tracks.items():
            dt = timestamp_s - track.current_state.timestamp_s
            predicted[track_id] = predict(track.current_state, dt)
            dts[track_id] = dt

        predicted_positions = {track_id: state.position for track_id, state in predicted.items()}
        assignments, unassigned = associate(predicted_positions, detections, self.gate_distance_m)

        for track_id, predicted_state in predicted.items():
            track = active_tracks[track_id]
            detection = assignments.get(track_id)
            if detection is not None:
                new_state = update(predicted_state, detection.position, self.alpha, self.beta, dts[track_id])
                track.consecutive_hits += 1
                track.consecutive_misses = 0
                if track.status == TrackStatus.TENTATIVE:
                    if track.consecutive_hits >= self.confirm_hits:
                        track.status = TrackStatus.CONFIRMED
                elif track.status == TrackStatus.COASTING:
                    track.status = TrackStatus.CONFIRMED
            else:
                new_state = predicted_state
                track.consecutive_misses += 1
                track.consecutive_hits = 0
                if track.status == TrackStatus.CONFIRMED:
                    track.status = TrackStatus.COASTING
                if track.consecutive_misses >= self.drop_misses:
                    track.status = TrackStatus.DROPPED
            track.history.append(new_state)

        for detection in unassigned:
            self._spawn_track(detection)

    def _spawn_track(self, detection: Detection) -> None:
        """Una traza nueva arranca sin informacion de velocidad (una unica
        deteccion no basta para estimarla): el filtro la ira corrigiendo a
        partir de la segunda deteccion que se le asocie."""
        track_id = f"TRK-{next(self._id_counter):04d}"
        initial_state = TrackState(
            timestamp_s=detection.timestamp_s,
            position=detection.position,
            velocity=Velocity(east_mps=0.0, north_mps=0.0, up_mps=0.0),
        )
        status = TrackStatus.CONFIRMED if self.confirm_hits <= 1 else TrackStatus.TENTATIVE
        self._tracks[track_id] = Track(
            track_id=track_id,
            status=status,
            history=[initial_state],
            consecutive_hits=1,
            consecutive_misses=0,
        )
