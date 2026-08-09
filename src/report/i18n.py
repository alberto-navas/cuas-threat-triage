"""
Traduccion del informe y del panel web (ES/EN/DE): plantillas de los
mensajes dinamicos que produce el scoring, y los textos fijos de la
interfaz.

Decision de diseno central, la misma que en el proyecto hermano: los
componentes de puntuacion (`ScoreComponent`) siguen guardando su
justificacion en español en el campo `rationale` de siempre (para no
romper nada que dependa de ese valor por defecto), pero ADEMAS guardan
`message_key` + `message_params` (ver src/model.py). Este modulo usa esas
dos cosas para volver a renderizar el mismo razonamiento en otro idioma en
el momento de generar el informe, sin que src/scoring/, src/classification/
ni src/decision/ tengan que saber nada de idiomas.

Limite deliberado: el nombre de un activo (`asset_id`), el nombre de un
anillo de proximidad (`ring_name`) y la descripcion de un escenario son
texto que escribio quien definio el escenario YAML, no texto que genera
este sistema -- igual que el proyecto hermano no traduce un mensaje de
firmware citado tal cual. Esas cadenas viajan sin tocar en cualquier
idioma del informe.
"""

from collections.abc import Mapping

SUPPORTED_LANGUAGES = ("es", "en", "de")
DEFAULT_LANGUAGE = "es"


def normalize_lang(lang: str | None) -> str:
    """Devuelve `lang` si es uno de los soportados, o el idioma por defecto si no."""
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return DEFAULT_LANGUAGE


# ---------------------------------------------------------------------------
# Plantillas de los componentes de puntuacion (src/scoring/*.py,
# src/decision/prioritizer.py). Cada clave corresponde a un `message_key`
# guardado en el ScoreComponent en el momento de crearlo. Los placeholders
# se rellenan con `message_params` via str.format(), salvo `drone_class`
# (ver DRONE_CLASS_LABELS) que se traduce aparte antes de formatear.
# ---------------------------------------------------------------------------

COMPONENT_MESSAGES: dict[str, dict[str, str]] = {
    "kinematics_no_relative_motion": {
        "es": "Sin movimiento relativo significativo respecto a '{asset_id}' (a {distance:.0f} m): "
        "no hay dinámica de aproximación que evaluar.",
        "en": "No significant relative motion toward '{asset_id}' (at {distance:.0f} m): "
        "no approach dynamics to evaluate.",
        "de": "Keine signifikante Relativbewegung zu '{asset_id}' ({distance:.0f} m entfernt): "
        "keine Annäherungsdynamik zu bewerten.",
    },
    "kinematics_receding": {
        "es": "Alejándose de '{asset_id}': el punto de máxima aproximación ya pasó (hace {elapsed:.0f} s).",
        "en": "Moving away from '{asset_id}': the closest point of approach already happened ({elapsed:.0f} s ago).",
        "de": "Entfernt sich von '{asset_id}': der Punkt der größten Annäherung liegt bereits {elapsed:.0f} s zurück.",
    },
    "kinematics_approach": {
        "es": "TCPA {tcpa:.0f} s, DCPA {dcpa:.0f} m respecto a '{asset_id}' (urgencia por tiempo "
        "{urgency_tcpa:.0f}/100, por distancia {urgency_dcpa:.0f}/100).",
        "en": "TCPA {tcpa:.0f} s, DCPA {dcpa:.0f} m from '{asset_id}' (time urgency {urgency_tcpa:.0f}/100, "
        "distance urgency {urgency_dcpa:.0f}/100).",
        "de": "TCPA {tcpa:.0f} s, DCPA {dcpa:.0f} m zu '{asset_id}' (Dringlichkeit nach Zeit "
        "{urgency_tcpa:.0f}/100, nach Distanz {urgency_dcpa:.0f}/100).",
    },
    "zone_inside_ring": {
        "es": "A {distance:.0f} m de '{asset_id}', dentro del anillo '{ring_name}' (radio {radius:.0f} m).",
        "en": "{distance:.0f} m from '{asset_id}', inside the '{ring_name}' ring (radius {radius:.0f} m).",
        "de": "{distance:.0f} m von '{asset_id}' entfernt, innerhalb des Rings '{ring_name}' (Radius {radius:.0f} m).",
    },
    "zone_outside_all_rings": {
        "es": "A {distance:.0f} m de '{asset_id}', fuera de todos los anillos de proximidad "
        "(el más amplio, '{outer_name}', tiene {outer_radius:.0f} m de radio).",
        "en": "{distance:.0f} m from '{asset_id}', outside every proximity ring (the widest, "
        "'{outer_name}', has a {outer_radius:.0f} m radius).",
        "de": "{distance:.0f} m von '{asset_id}' entfernt, außerhalb aller Annäherungsringe (der "
        "weiteste, '{outer_name}', hat einen Radius von {outer_radius:.0f} m).",
    },
    "classification_risk": {
        "es": "Clasificada como {drone_class_label} con confianza {confidence:.0%} (riesgo base "
        "{base_risk:.0f}/100 para ese tipo); ponderado hacia el valor neutro ({neutral:.0f}/100) "
        "en proporción a la incertidumbre de la clasificación.",
        "en": "Classified as {drone_class_label} with {confidence:.0%} confidence (base risk "
        "{base_risk:.0f}/100 for that type); weighted toward the neutral value ({neutral:.0f}/100) "
        "in proportion to the classification's uncertainty.",
        "de": "Klassifiziert als {drone_class_label} mit {confidence:.0%} Konfidenz (Basisrisiko "
        "{base_risk:.0f}/100 für diesen Typ); gewichtet zum neutralen Wert ({neutral:.0f}/100) im "
        "Verhältnis zur Unsicherheit der Klassifizierung.",
    },
    "behavior_no_speed": {
        "es": "Sin velocidad significativa reciente: no hay rumbo del que evaluar la alineación con el activo.",
        "en": "No significant recent speed: there's no heading to evaluate alignment with the asset.",
        "de": "Keine signifikante aktuelle Geschwindigkeit: kein Kurs vorhanden, um die Ausrichtung "
        "zum Objekt zu bewerten.",
    },
    "behavior_alignment": {
        "es": "Desalineación media de {mean_misalignment:.0f} grados entre el rumbo y el activo "
        "'{asset_id}' en los últimos {num_points} puntos (0 grados = apuntando directamente, "
        "180 = alejándose en línea recta).",
        "en": "Average heading misalignment of {mean_misalignment:.0f} degrees from '{asset_id}' "
        "over the last {num_points} points (0 degrees = pointing straight at it, 180 = moving "
        "straight away).",
        "de": "Durchschnittliche Kursabweichung von {mean_misalignment:.0f} Grad zum Objekt "
        "'{asset_id}' über die letzten {num_points} Punkte (0 Grad = direkt darauf zu, 180 = "
        "geradlinig davon weg).",
    },
    "asset_criticality": {
        "es": "Activo '{asset_id}' con criticidad declarada {criticality}/5.",
        "en": "Asset '{asset_id}' with a declared criticality of {criticality}/5.",
        "de": "Objekt '{asset_id}' mit angegebener Kritikalität {criticality}/5.",
    },
}

