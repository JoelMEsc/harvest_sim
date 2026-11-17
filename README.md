# harvest_sim — Línea base reactiva de cosecha (2D)

Reto agrícola multiagente · Equipo 3 · TC2008B.
Simulación 2D en Python de **una cosechadora y un carro recolector**. Es la línea base contra la que se compararán las mejoras de coordinación. Python genera un log JSON (`trace.json`); el visor y las gráficas solo leen ese archivo.

> **Estado (17 de noviembre):** la parte de Datos, CI (.github/workflows/ci.yml), scripts de automatización y suites completas de pruebas (configuración, mundo e integración) están implementadas. Los módulos de la simulación y agentes se encuentran en fase final de integración.
> **Entrega: martes 17 de noviembre, antes de la clase.** Cada persona tiene su guía paso a paso en [`docs/equipo/`](docs/equipo/README.md): **empieza por ahí**. La referencia de qué construir es [`docs/especificacion_primera_entrega.md`](docs/especificacion_primera_entrega.md).

## Instalación

Requiere Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Uso

### Ejecución integral de todos los escenarios

La forma más rápida de ejecutar la simulación completa, validar los logs, generar gráficas, tabla resumen y experimentos es mediante el script:

```bash
bash scripts/correr_todos.sh
```

*(Para probar todo el pipeline con datos de ejemplo antes de la integración final de la CLI, se puede utilizar `bash scripts/correr_todos.sh --ejemplo`).*

### Ejecución paso a paso

```bash
# Correr un escenario (genera runs/<escenario>/trace.json y gráficas)
python -m harvest_sim.cli config/escenario_a.json

# Visor 2D y gráficas, a partir del log
python viz/viewer.py runs/escenario_a/trace.json
python viz/plots.py runs/escenario_a/trace.json

# Dashboard interactivo en HTML (junta entorno, indicadores y experimentos)
python viz/dashboard.py runs/escenario_a runs/escenario_b runs/escenario_c --salida runs/dashboard.html

# Pruebas automatizadas
pytest
pytest tests/test_mundo.py::test_serpentina_cubre_todo_el_campo   # un solo test
```

Los comandos de CLI, visor y gráficas todavía lanzan `NotImplementedError` (esqueleto).
La simulación es determinista a propósito: no hay aleatoriedad en esta entrega.

## Verificación en un entorno limpio

Para comprobar que el proyecto se instala y ejecuta correctamente desde cero en una máquina limpia (criterio 8 de reproducibilidad):

```bash
bash scripts/verificar_instalacion.sh
```

Este script crea automáticamente un entorno virtual en una carpeta temporal, instala dependencias desde `requirements.txt`, ejecuta `pytest` y corre `scripts/correr_todos.sh`, limpiando los archivos temporales al terminar.

## Estructura

```
config/            escenarios (parámetros externos al código)
docs/              especificación y registro de decisiones
src/harvest_sim/   simulación (mundo, mensajes, agentes, telemetría, CLI)
viz/               visor y gráficas (solo leen trace.json)
tests/             una prueba por regla física y por comportamiento
runs/              salidas de las corridas (no se versionan)
```

## Reparto de trabajo

Cada archivo tiene un solo dueño. El detalle de tareas, dependencias y cronograma está en [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md).

| Persona | Rama | Archivos |
|---|---|---|
| Carlos | `branch-carlos` | `config.py`, `mundo.py`, `simulacion.py` |
| Oswaldo | `branch-oswaldo` | `rutas.py`, `carro.py`, `tests/test_rutas.py`, `tests/test_carro.py` |
| Mario | `branch-mario` | `mensajes.py`, `cosechadora.py`, `tests/test_mensajes.py`, `tests/test_cosechadora.py` |
| Joel | `branch-joel` | `telemetria.py`, `viz/plots.py`, `tools/`, `tests/fixtures/`, `tests/test_telemetria.py` |
| Emilio | `branch-emilio` | `viz/viewer.py`, `cli.py`, `tests/test_viewer.py` |
| Ilan | `branch-ilan` | `tests/test_mundo.py`, `tests/test_config.py`, `tests/test_integracion.py`, `.github/`, `scripts/`, `README.md`, `docs/autoevaluacion.md` |

Cada archivo tiene en su docstring la sección de la especificación que implementa. Los tests pendientes están marcados con `skip`: quita el decorador al implementar cada uno.

## Flujo de trabajo

- Ramas: `main` (entrega, solo el lunes), `development` (integración) y una rama personal por persona.
- Todo entra a `development` por pull request con una aprobación y CI en verde; nadie hace push directo.
- El contrato de interfaces (§3.1 del plan y §10 de la especificación) no se cambia sin avisar al equipo y anotarlo en [`docs/decisiones.md`](docs/decisiones.md).
- Todo lo no especificado se decide con la opción más simple y se registra en `docs/decisiones.md`.
