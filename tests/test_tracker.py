"""
Tests del tracker multi-objetivo (src/tracking/tracker.py): confirmacion
M-de-N, decaimiento a COASTING/DROPPED, recuperacion tras un fallo, y
aparicion de trazas nuevas a partir de detecciones sin asociar.
"""

from src.model import Detection, SensorType, TrackStatus
from src.simulation.detections import simulate_detections
from src.simulation.scenario import load_scenario
from src.tracking.tracker import MultiTargetTracker


def _detection(position_factory, timestamp_s: float, east_m: float, north_m: float = 0.0) -> Detection:
    return Detection(
        sensor_id="s1",
        sensor_type=SensorType.RADAR,
        timestamp_s=timestamp_s,
        position=position_factory(east_m=east_m, north_m=north_m),
    )


def test_static_target_confirmed_after_m_consecutive_hits(position_factory):
    detections = [_detection(position_factory, t, east_m=100.0) for t in range(5)]
    tracker = MultiTargetTracker(gate_distance_m=10.0, confirm_hits=3, drop_misses=3)

    tracks = tracker.run(detections)

    assert len(tracks) == 1
    track = tracks[0]
    assert track.status == TrackStatus.CONFIRMED
    assert len(track.history) == 5
    # A la primera deteccion (t=0) la traza nace: hits=1,2,3 en t=0,1,2 -> confirmada en t=2.
    assert track.history[2].timestamp_s == 2.0


def test_track_status_is_tentative_before_reaching_confirm_hits(position_factory):
    detections = [_detection(position_factory, t, east_m=100.0) for t in range(2)]
    tracker = MultiTargetTracker(gate_distance_m=10.0, confirm_hits=3, drop_misses=3)

    tracks = tracker.run(detections)

    assert tracks[0].status == TrackStatus.TENTATIVE


def test_track_drops_after_n_consecutive_misses(position_factory):
    detections = [_detection(position_factory, t, east_m=100.0) for t in range(3)]
    tracker = MultiTargetTracker(gate_distance_m=10.0, confirm_hits=2, drop_misses=2)

    # Pasa la linea temporal completa (0..5) aunque no haya deteccion en t=3,4,5,
    # para que el reloj del tracker avance y la traza pueda decaer.
    tracks = tracker.run(detections, timestamps=list(range(6)))

    assert len(tracks) == 1
    track = tracks[0]
    assert track.status == TrackStatus.DROPPED
    # t=0,1,2 con deteccion; t=3 primer fallo (COASTING); t=4 segundo fallo -> DROPPED.
    assert len(track.history) == 5


def test_track_recovers_to_confirmed_after_coasting(position_factory):
    detections = [
        _detection(position_factory, 0, east_m=100.0),
        _detection(position_factory, 1, east_m=100.0),
        # t=2: sin deteccion -> COASTING
        _detection(position_factory, 3, east_m=100.0),
    ]
    tracker = MultiTargetTracker(gate_distance_m=10.0, confirm_hits=2, drop_misses=3)

    tracks = tracker.run(detections, timestamps=[0, 1, 2, 3])

    assert len(tracks) == 1
    track = tracks[0]
    assert track.status == TrackStatus.CONFIRMED
    assert track.history[2].timestamp_s == 2.0  # el paso de COASTING sigue en el historial


def test_unassociated_detection_spawns_new_track(position_factory):
    detections = [
        _detection(position_factory, 0, east_m=0.0),
        _detection(position_factory, 1, east_m=0.0),  # confirma la primera traza
        _detection(position_factory, 1, east_m=5000.0),  # muy lejos: no puede ser la misma traza
    ]
    tracker = MultiTargetTracker(gate_distance_m=50.0, confirm_hits=5, drop_misses=5)

    tracks = tracker.run(detections)

    assert len(tracks) == 2
    assert {track.track_id for track in tracks} == {"TRK-0001", "TRK-0002"}


def test_end_to_end_single_threat_scenario_produces_one_confirmed_track(fixtures_dir):
    """Integracion con src/simulation: el escenario minimo tiene deteccion
    garantizada (probabilidad 1.0) y sin ruido en cada uno de sus 6
    instantes, asi que debe converger en una unica traza confirmada."""
    scenario = load_scenario(fixtures_dir / "minimal_scenario.yaml")
    detections = simulate_detections(scenario)
    tracker = MultiTargetTracker(gate_distance_m=50.0, confirm_hits=3, drop_misses=3)

    timestamps = [scenario.timestep_s * i for i in range(int(scenario.duration_s / scenario.timestep_s) + 1)]
    tracks = tracker.run(detections, timestamps=timestamps)

    assert len(tracks) == 1
    assert tracks[0].status == TrackStatus.CONFIRMED
