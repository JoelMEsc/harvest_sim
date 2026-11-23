# harvest_sim — Línea base reactiva de cosecha multiagente (2D)

Reto agrícola multiagente con John Deere · Equipo 3 · TC2008B.

**Carpeta de Drive con evidencias:** [Google Drive](https://drive.google.com/drive/folders/1XX1WP433XIvwLuCjnjkFnRm9IYrBwJON?usp=sharing)

Una **cosechadora** recorre un campo en cuadrícula en serpentina. Cuando se llena, le manda un mensaje al **carro recolector**, que va hasta ella, recibe el grano y lo lleva a la **bodega**. El tiempo que la cosechadora pasa llena esperando al carro es el **tiempo ocioso**, la métrica principal del reto. Esta versión es la **línea base reactiva** (el carro sale solo cuando la cosechadora ya está llena), contra la que se compararán las mejoras de coordinación.

La simulación está escrita en Python y produce un log por corrida (`trace.json`). El visor, las métricas, las gráficas, los experimentos y el dashboard **solo leen ese archivo**: la simulación es la única fuente de verdad.

> **Estado (17 de noviembre de 2026):** entrega completa e integrada en `development` y `main`. Los tres escenarios corren de principio a fin, sus logs validan y las 230 pruebas pasan.
>
> **Segunda entrega (en curso): coordinación multiagente.** Varios agentes, obstáculos, subasta Contract Net, despacho anticipado, aleatoriedad, combustible, costo J y servidor FastAPI para Unity. Qué se construye: [`docs/especificacion_segunda_entrega.md`](docs/especificacion_segunda_entrega.md). Guía de cada persona: [`docs/equipo/`](docs/equipo/README.md). Visualización 3D: repositorio [`harvest-simu-visualization`](https://github.com/GioMax102/harvest-simu-visualization).

---

## Inicio rápido

Requiere Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

bash scripts/correr_todos.sh     # simula los 3 escenarios, valida, grafica, corre el experimento y arma el dashboard
```

Al terminar, abre **`runs/dashboard.html`** en el navegador: junta el entorno, los indicadores y los experimentos en una sola página.

Para comprobar que todo funciona desde cero en una carpeta limpia (crea un entorno virtual temporal, instala, corre `pytest` y `correr_todos.sh`):

```bash
bash scripts/verificar_instalacion.sh
```

La simulación es **determinista a propósito**: el mismo escenario produce siempre el mismo `trace.json`, byte a byte.

---

## Resultados de la línea base

Con los tres escenarios de `config/` (generados con `bash scripts/correr_todos.sh`; la tabla completa queda en `runs/comparacion/resumen.md`):

| Escenario | Campo | Capacidad cosechadora / carro | Tasas (transferencia / descarga) | Completación (ticks) | Tiempo ocioso (ticks) | % ocioso | Ciclos | Colisiones | Grano entregado |
|---|---|---|---|---|---|---|---|---|---|
| A | 8 × 6 | 10 / 20 | 2 / 4 | 134 | 50 | 37,0 % | 5 | 0 | 100 % |
| B | 10 × 8 | 15 / 30 | 3 / 5 | 193 | 72 | 37,1 % | 6 | 0 | 100 % |
| C | 8 × 6 | 5 / 10 | 1 / 1 | 262 | 153 | 58,2 % | 10 | 0 | 100 % |

En el escenario C (capacidades chicas y tasas lentas) la cosechadora se vuelve a llenar antes de que el carro regrese, y el tiempo ocioso sube al 58 %. El experimento `config/experimentos/tasa_transferencia.json` muestra que subir la tasa de transferencia de 1 a 5 acorta la corrida de 158 a 120 ticks en A, de 246 a 182 en B y de 262 a 224 en C, con rendimientos decrecientes.

---

## Cómo funciona

```
config/escenario_X.json
        │
        ▼
python -m harvest_sim.cli ──► simulacion.ejecutar
                                 ├─ Mundo (grid, bodega, bases, grano, eventos)
                                 ├─ Cosechadora y Carro (máquinas de estados)
                                 ├─ rutas.py (BFS y conflictos de celda)
                                 └─ Buzon (mensajes LLENA / TRANSFERENCIA_TERMINADA)
                                 │
                                 ▼  TraceBuilder (harvest_sim/datos)
                       runs/escenario_X/trace.json   ◄── único contrato entre módulos
                                 │
       ┌─────────────┬───────────┼──────────────┬──────────────────┐
       ▼             ▼           ▼              ▼                  ▼
  validar_trace   métricas    gráficas     experimentos       visor 2D y dashboard
```

- **Cada tick:** se entregan los mensajes del tick anterior, actúa la cosechadora, actúa el carro y se registra lo que cambió. Un mensaje enviado en `t` se lee en `t+1`.
- **El log (formato 2.1)** guarda solo cambios: posición, estado y carga de cada agente, celdas cosechadas, depósitos, bloqueos y mensajes (con su acto comunicativo: `LLENA` es una petición y `TRANSFERENCIA_TERMINADA` un aviso). Cada tick lleva un checksum.
- **Reglas físicas R1–R9** (dentro del mapa, un paso por tick, nunca dos agentes en la misma celda, transferencia solo entre vecinos, conservación del grano, etc.): las verifican las pruebas de mundo y de integración en cada tick de las corridas reales.

El detalle está en la [especificación](docs/especificacion_primera_entrega.md) y en [`docs/ontologia.md`](docs/ontologia.md).

---

## Uso paso a paso

### Simular un escenario

```bash
python -m harvest_sim.cli config/escenario_a.json                 # runs/escenario_a/trace.json y sus gráficas
python -m harvest_sim.cli config/escenario_a.json --sin-plots     # solo el trace
python -m harvest_sim.cli config/escenario_a.json --silencioso    # sin el log de consola (--detallado: todo)
python -m harvest_sim.cli config/escenario_a.json --salida otra/carpeta
```

En la consola se imprime lo que pasa (cambios de estado, mensajes y depósitos), por ejemplo `t=013 | MSG #1 LLENA cosechadora_1 -> carro_1 {x: 6, y: 2, carga: 10} (se entrega en t=014)`. Si algo falla, la CLI termina con código 1 y el error en `stderr`.

### Ver una corrida en 2D

```bash
python viz/viewer.py runs/escenario_a/trace.json
python viz/viewer.py runs/escenario_a/trace.json --guardar-cuadros runs/escenario_a/cuadros --cada 10   # PNG sin ventana
```

Controles: `Espacio` pausa y reanuda, flechas avanzan o retroceden un tick, `Inicio` / `Fin` van a los extremos, `+` / `-` cambian la velocidad, `Esc` sale.

### Dashboard

```bash
python viz/dashboard.py runs/escenario_a runs/escenario_b runs/escenario_c --salida runs/dashboard.html
```

Tres paneles: **entorno** (cuadros del visor), **indicadores** (métricas y gráficas de cada escenario) y **experimental** (parámetros de cada escenario, comparación, tabla, mapas de calor y sensibilidad). Las imágenes van incrustadas, así que el HTML se puede compartir solo. Lee resultados ya generados: corre antes la simulación, `viz/plots.py`, el experimento y el visor con `--guardar-cuadros` (o simplemente `scripts/correr_todos.sh`).

### Validar un log

```bash
python tools/validar_trace.py runs/escenario_*/trace.json
```

Imprime `OK` o cada error con el tick, el evento y el campo (por ejemplo, `tick 14, evento 2 (DEPOSITO): entregado_total 7, se esperaba 6`), y termina con código 1 si hay errores.

### Gráficas y tabla resumen

```bash
python viz/plots.py runs/escenario_a/trace.json runs/escenario_b/trace.json runs/escenario_c/trace.json
python viz/plots.py runs/escenario_a/trace.json --agente cosechadora_1     # una cosechadora en vez del promedio
```

| Archivo | Pregunta que responde |
|---|---|
| `runs/<escenario>/plots/1_linea_de_tiempo_estados.png` | ¿Qué hace cada agente en cada tick? |
| `2_ocioso_acumulado.png` | ¿Cuánto ha esperado la cosechadora hasta ahora? |
| `3_distancia_cosechadora_carro.png` | ¿Qué tan lejos está el carro? |
| `4_flujo_del_grano.png` | ¿Cuánto grano llegó a la bodega y cuánto va en camino? |
| `5_mapa_espera.png`, `6_mapa_trafico.png` | ¿Dónde espera la cosechadora? ¿Por dónde pasan los agentes? |
| `runs/comparacion/comparacion_escenarios.png` | ¿Cómo se comparan los escenarios (6 indicadores)? |
| `runs/comparacion/resumen.csv`, `resumen.md` | Todas las métricas (CSV) y las principales (Markdown) |

### Experimentos (barrido de parámetros)

```bash
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
```

Un experimento es un JSON en `config/experimentos/` con los escenarios, el barrido (`{"parámetro": [valores]}`), las repeticiones y la métrica a graficar. Escribe en `runs/experimentos/<nombre>/`: `resultados.csv` (una fila por corrida), `resumen.csv` (media, desviación estándar e intervalo de confianza del 95 %) y `sensibilidad_<parámetro>.png`. Como la simulación es determinista, las repeticiones dan lo mismo y el resumen lo indica («sin variación»).

### Datos de ejemplo (sin la simulación)

```bash
python tools/generar_trace_ejemplo.py --escenarios     # 3 traces en runs/ejemplo/
bash scripts/correr_todos.sh --ejemplo                 # todo el flujo con esos datos
```

Sirven para probar el visor, las gráficas y las herramientas sin depender de la simulación. **No** son resultados. `python tools/generar_trace_ejemplo.py` regenera `tests/fixtures/trace_ejemplo.json`, el log de las pruebas.

### Desde Python

```python
from harvest_sim.config import cargar_config
from harvest_sim.simulacion import ejecutar
from harvest_sim.datos import escribir_trace, cargar_trace, validar_trace, calcular_metricas, reconstruir

trace = ejecutar(cargar_config("config/escenario_a.json"))
escribir_trace(trace, "runs/escenario_a/trace.json")
validar_trace(trace)                          # [] si cumple el formato
m = calcular_metricas(trace)                  # también vienen en trace["metricas"]
m["tiempo_ocioso_cosechadora"], m["por_agente"]["carro_1"]
for estado in reconstruir(trace):             # estado completo de cada tick
    ...
```

---

## Parámetros

Cada escenario es un JSON en `config/` (nada de valores fijos en el código):

```json
{
  "nombre": "escenario_a", "seed": 0, "ancho": 8, "alto": 7,
  "num_carros": 1, "num_cosechadoras": 1, "grano_por_celda": 1,
  "capacidad_cosechadora": 10, "capacidad_carro": 20,
  "tasa_transferencia": 2, "tasa_descarga": 4, "max_ticks": 5000,
  "obstaculos": {"celdas": [], "regiones": []}
}
```

- La fila `y = 0` es de servicio: bodega en `(0, 0)` y las bases de los agentes; el campo son las filas `y ≥ 1`.
- Las tasas son unidades de grano por tick: transferir o descargar `q` unidades dura `ceil(q / tasa)` ticks.
- `cargar_config` valida todo y falla con un mensaje claro (capacidades, ancho mínimo, enteros positivos…).
- Por ahora se acepta **una** cosechadora y **un** carro, y los obstáculos se validan pero deben ir vacíos (la simulación aún no los recorre). Las métricas y gráficas ya funcionan con cualquier número de agentes.

---

## Pruebas y CI

```bash
pytest                                                    # 230 pruebas
pytest tests/test_integracion.py                          # corridas completas de los 3 escenarios
pytest tests/test_mundo.py::test_serpentina_cubre_todo_el_campo
```

| Archivo | Qué prueba |
|---|---|
| `test_config.py`, `test_mundo.py`, `test_rutas.py` | Configuración, layout, serpentina, reglas físicas y rutas |
| `test_mensajes.py`, `test_cosechadora.py`, `test_carro.py` | Buzón y máquinas de estados de los agentes |
| `test_integracion.py` | R1–R9, terminación, mensajes, checksums y reproducibilidad sobre las corridas reales |
| `test_trace.py`, `test_metricas.py`, `test_campo.py`, `test_validador.py`, `test_generador.py`, `test_experimentos.py`, `test_plots.py` | Log, métricas, campo, validador, experimentos y gráficas |
| `test_viewer.py`, `test_dashboard.py` | Visor y dashboard sin ventana |

GitHub Actions (`.github/workflows/ci.yml`) corre `pytest` con Python 3.12 en cada push y pull request a `main`, `development` y las ramas personales.

---

## Estructura del repositorio

```
config/                  escenarios A, B y C; experimentos en config/experimentos/
src/harvest_sim/
├── config.py            carga y validación de la configuración
├── mundo.py             grid, bodega, bases, serpentina, grano y eventos del mundo
├── rutas.py             BFS, celda objetivo y resolución de conflictos
├── mensajes.py          tipos de mensaje y buzón
├── cosechadora.py       máquina de estados de la cosechadora
├── carro.py             máquina de estados del carro
├── simulacion.py        bucle de ticks y armado del trace
├── cli.py               python -m harvest_sim.cli
├── datos/               formato del log, métricas, campo, validador y experimentos
└── telemetria.py        acceso de compatibilidad a datos/
viz/                     viewer.py (visor 2D), plots.py (gráficas), dashboard.py (dashboard HTML)
tools/                   validar_trace.py, correr_experimento.py, generar_trace_ejemplo.py
scripts/                 correr_todos.sh, verificar_instalacion.sh
tests/                   pruebas; tests/fixtures/ con el log de ejemplo
docs/                    documentación (ver abajo)
runs/                    salidas de las corridas (no se versionan)
```

---

## Documentación

| Documento | Para qué |
|---|---|
| [`docs/especificacion_segunda_entrega.md`](docs/especificacion_segunda_entrega.md) | Qué agrega la segunda entrega: varios agentes, obstáculos, subasta, despacho anticipado, aleatoriedad, combustible, costo J, trace 2.2 y servidor |
| [`docs/especificacion_primera_entrega.md`](docs/especificacion_primera_entrega.md) | Qué hace el sistema: mundo, reglas, agentes, mensajes, formato del log, métricas, pruebas y contrato entre módulos |
| [`docs/equipo/README.md`](docs/equipo/README.md) | Contrato de la entrega actual y una guía por persona (la primera entrega, en `docs/equipo/entrega1/`) |
| [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md) | Reparto, cronograma y flujo de git |
| [`docs/decisiones.md`](docs/decisiones.md) | Cada decisión de diseño con sus alternativas |
| [`docs/ontologia.md`](docs/ontologia.md) | Clases de la ontología del curso, performativas y relación con IEEE 1872 / 1872.2 / 1873 / 7007 |
| [`docs/autoevaluacion.md`](docs/autoevaluacion.md) | El proyecto frente a los 8 criterios de la rúbrica |
| `docs/equipo/oswaldo/rutas.md`, `carro.md` | Explicación detallada de las rutas y del carro |

---

## Equipo

| Persona | Parte | Archivos |
|---|---|---|
| Carlos Arias | Mundo: configuración, mundo y simulación | `config.py`, `mundo.py`, `simulacion.py`, `config/escenario_*.json` |
| Oswaldo (StarLord133) | Rutas y carro | `rutas.py`, `carro.py` y sus pruebas |
| Emilio Moreno | Mensajes y cosechadora | `mensajes.py`, `cosechadora.py` y sus pruebas |
| Joel (JoelMEsc) | Datos: log, métricas, gráficas, validador y experimentos; arma el reporte | `datos/`, `viz/plots.py`, `tools/`, `config/experimentos/` y sus pruebas |
| Mario Giovanni (GioMax102) | Interfaz: visor, CLI y dashboard | `viz/viewer.py`, `viz/dashboard.py`, `cli.py` y sus pruebas |
| Ilan Narváez | Calidad: pruebas de integración, CI, scripts y autoevaluación | `test_config.py`, `test_mundo.py`, `test_integracion.py`, `.github/`, `scripts/` |

Flujo de trabajo: ramas personales → `development` por pull request → `main` para la entrega. El contrato entre módulos ([`docs/equipo/README.md`](docs/equipo/README.md) §3) no se cambia sin avisar y anotarlo en [`docs/decisiones.md`](docs/decisiones.md).
