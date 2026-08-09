"""
Tests de la puntuacion por riesgo de clasificacion
(src/scoring/classification_risk.py).
"""

import pytest

from src.model import Classification, DroneClass
from src.scoring.classification_risk import score_classification_risk


def _classification(drone_class: DroneClass, confidence: float) -> Classification:
    return Classification(track_id="TRK-1", drone_class=drone_class, confidence=confidence, rationale="")


def test_high_confidence_fpv_attack_scores_near_max():
    result = score_classification_risk(_classification(DroneClass.FPV_ATTACK, confidence=0.95))

    assert result.value == pytest.approx(0.95 * 100.0 + 0.05 * 50.0)


def test_high_confidence_bird_clutter_scores_near_zero():
    result = score_classification_risk(_classification(DroneClass.BIRD_CLUTTER, confidence=0.95))

    assert result.value == pytest.approx(0.95 * 5.0 + 0.05 * 50.0)


def test_zero_confidence_scores_exactly_neutral_regardless_of_class():
    fpv_result = score_classification_risk(_classification(DroneClass.FPV_ATTACK, confidence=0.0))
    bird_result = score_classification_risk(_classification(DroneClass.BIRD_CLUTTER, confidence=0.0))

    assert fpv_result.value == pytest.approx(50.0)
    assert bird_result.value == pytest.approx(50.0)


def test_unknown_scores_neutral_regardless_of_confidence():
    low = score_classification_risk(_classification(DroneClass.UNKNOWN, confidence=0.2))
    high = score_classification_risk(_classification(DroneClass.UNKNOWN, confidence=0.9))

    assert low.value == pytest.approx(50.0)
    assert high.value == pytest.approx(50.0)


def test_low_confidence_pulls_score_toward_neutral():
    high_confidence = score_classification_risk(_classification(DroneClass.FPV_ATTACK, confidence=0.9))
    low_confidence = score_classification_risk(_classification(DroneClass.FPV_ATTACK, confidence=0.3))

    assert high_confidence.value > low_confidence.value
    assert low_confidence.value > 50.0  # sigue por encima del neutro: la clase base es de alto riesgo
