"""
Tests de la asociacion vecino-mas-cercano con puerta de distancia
(src/tracking/associator.py).
"""

from src.model import Detection, SensorType
from src.tracking.associator import associate


def _detection(position_factory, east_m: float, north_m: float = 0.0) -> Detection:
    return Detection(
        sensor_id="s1",
        sensor_type=SensorType.RADAR,
        timestamp_s=1.0,
        position=position_factory(east_m=east_m, north_m=north_m),
    )


def test_associates_nearest_detection_within_gate(position_factory):
    predicted = {"trk1": position_factory(east_m=0.0)}
    detections = [_detection(position_factory, east_m=10.0)]

    assignments, unassigned = associate(predicted, detections, gate_distance_m=20.0)

    assert assignments == {"trk1": detections[0]}
    assert unassigned == []


def test_no_association_when_detection_outside_gate(position_factory):
    predicted = {"trk1": position_factory(east_m=0.0)}
    detections = [_detection(position_factory, east_m=100.0)]

    assignments, unassigned = associate(predicted, detections, gate_distance_m=20.0)

    assert assignments == {}
    assert unassigned == detections


def test_each_track_receives_at_most_one_detection(position_factory):
    predicted = {"trk1": position_factory(east_m=0.0)}
    close = _detection(position_factory, east_m=5.0)
    far = _detection(position_factory, east_m=15.0)

    assignments, unassigned = associate(predicted, [far, close], gate_distance_m=20.0)

    assert assignments == {"trk1": close}
    assert unassigned == [far]


def test_each_detection_assigned_to_at_most_one_track(position_factory):
    predicted = {
        "trk_near": position_factory(east_m=0.0),
        "trk_far": position_factory(east_m=3.0),
    }
    detection = _detection(position_factory, east_m=1.0)

    assignments, unassigned = associate(predicted, [detection], gate_distance_m=20.0)

    assert assignments == {"trk_near": detection}
    assert "trk_far" not in assignments
    assert unassigned == []


def test_no_predicted_tracks_leaves_all_detections_unassigned(position_factory):
    detections = [_detection(position_factory, east_m=1.0), _detection(position_factory, east_m=2.0)]

    assignments, unassigned = associate({}, detections, gate_distance_m=20.0)

    assert assignments == {}
    assert unassigned == detections
