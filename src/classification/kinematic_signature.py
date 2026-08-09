"""
Clasificacion de tipo de dron por firma cinematica.

La traza (src.model.Track) nunca lleva ninguna pista sobre el arquetipo que
la genero (ver src/simulation/trajectories.py): solo se dispone de la
posicion/velocidad que el tracker fue filtrando en cada instante, igual que
en un sistema real donde nadie le dice al clasificador que contacto es cual
de antemano. Este modulo deriva unas pocas caracteristicas simples de esa
serie -- velocidad media, ritmo de giro medio y su consistencia -- y aplica
un arbol de reglas explicito y documentado, nunca una caja negra de ML,
para que cada resultado pueda justificarse con las cifras concretas que lo
motivaron.
"""

import math
from dataclasses import dataclass

from src.model import Classification, DroneClass, Track

# --- Umbrales --------------------------------------------------------------
# Constantes expuestas (no hardcodeadas en la logica) para documentar en un
# solo sitio de donde sale cada una y poder ajustarlas sin tocar el arbol de
# reglas.

# Puntos minimos en el historial para fiarse de la firma cinematica. Con
# menos no hay suficientes pares consecutivos para que el ritmo de giro
# signifique nada.
_MIN_SAMPLES_FOR_CLASSIFICATION = 3

# Velocidad de sensor por debajo de la cual src.model.Velocity.heading_deg
# no es fiable (por convencion, sin componente horizontal devuelve 0.0).
# Excluir estos pares evita ritmos de giro espurios, sobre todo justo al
# nacer una traza, cuando su velocidad inicial estimada es (0, 0, 0).
_MIN_SPEED_FOR_HEADING_MPS = 0.5

# Velocidad media por debajo de la cual se considera clutter/ave, sin mirar
# el resto de caracteristicas: ni un ataque FPV ni una orbita ISR vuelan tan
# despacio de forma sostenida.
_BIRD_MAX_SPEED_MPS = 3.0

# Desviacion tipica del ritmo de giro a partir de la cual se considera
# "erratico" (deriva sin objetivo) en vez de "consistente" (linea recta u
# orbita de radio constante). Calibrado empiricamente ejecutando el pipeline
# completo (simulacion -> tracking -> clasificacion) sobre los escenarios de
# demo: incluso con una trayectoria real perfectamente recta u orbital, el
# ruido del sensor (`noise_std_m` en src/simulation/scenario.py) se cuela en
# la velocidad filtrada y deja un ritmo de giro residual de varios
# grados/s, bastante mayor que el ruido teorico "de manual" que cabria
# esperar de un filtro alpha-beta sobre una señal limpia. El umbral se puso
# por encima de ese ruido residual observado (tipicamente < 5 deg/s en los
# escenarios de demo) y por debajo del ritmo de un paseo aleatorio real
# (heading_volatility_dps en escena suele ser >= 20 grados/paso, y el ritmo
# de giro resultante tras el tracker se mantiene bien por encima de 10 deg/s).
_ERRATIC_TURN_RATE_STD_THRESHOLD_DPS = 8.0

# Ritmo de giro medio por debajo del cual, dentro del grupo "consistente",
# se considera una aproximacion en linea recta en vez de una orbita
# sostenida. Igual que el umbral anterior, calibrado para quedar por encima
# del ruido residual de una linea recta filtrada (tipicamente < 2 deg/s) y
# por debajo del ritmo de giro real de la orbita de reconocimiento de los
# escenarios de demo. Una orbita muy ancha y lenta puede parecer
# indistinguible de una linea recta en una ventana de observacion corta;
# ver la limitacion documentada en classify().
_ATTACK_MAX_MEAN_TURN_RATE_DPS = 3.0

# Velocidad media minima para llamar "aproximacion directa" (FPV_ATTACK) a
# una traza recta y consistente. Sin este suelo, un objetivo lento y recto
# (p.ej. un mismo dron volando muy despacio en linea recta un instante)
# tambien encajaria en la regla de FPV_ATTACK solo por ser recta -- se
# prefiere no clasificarlo en vez de forzar una etiqueta hostil sin
# suficiente evidencia de velocidad.
_ATTACK_MIN_SPEED_MPS = 15.0

