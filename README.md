# harvest_sim — Cosecha multiagente: cosechadoras, carros y el campo real

Reto agrícola multiagente con John Deere · Equipo 3 · TC2008B.

**Carpeta de Drive con evidencias:** [Google Drive](https://drive.google.com/drive/folders/1XX1WP433XIvwLuCjnjkFnRm9IYrBwJON?usp=sharing)

Las **cosechadoras** recorren un campo en cuadrícula en serpentina. Cuando una se llena (o está por llenarse), pide un **carro recolector**, que va hasta ella, recibe el grano y lo lleva a la **bodega**. El tiempo que la cosechadora pasa llena esperando al carro es el **tiempo ocioso**, la métrica principal del reto.

- **Línea base reactiva** (primera entrega): el carro sale solo cuando la cosechadora ya está llena.
- **Estrategias de coordinación** (segunda entrega): subasta Contract Net y despacho anticipado.
- **Campo real** (escenario G): El Pueblito, con su forma, caminos y relieve sacados del KML y del DEM.

La simulación está escrita en Python y produce un log por corrida (`trace.json`). El visor, las métricas, las gráficas, los experimentos y el dashboard **solo leen ese archivo**: la simulación es la única fuente de verdad.

> **Estado (24 de noviembre de 2026): segunda entrega integrada en `development`.** Varios agentes (franjas), obstáculos, rutas en el tiempo con reservas, subasta Contract Net con despacho anticipado, aleatoriedad con semilla, combustible con recargas, restricciones de seguridad registradas, costo J y servidor FastAPI para Unity. Seis escenarios (A–F): A, B y C siguen dando exactamente las métricas de la primera entrega (`tests/test_regresion.py`). **Resultados y respuestas a la retro:** [`docs/resultados_entrega2.md`](docs/resultados_entrega2.md). Qué se construyó: [`docs/especificacion_segunda_entrega.md`](docs/especificacion_segunda_entrega.md). Visualización 3D: [`harvest-simu-visualization`](https://github.com/GioMax102/harvest-simu-visualization).

> **Terreno real (25 de noviembre de 2026).** El escenario **G** simula el cultivo real de **El Pueblito** (Teocaltiche, Jalisco) a partir del KML: 3 lotes, arboleda y caminos en una cuadrícula de 12 m orientada con los surcos, relieve del DEM Copernicus GLO-30 y dos reglas nuevas (R12: nadie sale del predio; R13: los carros no pisan el cultivo en pie). El trace pasa a **2.3** solo cuando hay mapa; A–F no cambian. Resultados: [`docs/resultados_terreno.md`](docs/resultados_terreno.md). Contrato: [`docs/especificacion_terreno.md`](docs/especificacion_terreno.md).

---

## Inicio rápido

Requiere Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

bash scripts/correr_todos.sh     # simula A–G, valida, grafica, corre los experimentos (incluido G) y arma el dashboard
```

Al terminar, abre **`runs/dashboard.html`** en el navegador: junta el entorno, los indicadores y los experimentos de A–G en una sola página. La corrida completa tarda unos 2.5 minutos con 24 núcleos; casi todo es de los experimentos de 20 seeds, que se reparten entre los núcleos disponibles.

Para comprobar que todo funciona desde cero en una carpeta limpia (crea un entorno virtual temporal, instala, corre `pytest` y `correr_todos.sh`):

```bash
bash scripts/verificar_instalacion.sh
```

La simulación es **reproducible**: el mismo escenario con la misma `seed` produce siempre el mismo `trace.json`, byte a byte. Para Unity, levanta el servidor con `bash scripts/servidor.sh` (http://127.0.0.1:8000, documentación en `/docs`).

Otras formas de correr las estrategias y el campo real:

```bash
python -m harvest_sim.cli config/escenario_e.json --estrategia anticipada_plus --seed 3
python -m harvest_sim.cli config/escenario_g.json --estrategia anticipada_plus               # campo real (trace 2.3), ~25 s
python tools/correr_experimento.py config/experimentos/estrategias.json --procesos 8   # D, E, F × 4 estrategias × 20 seeds
python tools/correr_experimento.py config/experimentos/terreno_g_estrategias.json --procesos 8   # G (campo real) × 4 estrategias × 20 seeds
python tools/verificar_terreno.py                                                       # reglas R10, R12 y R13 en G desde el trace
python tools/kml_a_mapa.py --figura                                                     # regenera config/mapas/el_pueblito.json desde el KML
```

---

## Resultados

**Terreno real, escenario G** (detalle en [`docs/resultados_terreno.md`](docs/resultados_terreno.md)): en El Pueblito el despacho anticipado baja el ocio de las cosechadoras un 52 % (55 % con `anticipada_plus`) y el costo J un 28 %, porque los traslados desde la bodega son largos. Respetar el cultivo en pie (R13) cuesta entre 1.4 % y 2.2 % más de tiempo, y evita que los carros con despacho anticipado pasen hasta 864 m sobre maíz sin cosechar. El relieve (pendiente media de 1.5 %) sube el combustible un 1.6 % con el factor por defecto. 340 corridas; con R13, 0 colisiones, 0 salidas del predio y 0 m de carro sobre cultivo.

**Segunda entrega** (detalle, IC 95 % y figuras en [`docs/resultados_entrega2.md`](docs/resultados_entrega2.md)): en D y E, atender desde la bodega y encadenar servicios (`anticipada_plus`) baja el ocio de las cosechadoras entre 36 % y 40 % y el costo J entre 31 % y 36 %; el umbral de aviso por sí solo apenas cambia el ocio (−1 %); la capacidad del carro solo importa cuando la política la usa; y en F (combustible escaso e incertidumbre) la línea base le gana a la subasta. 640 corridas sin colisiones ni bloqueos.

**Línea base (primera entrega).** Con los escenarios A, B y C (generados con `bash scripts/correr_todos.sh`; la tabla completa queda en `runs/comparacion/resumen.md`):

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
                                 ├─ Mundo (grid o mapa real, bodega, bases, zonas, grano, combustible)
                                 ├─ Cosechadora y Carro (máquinas de estados)
                                 ├─ rutas.py (BFS y rutas en el tiempo con reservas)
                                 └─ Buzon (LLENA, subasta Contract Net, TRANSFERENCIA_TERMINADA)
                                 │
                                 ▼  TraceBuilder (harvest_sim/datos)
                       runs/escenario_X/trace.json   ◄── único contrato entre módulos
                                 │
       ┌─────────────┬───────────┼──────────────┬──────────────────┐
       ▼             ▼           ▼              ▼                  ▼
  validar_trace   métricas    gráficas     experimentos       visor 2D y dashboard
```

- **Cada tick:** se entregan los mensajes del tick anterior, actúa la cosechadora, actúa el carro y se registra lo que cambió. Un mensaje enviado en `t` se lee en `t+1`.
- **El log** guarda solo cambios: posición, estado, carga y combustible de cada agente, celdas cosechadas, depósitos, bloqueos, restricciones y mensajes, cada uno con su acto comunicativo (`LLENA` es una petición, `PROPUESTA` una oferta, `TRANSFERENCIA_TERMINADA` un aviso). Cada tick lleva un checksum.
  - A–F escriben el formato **2.2**.
  - G, que trae mapa, escribe el **2.3**: caminos, fuera de campo, lotes, relieve y formas reales.
  - El validador acepta 2.1, 2.2 y 2.3.
- **Reglas R1–R13.** Dentro del mapa, un paso por tick, nunca dos agentes en la misma celda, transferencia solo entre vecinos, conservación del grano, obstáculos (R10), combustible nunca negativo (R11), nadie fuera del predio (R12) y carros fuera del cultivo en pie (R13). Las pruebas de mundo y de integración las verifican en cada tick de las corridas reales.

El detalle está en las especificaciones ([primera entrega](docs/especificacion_primera_entrega.md), [segunda entrega](docs/especificacion_segunda_entrega.md) y [terreno](docs/especificacion_terreno.md)) y en [`docs/ontologia.md`](docs/ontologia.md).

---

## Uso paso a paso

### Simular un escenario

```bash
python -m harvest_sim.cli config/escenario_a.json                 # runs/escenario_a/trace.json y sus gráficas
python -m harvest_sim.cli config/escenario_a.json --sin-plots     # solo el trace
python -m harvest_sim.cli config/escenario_a.json --silencioso    # sin el log de consola (--detallado: todo)
python -m harvest_sim.cli config/escenario_a.json --salida otra/carpeta
python -m harvest_sim.cli config/escenario_g.json --estrategia anticipada --seed 0   # campo real; también --estrategia base, subasta, anticipada_plus
```

En la consola se imprime lo que pasa (cambios de estado, mensajes y depósitos), por ejemplo `t=013 | MSG #1 LLENA cosechadora_1 -> carro_1 {x: 6, y: 2, carga: 10} (se entrega en t=014)`. Si algo falla, la CLI termina con código 1 y el error en `stderr`.

### Ver una corrida en 2D

```bash
python viz/viewer.py runs/escenario_a/trace.json
python viz/viewer.py runs/escenario_a/trace.json --guardar-cuadros runs/escenario_a/cuadros --cada 10   # PNG sin ventana
python viz/viewer.py runs/escenario_g/trace.json      # campo real: caminos, fuera del predio y obstáculos del mapa
```

El campo real en 3D (relieve, caminos y contornos de los lotes) se ve en Unity: [`harvest-simu-visualization`](https://github.com/GioMax102/harvest-simu-visualization). Para pasarle traces, usa `python tools/exportar_traces_unity.py <Assets/Data/Traces>`, que corre todos los escenarios de `config/` (incluido G), los valida y los copia.

Controles: `Espacio` pausa y reanuda, flechas avanzan o retroceden un tick, `Inicio` / `Fin` van a los extremos, `+` / `-` cambian la velocidad, `Esc` sale.

### Dashboard

```bash
python viz/dashboard.py runs/escenario_{a,b,c,d,e,f,g} --salida runs/dashboard.html
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
python viz/plots.py runs/escenario_g/trace.json --sin-comparacion          # solo las gráficas del trace, sin tocar runs/comparacion
```

La comparación entre escenarios acepta hasta 6 (A–F). G dura unas 10 veces más, así que `correr_todos.sh` le hace solo sus gráficas propias.

| Archivo | Pregunta que responde |
|---|---|
| `runs/<escenario>/plots/1_linea_de_tiempo_estados.png` | ¿Qué hace cada agente en cada tick? |
| `2_ocioso_acumulado.png` | ¿Cuánto ha esperado la cosechadora hasta ahora? |
| `3_distancia_cosechadora_carro.png` | ¿Qué tan lejos está el carro? |
| `4_flujo_del_grano.png` | ¿Cuánto grano llegó a la bodega y cuánto va en camino? |
| `7_combustible.png` | ¿Cuánto combustible le queda a cada agente? (solo traces 2.2 y 2.3) |
| `5_mapa_espera.png`, `6_mapa_trafico.png` | ¿Dónde espera la cosechadora? ¿Por dónde pasan los agentes? |
| `runs/comparacion/comparacion_escenarios.png` | ¿Cómo se comparan los escenarios (6 indicadores)? |
| `runs/comparacion/resumen.csv`, `resumen.md` | Todas las métricas (CSV) y las principales (Markdown) |

### Experimentos (barrido de parámetros)

```bash
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
python tools/correr_experimento.py config/experimentos/estrategias.json --procesos 8
```

| Experimento | Qué compara |
|---|---|
| `tasa_transferencia.json` | A, B y C con tasas de transferencia de 1 a 5 (primera entrega) |
| `estrategias.json` | D, E y F × 4 estrategias × 20 seeds (principal de la segunda entrega) |
| `estrategias_incertidumbre.json` | D con incertidumbre × 4 estrategias × 20 seeds |
| `umbral_aviso.json`, `capacidad_carro.json` | Umbral de aviso y capacidad del carro en D |
| `terreno_g_estrategias.json` | G (campo real) × 4 estrategias × 20 seeds |
| `terreno_g_pendiente.json` | G con el factor de pendiente de 0 a 8 |
| `terreno_g_r13.json` | G con R13 contra G sin R13 (compactación del suelo) |
| `m1_despacho.json`, `m1_despacho_incertidumbre.json` | Despacho aprendido (Q-learning y SARSA) contra el umbral fijo y la subasta, en D y G (M1) |

Un experimento es un JSON en `config/experimentos/` con estos campos:
- los escenarios;
- las estrategias (opcional);
- el barrido, `{"parámetro": [valores]}`; una clave con punto entra a una sección, como `"politica.respetar_cultivo"`;
- las seeds o las repeticiones;
- la métrica a graficar.

Escribe en `runs/experimentos/<nombre>/`:
- `resultados.csv`: una fila por corrida;
- `resumen.csv`: media, desviación estándar e intervalo de confianza del 95 %;
- con estrategias, `comparacion.csv` (pareada contra `base`) y `ablacion.csv` (costo J);
- las gráficas de sensibilidad y de estrategias.

Con `"referencia": "<estrategia>"`, la comparación pareada se hace contra esa estrategia en vez de `base`. Sin incertidumbre (A–E y G), todas las seeds dan lo mismo y el resumen lo indica («sin variación»).

### Mejoras: despacho aprendido (M1)

```bash
python tools/entrenar_despacho.py config/escenario_g.json --algoritmo qlearning --episodios 60   # config/aprendizaje/qtabla_qlearning_escenario_g.json
python -m harvest_sim.cli config/escenario_g.json --estrategia qlearning                         # corre con la tabla, sin explorar
```

En Unity se ven las decisiones (placa «Q: pide carro» y tarjeta con el estado y los valores Q); los traces de ejemplo están en `harvest-simu-visualization/Assets/Data/Traces/mejoras/`. En vez de pedir carro al pasar un umbral fijo, la cosechadora consulta una tabla Q aprendida (Q-learning o SARSA escritos por el equipo, con estados, acciones, recompensas y cliff). Está desactivada por defecto. Formulación: [`docs/especificacion_mejoras.md`](docs/especificacion_mejoras.md). Resultados: [`docs/resultados_mejoras.md`](docs/resultados_mejoras.md).

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

- **Sin mapa (A–F):**
  - la fila `y = 0` es de servicio: bodega en `(0, 0)` y las bases de los agentes;
  - el campo son las filas `y ≥ 1`, menos los obstáculos (`celdas` y `regiones`).
- **Con mapa (G):**
  - `"mapa": "mapas/el_pueblito.json"` trae el tamaño, los obstáculos, los caminos, la bodega, las bases y el relieve;
  - el escenario solo fija los agentes, las capacidades, las tasas y la política (ver `config/escenario_g.json`).
- **Agentes:** cualquier número de cosechadoras y carros (`num_cosechadoras`, `num_carros`); cada cosechadora cosecha su franja o zona.
- **Tasas:** son unidades de grano por tick; transferir o descargar `q` unidades dura `ceil(q / tasa)` ticks.
- **Secciones opcionales.** Cada una tiene valores por defecto que reproducen la línea base:
  - `politica`: `asignacion` directa o subasta, `umbral_aviso`, `atender_desde_bodega`, `encadenar_servicios`, `respetar_cultivo`, y `aviso` y `qtabla` (M1, despacho aprendido);
  - `incertidumbre`: rendimiento por celda, duración extra y retraso de mensajes;
  - `combustible`: tanques, consumos, reserva, recarga y `factor_pendiente`;
  - `costo`: los pesos de J.
- **Estrategias:** `--estrategia` en la CLI aplica una de las 4 de coordinación (`base`, `subasta`, `anticipada`, `anticipada_plus`) sobre la política. También acepta las aprendidas (`qlearning`, `sarsa`), que necesitan una tabla entrenada en `config/aprendizaje/` (ver «Mejoras»).
- **Validación:** `cargar_config` valida todo y falla con un mensaje claro (capacidades, ancho mínimo, enteros positivos, mapa coherente con el escenario…).

---

## Pruebas y CI

```bash
pytest                                                    # 742 pruebas
pytest tests/test_integracion.py                          # corridas completas de A–F (y D, E, F con las 4 estrategias)
pytest tests/test_terreno_integracion.py                  # G completo: R10, R12, R13 y compactación del suelo
python tools/verificar_terreno.py                         # G × 4 estrategias × 20 seeds (~3 min), revisado desde el trace
pytest tests/test_regresion.py                            # A, B y C contra las métricas de v0.1
pytest tests/test_mundo.py::test_serpentina_cubre_todo_el_campo
```

| Archivo | Qué prueba |
|---|---|
| `test_config.py`, `test_mundo.py`, `test_rutas.py` | Configuración, layout, serpentina, reglas físicas y rutas |
| `test_mensajes.py`, `test_cosechadora.py`, `test_carro.py` | Buzón y máquinas de estados de los agentes |
| `test_integracion.py` | R1–R11, terminación, mensajes y retraso, subasta, pasillo E (4 estrategias × 20 seeds), recargas, checksums y reproducibilidad sobre las corridas reales |
| `test_regresion.py` | A, B y C dan las métricas guardadas de `v0.1-entrega1` |
| `test_cosechadora_subasta.py`, `test_servidor.py` | Cosechadora administradora de la subasta y servidor FastAPI |
| `test_trace.py`, `test_metricas.py`, `test_campo.py`, `test_validador.py`, `test_generador.py`, `test_experimentos.py`, `test_plots.py` | Log, métricas, campo, validador, experimentos y gráficas |
| `test_viewer.py`, `test_dashboard.py` | Visor (2.1, 2.2 y 2.3) y dashboard sin ventana |
| `test_formato_23.py`, `test_mapa.py`, `test_relieve.py` | Trace 2.3, conversión del KML al mapa (área, caminos soldados, red conectada) y relieve del DEM |
| `test_mundo_mapa.py`, `test_terreno_integracion.py` | Mundo con mapa (R12, R13, zonas, bodega y bases del mapa) y corrida completa de G |
| `test_exportar_unity.py` | Exportación de traces para Unity |
| `test_aprendizaje.py` | Despacho aprendido (M1): estado, Q-learning contra SARSA, cliff, respaldo del umbral, tablas y reproducibilidad |

GitHub Actions (`.github/workflows/ci.yml`) corre `pytest` con Python 3.12 en cada push y pull request a `main`, `development` y las ramas personales.

---

## Estructura del repositorio

```
config/                  escenarios A–G; experimentos en config/experimentos/; mapas reales en config/mapas/ (KML, JSON y DEM);
                         tablas Q entrenadas en config/aprendizaje/
src/harvest_sim/
├── config.py            carga y validación de la configuración
├── mundo.py             grid, bodega, bases, serpentina, grano y eventos del mundo
├── rutas.py             BFS, celda objetivo y resolución de conflictos
├── mensajes.py          tipos de mensaje y buzón
├── cosechadora.py       máquina de estados de la cosechadora
├── carro.py             máquina de estados del carro
├── agente.py            base común de los agentes
├── simulacion.py        bucle de ticks y armado del trace
├── cli.py               python -m harvest_sim.cli
├── servidor.py          API FastAPI para Unity (scripts/servidor.sh)
├── aprendizaje.py       despacho aprendido (M1): Q-learning y SARSA tabulares
├── mapa/                KML a mapa: kml.py, pasadas.py, convertir.py y relieve.py (DEM)
├── datos/               formato del log (2.1–2.3), métricas, campo, validador, tablas y experimentos
└── telemetria.py        acceso de compatibilidad a datos/
viz/                     viewer.py (visor 2D), plots.py (gráficas), dashboard.py (dashboard HTML)
tools/                   validar_trace.py, correr_experimento.py, verificar_terreno.py, kml_a_mapa.py, entrenar_despacho.py,
                         exportar_traces_unity.py, generar_trace_ejemplo.py, traces_ejemplo_22.py, traces_ejemplo_23.py
scripts/                 correr_todos.sh, verificar_instalacion.sh, servidor.sh
tests/                   pruebas; tests/fixtures/ con los logs de ejemplo (2.1, 2.2 y 2.3)
docs/                    documentación (ver abajo)
runs/                    salidas de las corridas (no se versionan)
```

---

## Documentación

| Documento | Para qué |
|---|---|
| [`docs/temas_del_curso.md`](docs/temas_del_curso.md) | Cada tema del curso TC2008B (multiagentes y gráficas): dónde se usa, cómo y con qué resultado; lo que falta |
| [`docs/resultados_terreno.md`](docs/resultados_terreno.md) | Resultados del campo real (escenario G): estrategias, factor de pendiente, R13 y compactación del suelo |
| [`docs/especificacion_terreno.md`](docs/especificacion_terreno.md) | Terreno real: KML a mapa, trace 2.3, reglas R12 y R13, relieve, zonas, escenario G y Unity |
| [`docs/especificacion_mejoras.md`](docs/especificacion_mejoras.md), [`docs/resultados_mejoras.md`](docs/resultados_mejoras.md) | Mejoras M1–M12: formulación y resultados |
| [`docs/plan_terreno.md`](docs/plan_terreno.md) | Plan del terreno real (P0–P7) y mejoras siguientes (M1–M12), con su estado |
| [`docs/resultados_entrega2.md`](docs/resultados_entrega2.md) | Resultados de la segunda entrega: estrategias, incertidumbre, umbral, capacidad del carro, costo J, respuestas a la retro y limitaciones |
| [`docs/especificacion_segunda_entrega.md`](docs/especificacion_segunda_entrega.md) | Qué agrega la segunda entrega: varios agentes, obstáculos, subasta, despacho anticipado, aleatoriedad, combustible, costo J, trace 2.2 y servidor |
| [`docs/especificacion_primera_entrega.md`](docs/especificacion_primera_entrega.md) | Qué hace el sistema: mundo, reglas, agentes, mensajes, formato del log, métricas, pruebas y contrato entre módulos |
| [`docs/equipo/README.md`](docs/equipo/README.md) | Contrato de la entrega actual y una guía por persona (la primera entrega, en `docs/equipo/entrega1/`) |
| [`docs/plan_de_trabajo.md`](docs/plan_de_trabajo.md) | Reparto, cronograma y flujo de git |
| [`docs/decisiones.md`](docs/decisiones.md) | Cada decisión de diseño con sus alternativas |
| [`docs/ontologia.md`](docs/ontologia.md) | Clases de la ontología del curso, performativas y relación con IEEE 1872 / 1872.2 / 1873 / 7007 |
| [`docs/autoevaluacion.md`](docs/autoevaluacion.md) | El proyecto frente a los 8 criterios de la rúbrica |
| `docs/equipo/oswaldo/rutas.md`, `carro.md` | Explicación detallada de las rutas y del carro |
| `docs/equipo/carlos/mundo.md`, `docs/equipo/emilio/cosechadora.md` | El mundo y la cosechadora de la segunda entrega |

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
