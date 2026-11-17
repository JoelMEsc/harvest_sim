# harvest_sim — Línea base reactiva de cosecha (2D)

Reto agrícola multiagente · Equipo 3 · TC2008B.
Simulación 2D en Python de **una cosechadora y un carro recolector**. Es la línea base contra la que se compararán las mejoras de coordinación. Python genera un log JSON (`trace.json`); el visor, las métricas, las gráficas y los experimentos solo leen ese archivo.

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

Los scripts de `tools/` y `viz/` también corren sin `pip install -e .` (agregan `src/` a la ruta), pero lo recomendado es instalar.

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

# Visor 2D, a partir del log
python viz/viewer.py runs/escenario_a/trace.json

# Dashboard interactivo en HTML (junta entorno, indicadores y experimentos)
python viz/dashboard.py runs/escenario_a runs/escenario_b runs/escenario_c --salida runs/dashboard.html

# Pruebas automatizadas
pytest
pytest tests/test_mundo.py::test_serpentina_cubre_todo_el_campo   # un solo test
```

La simulación es determinista a propósito: no hay aleatoriedad en esta entrega.

## Verificación en un entorno limpio

Para comprobar que el proyecto se instala y ejecuta correctamente desde cero en una máquina limpia (criterio 8 de reproducibilidad):

```bash
bash scripts/verificar_instalacion.sh
```

Este script crea automáticamente un entorno virtual en una carpeta temporal, instala dependencias desde `requirements.txt`, ejecuta `pytest` y corre `scripts/correr_todos.sh`, limpiando los archivos temporales al terminar.

## Datos: log, métricas, gráficas y experimentos (ya funciona)

Todo lo de esta sección se puede usar hoy con **datos de ejemplo** y funciona igual con los traces reales cuando exista la simulación.

### 1. Conseguir traces

```bash
python tools/generar_trace_ejemplo.py --escenarios     # 3 traces de ejemplo en runs/ejemplo/<nombre>/trace.json
python tools/generar_trace_ejemplo.py                  # regenera tests/fixtures/trace_ejemplo.json (el de las pruebas)
```

El generador **no es la simulación**: produce datos de ejemplo deterministas (1 cosechadora, 1 carro, sin obstáculos) para desarrollar el visor, el dashboard y las pruebas sin esperar. Los traces reales salen de `python -m harvest_sim.cli`.

### 2. Validar un trace

```bash
python tools/validar_trace.py runs/ejemplo/*/trace.json
python tools/validar_trace.py runs/escenario_a/trace.json --max 20 --retraso-maximo 1
```

Imprime `OK` o cada error con el tick, el evento y el campo (por ejemplo, `tick 14, evento 2 (DEPOSITO): entregado_total 7, se esperaba 6`), y sale con código 1 si hay errores. Es lo primero que hay que correr cuando la simulación produzca su primer trace.

### 3. Gráficas y tabla resumen

```bash
python viz/plots.py runs/escenario_a/trace.json runs/escenario_b/trace.json runs/escenario_c/trace.json
python viz/plots.py runs/escenario_a/trace.json --agente cosechadora_1     # una sola cosechadora en vez del promedio
python viz/plots.py runs/ejemplo/*/trace.json --salida otra/carpeta
```

| Salida | Qué muestra |
|---|---|
| `runs/<escenario>/plots/1_linea_de_tiempo_estados.png` | Qué hace cada agente en cada tick |
| `2_ocioso_acumulado.png` | Tiempo que la cosechadora lleva esperando al carro |
| `3_distancia_cosechadora_carro.png` | Distancia de la cosechadora al carro más cercano |
| `4_flujo_del_grano.png` | Grano en la bodega + en tránsito = cosechado, contra el total esperado |
| `5_mapa_espera.png`, `6_mapa_trafico.png` | Dónde espera la cosechadora y por dónde pasan los agentes |
| `runs/comparacion/comparacion_escenarios.png` | 6 indicadores comparados entre escenarios |
| `runs/comparacion/resumen.csv`, `resumen.md` | Todas las métricas (CSV) y las principales (Markdown, para el reporte) |

### 4. Experimentos (barrido de parámetros)

```bash
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json --simulador ejemplo   # mientras no exista la simulación
```

Un experimento es un JSON en `config/experimentos/` con los escenarios, el barrido (`{"parámetro": [valores]}`), las repeticiones y la métrica a graficar. Escribe en `runs/experimentos/<nombre>/`: `resultados.csv` (una fila por corrida), `resumen.csv` (media, desviación estándar e intervalo de confianza del 95 %) y `sensibilidad_<parámetro>.png`. Con `--simulador ejemplo` los números **no** son resultados: solo sirven para probar la herramienta.

### 5. Desde Python

```python
from harvest_sim.datos import (TraceBuilder, cargar_trace, escribir_trace, validar_trace,
                               calcular_metricas, series_temporales, reconstruir, grano_esperado)