# Puntos iniciales de una traza que se descartan antes de calcular la firma
# cinematica. Un track recien nacido arranca con velocidad (0, 0, 0) como
# suposicion inicial (ver src/tracking/tracker.py:_spawn_track), asi que las
# primeras correcciones del filtro alpha-beta son un salto grande desde ese
# cero hacia la velocidad real -- un transitorio de convergencia, no una
# maniobra del objetivo. Sin descartarlo, ese unico salto (potencialmente de
# mas de 100 grados) domina la media y la desviacion del ritmo de giro de
# toda la traza. Solo se descarta si sobran suficientes puntos despues
# (ver compute_kinematic_signature): una traza recien confirmada, con poco
# historial, se clasifica igualmente con lo que haya, con menos confianza.
_WARMUP_SAMPLES_TO_SKIP = 5


@dataclass(frozen=True)
class KinematicSignature:
    """Caracteristicas cinematicas resumidas del historial de una traza,
    usadas como entrada al arbol de reglas de `classify()`."""

    num_samples: int
    avg_speed_mps: float
    mean_turn_rate_dps: float
    turn_rate_std_dps: float


def _heading_delta_deg(from_heading_deg: float, to_heading_deg: float) -> float:
    """Diferencia angular con signo, en (-180, 180], de pasar de un rumbo a
    otro -- para no confundir un giro de 10 grados que cruza el limite
    0/360 con uno de 350 grados."""
    return (to_heading_deg - from_heading_deg + 180.0) % 360.0 - 180.0


def compute_kinematic_signature(track: Track) -> KinematicSignature:
    """Resume el historial de la traza (sin el transitorio inicial del
    filtro, ver `_WARMUP_SAMPLES_TO_SKIP`) en las pocas caracteristicas que
    usa `classify()`."""
    history = track.history
    if len(history) > _WARMUP_SAMPLES_TO_SKIP + _MIN_SAMPLES_FOR_CLASSIFICATION:
        history = history[_WARMUP_SAMPLES_TO_SKIP:]
    num_samples = len(history)
    if num_samples == 0:
        return KinematicSignature(num_samples=0, avg_speed_mps=0.0, mean_turn_rate_dps=0.0, turn_rate_std_dps=0.0)

    avg_speed_mps = sum(state.velocity.speed_mps for state in history) / num_samples

    turn_rates_dps = []
    for previous, current in zip(history, history[1:], strict=False):
        dt = current.timestamp_s - previous.timestamp_s
        if previous.velocity.speed_mps < _MIN_SPEED_FOR_HEADING_MPS:
            continue
        if current.velocity.speed_mps < _MIN_SPEED_FOR_HEADING_MPS:
            continue
        delta_deg = _heading_delta_deg(previous.velocity.heading_deg, current.velocity.heading_deg)
        turn_rates_dps.append(abs(delta_deg) / dt)

    if not turn_rates_dps:
        return KinematicSignature(
            num_samples=num_samples, avg_speed_mps=avg_speed_mps, mean_turn_rate_dps=0.0, turn_rate_std_dps=0.0
        )

    mean_turn_rate_dps = sum(turn_rates_dps) / len(turn_rates_dps)
    variance = sum((rate - mean_turn_rate_dps) ** 2 for rate in turn_rates_dps) / len(turn_rates_dps)

    return KinematicSignature(
        num_samples=num_samples,
        avg_speed_mps=avg_speed_mps,
        mean_turn_rate_dps=mean_turn_rate_dps,
        turn_rate_std_dps=math.sqrt(variance),
    )


def _confidence(margin: float, scale: float) -> float:
    """Convierte un margen (cuanto se supera el umbral que decidio la
    clase) en una confianza entre 0.5 (justo en el umbral) y 0.95 (margen
    amplio o mayor). Nunca 1.0: una firma cinematica es evidencia indirecta
    del comportamiento, no una certeza absoluta."""
    normalized = max(0.0, min(1.0, margin / scale))
    return 0.5 + 0.45 * normalized