# Etiqueta legible para el valor crudo de DroneClass que viaja en
# message_params["drone_class"] (p.ej. "fpv_attack"). Se inyecta como
# `drone_class_label` antes de formatear la plantilla de "classification_risk".
DRONE_CLASS_LABELS: dict[str, dict[str, str]] = {
    "fpv_attack": {
        "es": "ataque FPV (fpv_attack)",
        "en": "FPV attack (fpv_attack)",
        "de": "FPV-Angriff (fpv_attack)",
    },
    "isr_fixed_wing": {
        "es": "ala fija ISR / reconocimiento (isr_fixed_wing)",
        "en": "ISR fixed-wing / reconnaissance (isr_fixed_wing)",
        "de": "ISR-Starrflügler / Aufklärung (isr_fixed_wing)",
    },
    "commercial": {
        "es": "comercial o recreativo (commercial)",
        "en": "commercial or recreational (commercial)",
        "de": "kommerziell oder Freizeit (commercial)",
    },
    "bird_clutter": {
        "es": "ave o clutter (bird_clutter)",
        "en": "bird or clutter (bird_clutter)",
        "de": "Vogel oder Clutter (bird_clutter)",
    },
    "unknown": {
        "es": "sin clasificar (unknown)",
        "en": "unclassified (unknown)",
        "de": "nicht klassifiziert (unknown)",
    },
}


def translate_component(
    message_key: str | None, message_params: Mapping[str, object], rationale: str, lang: str
) -> str:
    """Vuelve a renderizar la justificacion de un `ScoreComponent` en
    `lang`. Si no tiene `message_key` (o no se reconoce), devuelve
    `rationale` tal cual -- nunca deja un componente sin texto."""
    lang = normalize_lang(lang)
    if message_key is None or message_key not in COMPONENT_MESSAGES:
        return rationale

    params = dict(message_params)
    if "drone_class" in params:
        raw_class = str(params.pop("drone_class"))
        params["drone_class_label"] = DRONE_CLASS_LABELS.get(raw_class, {}).get(lang, raw_class)

    return COMPONENT_MESSAGES[message_key][lang].format(**params)


# ---------------------------------------------------------------------------
# Etiquetas cortas (nivel de amenaza, nombre de componente) -- se pasan al
# contexto de Jinja2 como diccionarios planos para el idioma activo.
# ---------------------------------------------------------------------------

TIER_LABELS: dict[str, dict[str, str]] = {
    "critical": {"es": "crítico", "en": "critical", "de": "kritisch"},
    "high": {"es": "alto", "en": "high", "de": "hoch"},
    "medium": {"es": "medio", "en": "medium", "de": "mittel"},
    "low": {"es": "bajo", "en": "low", "de": "niedrig"},
}

