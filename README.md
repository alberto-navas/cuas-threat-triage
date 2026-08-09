# C-UAS Threat Triage

[English](README.en.md) · **Español**

[![Tests](https://github.com/alberto-navas/cuas-threat-triage/actions/workflows/tests.yml/badge.svg)](https://github.com/alberto-navas/cuas-threat-triage/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Demo en vivo: [cuas-threat-triage.onrender.com](https://cuas-threat-triage.onrender.com)**
(plan gratuito: si lleva un rato inactivo, la primera carga tarda ~30-50s)

Sistema de apoyo a la decisión de priorización de amenazas para defensa
antidrones (C-UAS). A partir de un escenario simulado, construye el
pipeline completo — detección → seguimiento → clasificación → decisión —
y produce un ranking de prioridad de respuesta explicable: qué traza
atender primero, contra qué activo, y por qué.

<p align="center">
  <img src="docs/screenshots/demo.gif" alt="Demo: elegir un escenario, generar el informe, y ver el mapa táctico, la tabla de prioridad y el desglose explicable por traza" width="800">
</p>

## Motivación

Un operador de defensa aérea evaluando varios contactos simultáneos tiene
que decidir, en segundos, cuál atender primero. Ese razonamiento —
cinemática de aproximación, tipo de contacto, proximidad a lo que se
protege — es exactamente el tipo de problema que se presta a una capa de
software explicable: no sustituye el juicio del operador, se lo entrega ya
ordenado y justificado. Este proyecto es una exploración de esa capa de
decisión, con datos 100% sintéticos (no existe ningún dataset público de
trazas C-UAS fusionadas — es información sensible en cualquier sistema
operativo real).

## Capacidades

- **Simulación de escenarios**: activos protegidos con anillos de
  proximidad, sensores con ruido y probabilidad de detección configurables,
  y cuatro arquetipos de amenaza (aproximación directa tipo FPV, órbita de
  reconocimiento, deriva recreativa errática, clutter/ave) —
  `src/simulation/`.
- **Seguimiento multi-objetivo**: filtro alpha-beta de velocidad constante
  + asociación vecino-más-cercano con puerta de distancia + confirmación
  M-de-N (`TENTATIVE → CONFIRMED → COASTING → DROPPED`) — `src/tracking/`.
- **Clasificación explicable por firma cinemática**: velocidad media, ritmo
  de giro y su consistencia deciden el tipo de dron mediante un árbol de
  reglas documentado, no una caja negra — `src/classification/`. La traza
  nunca lleva ninguna pista sobre el arquetipo que la generó: el
  clasificador solo ve lo mismo que vería un sistema real.
- **Puntuación de amenaza en cuatro componentes independientes**, cada uno
  auditable por separado — `src/scoring/`:
  - *Cinemática*: TCPA/DCPA (tiempo y distancia al punto de máxima
    aproximación), la misma matemática que usa la detección de colisiones
    en navegación marítima y control de tráfico aéreo.
  - *Zona*: en qué anillo de proximidad del activo está la traza ahora.
  - *Riesgo por clasificación*: ponderado por la confianza — una
    clasificación poco fiable empuja hacia un valor neutro, no hacia el
    extremo de su clase.
  - *Comportamiento*: alineación de rumbo sostenida con el activo concreto
    (distingue una traza "con pinta de ataque" que apunta a *otro* activo).
- **Decisión multi-activo**: cada traza se puntúa contra todos los activos
  protegidos y se prioriza globalmente por la amenaza más alta, con la
  criticidad declarada del activo como un quinto componente explícito del
  score — `src/decision/`.
- **Informe HTML autocontenido**: mapa táctico (coordenadas locales, no
  geográficas — es un sistema de punto de defensa, no un mapa de calles) +
  tabla de prioridad + desglose completo por traza con la justificación de
  cada componente — `src/report/`.
- **CLI** (`src/cli.py`) y **panel web** (`src/web/`, FastAPI) sobre el
  mismo pipeline compartido (`src/pipeline.py`).

## Arquitectura

`src/model.py` es el modelo de datos común (`Detection`, `Track`,
`ProtectedAsset`, `ThreatScore`...) que usan todas las etapas — el
"vocabulario" compartido que hace que ninguna etapa necesite conocer los
detalles internos de la anterior.

```
escenario (YAML: activos + sensores + amenazas)
        │
        ▼
src/simulation/scenario.py      (carga y valida el escenario)
src/simulation/trajectories.py  (trayectoria "verdad" por arquetipo)
src/simulation/detections.py    (detecciones ruidosas por sensor)
        │
        ▼
src/tracking/filter.py       (filtro alpha-beta de velocidad constante)
src/tracking/associator.py   (asociación vecino-más-cercano con puerta)
src/tracking/tracker.py      (confirmación M-de-N)  ──► Track
        │
        ▼
src/classification/kinematic_signature.py  (reglas por firma cinemática)  ──► DroneClass
        │
        ▼
src/scoring/kinematics.py           (TCPA/DCPA)
src/scoring/zone.py                 (anillos de proximidad)
src/scoring/classification_risk.py  (riesgo por tipo, ponderado por confianza)
src/scoring/behavior.py             (alineación de rumbo sostenida)
        │
        ▼
src/decision/prioritizer.py   (suma ponderada ──► ThreatScore, ranking global)
        │
        ▼
src/report/generator.py  ──► informe HTML (mapa táctico + tabla de prioridad)
        ▲
        │
src/cli.py            src/web/ (FastAPI)
```

Un ejemplo de un detalle de diseño que quedó documentado en el propio
código: el tracker asocia detecciones simultáneas de dos sensores sobre la
misma amenaza de forma "golosa" (vecino-más-cercano puro, no un algoritmo
de asignación óptima como el húngaro), así que puede generar trazas
"fantasma" efímeras — se decidió documentar esa limitación conocida en vez
de resolverla con más complejidad de la que aporta valor a este alcance
(ver `src/tracking/tracker.py`).

## Uso

```bash
# Un escenario -> un informe
python -m src.cli data/scenarios/demo_mixed_threats.yaml

# Varios escenarios -> un informe cada uno, en un directorio
python -m src.cli data/scenarios/*.yaml --output output/

# Ajustar el tracker (puerta de asociación, confirmación/descarte)
python -m src.cli data/scenarios/demo_swarm_multi_asset.yaml --gate-distance-m 100 --confirm-hits 2

# Panel web: elegir o subir un escenario, ver el informe en el navegador
python -m src.web
# -> http://127.0.0.1:8000
```

Los escenarios de demostración están en `data/scenarios/`: uno con los
cuatro arquetipos de amenaza sobre un único activo, otro con un enjambre de
tres aproximaciones simultáneas repartidas entre dos activos con distinta
criticidad.

## Tests

```bash
pytest -v
```

147 tests cubriendo los diez módulos del pipeline (simulación, tracking,
clasificación, scoring, decisión, informe, CLI, panel web), usando
fixtures sintéticas versionadas en `tests/fixtures/` — ninguno depende de
descargar nada externo. Se ejecutan automáticamente en cada `push` vía
GitHub Actions (`.github/workflows/tests.yml`), en Ubuntu y Windows.

## Calidad de código

```bash
ruff check .        # lint
ruff format .       # formato
mypy src/           # comprobación estática de tipos
```

Configurado en `pyproject.toml`. Comprobado automáticamente en cada
`push` (job `lint` separado del de tests). `mypy` solo ignora los stubs
que faltan de `plotly` (no publica tipos); el resto del código, incluido
todo lo propio, se comprueba con precisión.

**Cobertura de tests**: 100% (`pytest --cov=src`), con un umbral de CI en
85% como red de seguridad contra una caída grande, no como objetivo línea
a línea a perseguir.

Un ejemplo real de por qué la cobertura estricta importa aquí: al validar
la clasificación contra el pipeline completo (no contra la trayectoria
ideal), salió a la luz que el ruido de sensor se colaba en la velocidad
filtrada lo bastante como para que una trayectoria perfectamente recta
pareciera errática. Se recalibraron los umbrales de clasificación y el
`beta` del filtro contra datos reales del propio pipeline, no a ciegas —
la causa y la corrección quedaron documentadas en el código
(`src/tracking/tracker.py`, `src/classification/kinematic_signature.py`).

## Datos de prueba

Todo el dato de este proyecto es sintético: no existe ningún dataset
público de trazas C-UAS fusionadas (posición + velocidad + clasificación
por instante) contra el que contrastar, porque es información sensible en
cualquier sistema operativo real — a diferencia del proyecto hermano
([Drone Flight Incident Analyzer](https://github.com/alberto-navas/drone-flight-incident-analyzer)),
donde sí existen logs de vuelo reales y públicos. Los parámetros de cada
arquetipo de amenaza (velocidades, radios de órbita, volatilidad de rumbo)
se eligieron como plausibles para cada perfil — un FPV de ataque más
rápido que un dron comercial, una órbita de reconocimiento con un radio
lo bastante cerrado como para que el ritmo de giro sea detectable —, no
derivados de una especificación o dataset concreto.

## Qué NO hace este proyecto deliberadamente

Esto es la capa de **detección → seguimiento → clasificación → decisión**,
nunca la de neutralización:

- No incluye código de guiado de interceptores, jamming/inhibición de RF,
  spoofing GPS activo, ni control de ningún efector real, cinético o no
  cinético.
- No decide ni ejecuta ninguna acción de enganche o disparo: la salida es
  una lista priorizada para apoyo a la decisión de un operador humano,
  nunca una orden autónoma de intercepción.
- No procesa señal cruda de sensores reales (IQ de radar, RF, vídeo): los
  datos de entrada son sintéticos, generados por un simulador de
  escenarios declarado como tal en cada informe.
- La clasificación de tipo de dron es heurística sobre firma cinemática
  simulada, no un clasificador certificado ni entrenado con datos
  operativos reales.
- El panel web es un *replay* de un escenario simulado, no una conexión en
  vivo a hardware de ningún tipo.

## Posibles extensiones

- Correlación de trazas coordinadas (bonificación de score por "grupo
  swarm") — el generador de escenarios ya soporta amenazas simultáneas
  multi-activo, pero el scoring de v1 puntúa cada traza de forma
  independiente; ver el comentario de fase en `src/decision/prioritizer.py`.
- Un clasificador ML opcional entrenado sobre firma cinemática sintética,
  con explicación por predicción (qué característica pesó más), como
  capa adicional junto a las reglas explícitas actuales — nunca en su
  lugar.
- Terreno real (modelo de elevación) en vez de plano en el cálculo de
  alcance de sensor y DCPA.