def classify(track: Track) -> Classification:
    """Clasifica una traza por su firma cinematica, con la regla que
    decidio el resultado explicada en `rationale`. No mira `track.status`:
    clasificacion y confirmacion de traza son responsabilidades
    independientes, y una traza aun TENTATIVE con suficientes puntos puede
    clasificarse igual que una CONFIRMED.

    Limitacion conocida: una orbita de reconocimiento muy ancha y lenta,
    observada en una ventana corta, puede curvar tan poco que resulte
    indistinguible de una linea recta -- en ese caso esta funcion
    clasificara la traza como FPV_ATTACK (o quedara sin clasificar si
    tambien va despacio). No hay forma de evitarlo sin mas historial o un
    umbral de ritmo de giro mas sensible al ruido; se documenta en vez de
    ajustarse a un caso de prueba concreto.
    """
    signature = compute_kinematic_signature(track)

    if signature.num_samples < _MIN_SAMPLES_FOR_CLASSIFICATION:
        return Classification(
            track_id=track.track_id,
            drone_class=DroneClass.UNKNOWN,
            confidence=0.2,
            rationale=(
                f"Historial insuficiente ({signature.num_samples} puntos, minimo "
                f"{_MIN_SAMPLES_FOR_CLASSIFICATION}) para una firma cinematica fiable."
            ),
        )

    if signature.avg_speed_mps < _BIRD_MAX_SPEED_MPS:
        confidence = _confidence(_BIRD_MAX_SPEED_MPS - signature.avg_speed_mps, _BIRD_MAX_SPEED_MPS)
        return Classification(
            track_id=track.track_id,
            drone_class=DroneClass.BIRD_CLUTTER,
            confidence=confidence,
            rationale=(
                f"Velocidad media {signature.avg_speed_mps:.1f} m/s, por debajo del umbral de "
                f"{_BIRD_MAX_SPEED_MPS:.1f} m/s: compatible con un ave o un falso positivo de clutter, "
                "no con un dron en desplazamiento sostenido."
            ),
        )

    if signature.turn_rate_std_dps >= _ERRATIC_TURN_RATE_STD_THRESHOLD_DPS:
        confidence = _confidence(
            signature.turn_rate_std_dps - _ERRATIC_TURN_RATE_STD_THRESHOLD_DPS, _ERRATIC_TURN_RATE_STD_THRESHOLD_DPS
        )
        return Classification(
            track_id=track.track_id,
            drone_class=DroneClass.COMMERCIAL,
            confidence=confidence,
            rationale=(
                f"Velocidad media {signature.avg_speed_mps:.1f} m/s con ritmo de giro erratico "
                f"(desviacion {signature.turn_rate_std_dps:.1f} deg/s, umbral "
                f"{_ERRATIC_TURN_RATE_STD_THRESHOLD_DPS:.1f}): sin patron de aproximacion ni de orbita, "
                "compatible con un dron recreativo sin rumbo fijo."
            ),
        )

    if signature.mean_turn_rate_dps < _ATTACK_MAX_MEAN_TURN_RATE_DPS:
        if signature.avg_speed_mps < _ATTACK_MIN_SPEED_MPS:
            return Classification(
                track_id=track.track_id,
                drone_class=DroneClass.UNKNOWN,
                confidence=0.3,
                rationale=(
                    f"Trayectoria recta y consistente (ritmo de giro medio {signature.mean_turn_rate_dps:.2f} deg/s) "
                    f"pero a solo {signature.avg_speed_mps:.1f} m/s, por debajo del umbral de "
                    f"{_ATTACK_MIN_SPEED_MPS:.1f} m/s esperado para una aproximacion hostil: "
                    "no encaja con suficiente confianza en ningun perfil conocido."
                ),
            )
        confidence = _confidence(
            _ATTACK_MAX_MEAN_TURN_RATE_DPS - signature.mean_turn_rate_dps, _ATTACK_MAX_MEAN_TURN_RATE_DPS
        )
        return Classification(
            track_id=track.track_id,
            drone_class=DroneClass.FPV_ATTACK,
            confidence=confidence,
            rationale=(
                f"Velocidad media {signature.avg_speed_mps:.1f} m/s en linea consistente "
                f"(ritmo de giro medio {signature.mean_turn_rate_dps:.2f} deg/s, desviacion "
                f"{signature.turn_rate_std_dps:.1f} deg/s): compatible con una aproximacion directa sostenida."
            ),
        )

    confidence = _confidence(
        signature.mean_turn_rate_dps - _ATTACK_MAX_MEAN_TURN_RATE_DPS, _ATTACK_MAX_MEAN_TURN_RATE_DPS * 4.0
    )
    return Classification(
        track_id=track.track_id,
        drone_class=DroneClass.ISR_FIXED_WING,
        confidence=confidence,
        rationale=(
            f"Velocidad media {signature.avg_speed_mps:.1f} m/s con giro sostenido y consistente "
            f"(ritmo medio {signature.mean_turn_rate_dps:.2f} deg/s, "
            f"desviacion {signature.turn_rate_std_dps:.1f} deg/s): "
            "compatible con una orbita de reconocimiento a radio constante."
        ),
    )