trace = cargar_trace("runs/escenario_a/trace.json")
validar_trace(trace)                     # [] si cumple el formato
m = calcular_metricas(trace)
m["tiempo_ocioso_cosechadora"]           # promedio por cosechadora (métrica principal)
m["por_agente"]["cosechadora_1"]         # detalle de un agente
for estado in reconstruir(trace):        # estado completo de cada tick (para pruebas)
    ...
```

`harvest_sim.telemetria` reexporta lo mismo (compatibilidad con imports anteriores).

### 6. Qué hay en el paquete `src/harvest_sim/datos/`

| Módulo | Contenido |
|---|---|
| `formato.py` | Versión del formato (2.1), tipos de evento y vocabulario compartido: estados, mensajes, performativas y clases de la ontología |
| `trace.py` | `TraceBuilder` (lo usa la simulación para armar el log), checksum por tick, escribir, cargar y verificar |
| `linea_de_tiempo.py` | Recorre el trace una sola vez y da el estado de cada tick; `reconstruir` |
| `campo.py` | Celdas de campo, obstáculos y grano esperado: la fórmula en un solo lugar |
| `metricas.py` | Métricas (promedio por tipo de agente + detalle por agente), series por tick y mapas por celda |
| `validacion.py` | `validar_trace`: el contrato del formato |
| `experimentos.py` | Escenarios × barrido × repeticiones y resumen estadístico |
| `tablas.py` | Aplanar métricas para CSV |

El formato del log y lo que cada módulo de la simulación debe entregarle a `TraceBuilder` están en [`docs/equipo/README.md`](docs/equipo/README.md) §3 y en la especificación §6.1. Las definiciones de las métricas, en la especificación §6.2 y en [`docs/decisiones.md`](docs/decisiones.md).

## Estructura

```
config/              escenarios (parámetros externos al código) y experimentos (config/experimentos/)
docs/                especificación, plan de trabajo, decisiones, ontología
docs/equipo/         guía paso a paso de cada persona y el contrato del trace
src/harvest_sim/     simulación (mundo, rutas, mensajes, agentes, CLI)
src/harvest_sim/datos/  log, métricas, validador y experimentos
viz/                 visor, gráficas y dashboard (solo leen trace.json)
tools/               validar traces, correr experimentos, generar datos de ejemplo
tests/               una prueba por regla física y por comportamiento; tests/fixtures/ con el trace de ejemplo
runs/                salidas de las corridas (no se versionan)
```

## Reparto de trabajo

Cada archivo tiene un solo dueño. Tareas, dependencias y cronograma: [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md). Guía de cada persona: [`docs/equipo/`](docs/equipo/README.md).

| Persona | Rama | Archivos |
|---|---|---|
| Carlos | `branch-carlos` | `config.py`, `mundo.py`, `simulacion.py`, `config/escenario_*.json` |
| Oswaldo | `branch-oswaldo` | `rutas.py`, `carro.py`, `tests/test_rutas.py`, `tests/test_carro.py` |
| Emilio | `branch-emilio` | `mensajes.py`, `cosechadora.py`, `tests/test_mensajes.py`, `tests/test_cosechadora.py` |
| Joel | `branch-joel` | `src/harvest_sim/datos/`, `telemetria.py`, `viz/plots.py`, `tools/`, `config/experimentos/`, `tests/fixtures/` y las pruebas de Datos; arma el PDF de la entrega |
| Giovanni | `branch-giovanni` | `viz/viewer.py`, `viz/dashboard.py`, `cli.py`, `tests/test_viewer.py`, `tests/test_dashboard.py` |
| Ilan | `branch-ilan` | `tests/test_mundo.py`, `tests/test_config.py`, `tests/test_integracion.py`, `.github/`, `scripts/`, `README.md`, `docs/autoevaluacion.md` |

Cada archivo tiene en su docstring la sección de la especificación que implementa. Los tests pendientes están marcados con `skip`: quita el decorador al implementar cada uno.

## Flujo de trabajo

- Ramas: `main` (entrega), `development` (integración) y una rama personal por persona.
- Todo entra a `development` por pull request con una aprobación y CI en verde; nadie hace push directo.
- El contrato de interfaces ([`docs/equipo/README.md`](docs/equipo/README.md) §3 y §10 de la especificación) no se cambia sin avisar al equipo y anotarlo en [`docs/decisiones.md`](docs/decisiones.md).
- Todo lo no especificado se decide con la opción más simple y se registra en `docs/decisiones.md`.