COMPONENT_NAME_LABELS: dict[str, dict[str, str]] = {
    "cinematica": {"es": "Cinemática", "en": "Kinematics", "de": "Kinematik"},
    "zona": {"es": "Zona", "en": "Zone", "de": "Zone"},
    "clasificacion": {"es": "Clasificación", "en": "Classification", "de": "Klassifizierung"},
    "comportamiento": {"es": "Comportamiento", "en": "Behavior", "de": "Verhalten"},
    "criticidad_activo": {"es": "Criticidad del activo", "en": "Asset criticality", "de": "Kritikalität des Objekts"},
}


def labels_for(dictionary: dict[str, dict[str, str]], lang: str) -> dict[str, str]:
    """Aplana TIER_LABELS/COMPONENT_NAME_LABELS a un dict {clave: texto} para un idioma, listo para Jinja2."""
    lang = normalize_lang(lang)
    return {key: values[lang] for key, values in dictionary.items()}


# ---------------------------------------------------------------------------
# Textos fijos de la interfaz (informe y mapa tactico). Un solo diccionario
# grande por idioma en vez de decenas de pequeños: mas facil de revisar que
# las 3 versiones de cada frase esten completas y sean coherentes entre si.
# ---------------------------------------------------------------------------

UI_STRINGS: dict[str, dict[str, str]] = {
    "es": {
        "report_title": "Informe de amenazas",
        "generated_prefix": "Generado",
        "duration_label": "Duración simulada",
        "step_label": "Paso",
        "assets_suffix": "activo(s) protegido(s)",
        "tracks_suffix": "traza(s) activa(s) evaluada(s)",
        "map_heading": "Mapa táctico",
        "priority_heading": "Prioridad de respuesta",
        "th_rank": "#",
        "th_track": "Traza",
        "th_asset": "Activo amenazado",
        "th_score": "Puntuación",
        "th_tier": "Nivel",
        "breakdown_heading": "Desglose por traza",
        "footer_line1": "Datos sintéticos generados por simulación — ningún dato procede de sensores reales.",
        "footer_line2": "Esta es la capa de detección → seguimiento → clasificación → decisión: una "
        "herramienta de apoyo a la decisión, no de neutralización. Ver el README del proyecto para el "
        "alcance completo y sus límites éticos.",
        "map_axis_east": "Este (m)",
        "map_axis_north": "Norte (m)",
        "map_unscored": "sin puntuar",
        "map_hover_asset": "Activo",
        "map_hover_criticality": "Criticidad",
        "map_hover_east": "este",
        "map_hover_north": "norte",
    },
    "en": {
        "report_title": "Threat report",
        "generated_prefix": "Generated",
        "duration_label": "Simulated duration",
        "step_label": "Step",
        "assets_suffix": "protected asset(s)",
        "tracks_suffix": "active track(s) evaluated",
        "map_heading": "Tactical map",
        "priority_heading": "Response priority",
        "th_rank": "#",
        "th_track": "Track",
        "th_asset": "Threatened asset",
        "th_score": "Score",
        "th_tier": "Level",
        "breakdown_heading": "Per-track breakdown",
        "footer_line1": "Synthetic data generated by simulation — none of it comes from real sensors.",
        "footer_line2": "This is the detection → tracking → classification → decision layer: a decision-"
        "support tool, not a neutralization one. See the project README for the full scope and its "
        "ethical limits.",
        "map_axis_east": "East (m)",
        "map_axis_north": "North (m)",
        "map_unscored": "unscored",
        "map_hover_asset": "Asset",
        "map_hover_criticality": "Criticality",
        "map_hover_east": "east",
        "map_hover_north": "north",
    },
    "de": {
        "report_title": "Bedrohungsbericht",
        "generated_prefix": "Erstellt am",
        "duration_label": "Simulierte Dauer",
        "step_label": "Schritt",
        "assets_suffix": "geschützte(s) Objekt(e)",
        "tracks_suffix": "aktive(r) Track(s) ausgewertet",
        "map_heading": "Taktische Karte",
        "priority_heading": "Reaktionspriorität",
        "th_rank": "#",
        "th_track": "Track",
        "th_asset": "Bedrohtes Objekt",
        "th_score": "Punktzahl",
        "th_tier": "Stufe",
        "breakdown_heading": "Aufschlüsselung pro Track",
        "footer_line1": "Synthetische, durch Simulation erzeugte Daten — keine Daten stammen von echten Sensoren.",
        "footer_line2": "Dies ist die Ebene Erkennung → Verfolgung → Klassifizierung → Entscheidung: ein "
        "Werkzeug zur Entscheidungsunterstützung, kein Werkzeug zur Neutralisierung. Der vollständige "
        "Umfang und seine ethischen Grenzen stehen im README des Projekts.",
        "map_axis_east": "Osten (m)",
        "map_axis_north": "Norden (m)",
        "map_unscored": "nicht bewertet",
        "map_hover_asset": "Objekt",
        "map_hover_criticality": "Kritikalität",
        "map_hover_east": "Ost",
        "map_hover_north": "Nord",
    },
}


def ui(lang: str) -> Mapping[str, str]:
    """Devuelve el diccionario de textos fijos de la interfaz para `lang`, listo para pasar a Jinja2."""
    return UI_STRINGS[normalize_lang(lang)]
