# Plan detallado — Parte de Datos (Joel), segunda entrega

> **Copia versionada, histórica:** el plan de Datos de la segunda entrega (ya entregada). Se guarda como referencia.

> **Fuera del repositorio** (vive en `tc2008b/`). Escrito el 24 de noviembre de 2026. Cada paso dice **qué** hacer, **por qué**, **cómo**, **qué considerar** y **cuándo está listo**, para que lo pueda ejecutar cualquier persona (o agente) con información mínima. **Nada se ejecuta hasta que Joel confirme las decisiones del §2.**

---

## 0. Contexto mínimo

### 0.1 Dónde estamos

- Repositorio `harvest_sim` (GitHub `JoelMEsc/harvest_sim`). La primera entrega está en `main` con la etiqueta `v0.1-entrega1`: 1 cosechadora y 1 carro, línea base reactiva, 230 pruebas.
- La segunda entrega (coordinación multiagente) está **especificada** en `docs/especificacion_segunda_entrega.md` y repartida en `docs/equipo/<persona>/guia.md`. La guía de Joel es `docs/equipo/joel/guia.md`.
- La parte de Datos vive en `src/harvest_sim/datos/` (`formato`, `trace`, `linea_de_tiempo`, `campo`, `metricas`, `validacion`, `experimentos`, `tablas`), más `viz/plots.py` y `tools/`.

### 0.2 Lo que ya hicieron los demás y afecta a Datos (revisado el 24 de noviembre)

| Quién | Rama | Qué hizo | Qué espera de Datos |
|---|---|---|---|
| Oswaldo | `branch-oswaldo-rutas` (2 commits, sin PR) | `bfs_tiempo`, `estimar_costo`, carro contratista | Definió los tipos de mensaje **como texto local en `carro.py`** porque `formato.py` aún no los tiene. Usa `motivo` `"sin_capacidad"`, `"combustible"` y uno extra, **`"sin_ruta"`**. Registra la regla `"combustible_reserva"` y reglas de desvío. Pone `combustible` en el registro solo si el mundo lo inicializó |
| Mario Giovanni | `mario_giovanni_branch` (6 commits, sin PR) | Visor y dashboard que leen 2.1 y 2.2 (combustible, `RECARGA`, `RESTRICCION`); CLI con `--seed` y `--estrategia` | **`datos.experimentos.ESTRATEGIAS`**: la CLI acepta `ESTRATEGIAS[nombre]` como `{"politica": {...}}` o como el dict de la política directamente |
| Carlos, Emilio, Ilan | sin cambios aún | — | Formato 2.2 (Emilio: performativas), regresión contra v0.1 (Ilan) |

**Conclusión:** el formato 2.2 es lo más urgente; destraba a Emilio y le permite a Oswaldo dejar de definir los tipos a mano.

### 0.3 Reglas de trabajo

- Trabajar en `branch-joel`; nunca push directo a `development` ni a `main`. Un commit por paso; push y PR al terminar cada paso marcado ⚡, para que los demás lo usen pronto. El equipo acordó integrar sin revisión.
- Mensajes de commit terminan en `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; descripciones de PR en `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Solo archivos de Datos (`src/harvest_sim/datos/`, `src/harvest_sim/servidor.py`, `viz/plots.py`, `tools/`, `config/experimentos/`, `tests/fixtures/`, pruebas de Datos, `requirements.txt` para el servidor) y `docs/decisiones.md`. Los documentos personales (`docs/guia_joel_datos.md`, `docs/plan_personal.md`) no se commitean.
- Entorno: `python3 -m venv <carpeta> && <carpeta>/bin/pip install -r requirements.txt && <carpeta>/bin/pip install -e .`; pruebas con `SDL_VIDEODRIVER=dummy <carpeta>/bin/python -m pytest -q`.
- **Regla de oro de la entrega:** con la configuración por defecto, A, B y C dan las mismas métricas que v0.1. Ninguna métrica existente cambia de nombre ni de valor.

---

## 1. Qué se entrega de Datos (resumen)

| # | Entregable | Destraba a | Paso |
|---|---|---|---|
| 1 | Formato 2.2: vocabulario, `TraceBuilder` y validador ⚡ | Emilio, Oswaldo, Carlos, Mario Giovanni, Ilan | 1 |
| 2 | Traces de ejemplo 2.2 (2 + 2 agentes, subasta, recarga, restricción) ⚡ | Mario Giovanni (Unity, visor), Ilan | 2 |
| 3 | `ESTRATEGIAS` y experimentos por estrategia ⚡ (lo pide la CLI) | Mario Giovanni (CLI), Ilan (scripts) | 4 |
| 4 | Métricas: combustible, restricciones, subasta, costo J | Reporte | 3 |
| 5 | Comparación pareada contra la línea base con IC 95 % | Reporte | 4 |
| 6 | Gráficas de la entrega | Dashboard, reporte | 5 |
| 7 | Servidor FastAPI ⚡ | Mario Giovanni (Unity) | 6 |
| 8 | Exportar traces a Unity | Mario Giovanni | 7 |
| 9 | Corridas reales, experimento completo y reporte | Entrega | 9 y 10 |

---

## 2. Decisiones que Joel debe confirmar

| # | Decisión | Recomendación | Por qué |
|---|---|---|---|
| D1 | **Forma de `ESTRATEGIAS`**: `{"base": {"politica": {...}}, ...}` | Sí | La CLI de Mario Giovanni ya acepta esa forma, y deja espacio para que una estrategia cambie algo fuera de la política |
| D2 | **Comparación pareada por seed:** para cada métrica, diferencia estrategia − base seed por seed, con media e IC 95 % de esas diferencias (t de Student) | Sí | Ambas corren con las mismas seeds: emparejar elimina la variación del escenario y da intervalos más angostos. Se marca «mejora» solo si el IC no cruza el 0 |
| D3 | **Validación de los payloads de mensajes** (claves obligatorias por tipo) como **error** en 2.2 | Sí | Es parte del contrato de la subasta; si falta `servicio` o `costo`, las métricas de subasta no se pueden calcular |
| D4 | **Regla o motivo desconocido** en `RESTRICCION` o `RECHAZO` → **aviso**, no error | Sí | Oswaldo ya usa `"sin_ruta"` y reglas de desvío; los avisos no bloquean a nadie y se agregan a la lista después |
| D5 | **Traces de ejemplo 2.2 armados a mano** (un guion, como el de las pruebas), no extendiendo el generador | Sí | Extender el generador duplicaría la subasta y las rutas (lógica de otros roles). Un guion pequeño y validado basta para Unity y para probar el formato |
| D6 | **Fixture actual** (`trace_ejemplo.json`, 1 + 1) se conserva para las pruebas con valores a mano; se **agrega** una corrida corta real cuando exista la simulación | Sí | Cambiar el fixture obliga a recalcular a mano todas las pruebas; la corrida real se agrega como prueba de humo |
| D7 | **Gráfica nueva por corrida:** nivel de combustible de cada agente con las recargas marcadas (`7_combustible.png`) | Sí | Muestra la métrica de sostenibilidad y la reserva; las demás gráficas no cambian |
| D8 | **Dependencias del servidor:** `fastapi`, `uvicorn` y `httpx` (este solo para `TestClient`) con versión fija, verificada al instalar | Sí | Sin versión fija no hay reproducibilidad; `httpx` es lo que usa `TestClient` |
| D9 | **Servidor con simulador inyectable** (`crear_app(simulador=...)`) | Sí | Se prueba y lo usa Unity desde ya con traces de ejemplo, sin esperar la simulación completa |

---

## 3. Explicaciones

### 3.1 Qué cambia del log (2.1 → 2.2)

Solo se **agregan** campos (especificación §12). Un trace 2.1 sigue siendo válido y todas las métricas viejas se calculan igual:

| Nuevo | Detalle |
|---|---|
| `AGENTE.set.combustible` | número ≥ 0, opcional (solo si el mundo lo inicializa) |
| `CELDA_COSECHADA.cantidad` | entero ≥ 1, obligatorio en 2.2 |
| `mundo.rendimiento` | opcional: matriz alto × ancho; 0 en servicio y obstáculos |
| `RECARGA` | `agente`, `cantidad`, `nivel` |
| `RESTRICCION` | `agente`, `regla`, `detalle` |
| Mensajes | 7 tipos con su performativa; `entrega_en` hasta `t + 1 + retraso máximo` |

### 3.2 La comparación pareada (D2), con un ejemplo

Con 20 seeds, la estrategia `anticipada` y la `base` corren cada seed en el mismo mapa. Para cada seed se resta: ocio(anticipada) − ocio(base). Con esas 20 diferencias se calcula la media y el IC 95 % (t con 19 grados de libertad). Si el intervalo es, por ejemplo, [−22; −15] ticks, la anticipada reduce el ocio entre 15 y 22 ticks con 95 % de confianza. Si el intervalo cruza el 0, la diferencia no es concluyente. El sentido de cada métrica (menor o mayor es mejor) se recupera del commit `458e39d` (decisión del 2026-11-16).

### 3.3 El costo J

`J = λT·completación + λD·distancia + λC·colisiones + λW·ocio_total + λF·combustible_usado + λR·restricciones`. Los pesos vienen de `config.costo.pesos` del trace (con valores por defecto si no existen). Las métricas reportan cada término `λ·x` y el total. La **ablación** se hace en los experimentos: se recalcula J con cada peso en 0 y se revisa si cambia el orden de las estrategias.

---

## 4. Pasos

Orden: 1 → 2 → 4 (primera parte, `ESTRATEGIAS`) → 6 → 3 → 4 (resto) → 5 → 7 → 8; los pasos 9 y 10 esperan a la simulación completa. Cada paso termina con pruebas en verde y su commit.

### Paso 1 — Formato 2.2 ⚡

- **Objetivo:** que el contrato 2.2 exista en código: vocabulario, `TraceBuilder` y validador.
- **Por qué:** Emilio necesita las performativas; Oswaldo, los tipos; Carlos, saber qué eventos generar; Mario Giovanni e Ilan, un validador que acepte 2.2.
- **Cómo:**
  1. `datos/formato.py`:
     - `SCHEMA_VERSION = "2.2"` y `VERSIONES_ACEPTADAS = ("2.1", "2.2")`.
     - Constantes de los 7 tipos de mensaje (`SOLICITUD_SERVICIO`, `PROPUESTA`, `RECHAZO`, `ACEPTACION`, `RECHAZO_PROPUESTA`, `LLENA`, `TRANSFERENCIA_TERMINADA`) y `PERFORMATIVAS` con `cfp`, `propose`, `refuse`, `accept-proposal`, `reject-proposal`, `request`, `inform`; `PERFORMATIVAS_VALIDAS` con las 7.
     - `PAYLOAD_POR_TIPO`: claves obligatorias de cada mensaje (`SOLICITUD_SERVICIO`: servicio, x, y, carga, capacidad; `PROPUESTA`: servicio, costo; `RECHAZO`: servicio, motivo; `ACEPTACION` y `RECHAZO_PROPUESTA`: servicio; `LLENA`: x, y, carga; `TRANSFERENCIA_TERMINADA`: cantidad).
     - `MOTIVOS_RECHAZO = ("sin_capacidad", "combustible", "sin_ruta")` y `REGLAS_RESTRICCION = ("R3_celda_ocupada", "R4_intercambio", "R9_bodega", "R10_obstaculo", "combustible_reserva")`.
     - Eventos nuevos en `CATEGORIA` (categoría 2) y `CAMPOS_EVENTO` (`RECARGA`: agente texto, cantidad número, nivel número; `RESTRICCION`: agente, regla y detalle, texto). `CELDA_COSECHADA.cantidad` como campo **opcional en 2.1 y obligatorio en 2.2**.
     - `CAMPOS_AGENTE = ("pose", "estado", "carga", "combustible")`.
  2. `datos/trace.py` (`TraceBuilder.agregar_tick`): incluir `combustible` en la comparación **solo si viene en el registro** (`r.get("combustible")`), redondeado a 2 decimales. Un registro sin combustible produce exactamente lo mismo que hoy (regresión).
  3. `datos/validacion.py`:
     - Aceptar las versiones de `VERSIONES_ACEPTADAS`.
     - Números (`combustible`, `cantidad` de `RECARGA`, `nivel`): int o float, sin bool, ≥ 0.
     - Payload: claves obligatorias por tipo (error, D3).
     - `motivo` y `regla` desconocidos: aviso (D4).
     - `retraso_maximo` por defecto = `config.incertidumbre.retraso_mensajes.maximo + 1` si el trace lo trae; si no, 1. El parámetro explícito sigue ganando.
     - `mundo.rendimiento`: matriz alto × ancho de enteros ≥ 0; > 0 en el campo y 0 en servicio y obstáculos.
     - Si existe `config.combustible`, `combustible ≤ tanque` de su tipo.
     - `CELDA_COSECHADA.cantidad`, si `mundo.rendimiento` existe, debe coincidir con el rendimiento de esa celda.
  4. `datos/campo.py`: `grano_esperado` suma `mundo.rendimiento` sobre las celdas de campo si existe; si no, celdas × `grano_por_celda` (igual que hoy).
  5. `tools/generar_trace_ejemplo.py`: agrega `cantidad` a cada `CELDA_COSECHADA` y regenera el fixture y los escenarios de ejemplo (siguen siendo 1 + 1, sin combustible). Actualiza la prueba de bytes idénticos.
- **Considerar:** Oswaldo y Emilio comparan los tipos como texto; mantener exactamente esos textos. `PERFORMATIVAS[tipo]` es lo que Emilio importa en el buzón.
- **Pruebas nuevas** (en `test_validador.py`, `test_trace.py`, `test_campo.py`):
  - Un trace 2.1 sigue válido; un 2.2 sin `cantidad` falla.
  - Payload sin `costo` falla; `motivo` y `regla` desconocidos dan aviso, no error.
  - Combustible negativo o mayor que el tanque falla.
  - Retraso dentro y fuera del máximo tomado de la configuración.
  - Rendimiento con dimensiones malas, con valor > 0 en un obstáculo, o con `cantidad` distinta a la de su celda: falla.
  - `grano_esperado` con rendimiento variable, calculado a mano.
  - `TraceBuilder` con y sin `combustible`: sin él, idéntico a hoy.
- **Listo cuando:** pasan todas las pruebas (las 230 de antes más las nuevas) y el fixture regenerado valida.
- **Commit:** `Formato 2.2: mensajes de la subasta, combustible, recargas, restricciones y rendimiento`. **PR y fusión en cuanto pase**, y aviso a Emilio y Oswaldo de que importen los tipos y las performativas desde `datos.formato`.

### Paso 2 — Traces de ejemplo 2.2 ⚡

- **Objetivo:** traces 2.2 válidos que muestren todo lo nuevo, para Unity, el visor y las pruebas, antes de que exista la simulación.
- **Por qué:** Mario Giovanni ya lee 2.2, pero no tiene con qué probar la subasta, las recargas ni varios agentes.
- **Cómo:** `tools/traces_ejemplo_22.py`, con un guion escrito a mano (como `tests/ayuda_datos.trace_a_mano`, pero con mensajes y eventos) en un mapa de 8 × 6 con un obstáculo:
  - 2 cosechadoras y 2 carros, unos 40 ticks.
  - Una subasta completa: cfp a los dos carros, dos propuestas, una aceptación y un rechazo de propuesta.
  - Una subasta con un `RECHAZO` por combustible y su `RESTRICCION`.
  - Una `RECARGA` en la base; un mensaje con retraso (`entrega_en = t + 2`).
  - Un desvío alrededor del obstáculo con `R10_obstaculo`.
  - `mundo.rendimiento` variable y `combustible` en cada agente.

  Escribe `tests/fixtures/trace_ejemplo_22.json` y, con `--salida`, una copia en otra carpeta.
- **Considerar:** es un guion, no una simulación: no tiene que ser óptimo, solo **válido** (validador sin errores), coherente (R1–R11, conservación del grano) y determinista.
- **Pruebas:** el trace valida; las métricas nuevas del paso 3 se calculan a mano sobre él (es su principal caso de prueba).
- **Listo cuando:** valida, el visor de Mario Giovanni lo abre y está en el PR.
- **Commit:** `Traces de ejemplo 2.2 con dos cosechadoras, dos carros, subasta, recargas y restricciones`.

### Paso 3 — Métricas nuevas

- **Objetivo:** medir combustible, restricciones, subasta y costo J sin cambiar ninguna métrica existente.
- **Cómo** (`datos/metricas.py`, todo desde la línea de tiempo):
  1. `linea_de_tiempo.py`: seguir `combustible` por agente y tick (None si no hay), y la cantidad cosechada por tick (`cantidad` o, en 2.1, `grano_por_celda`).
  2. **Combustible** (solo si el trace tiene `combustible`):
     - `combustible_usado`: suma de las bajadas entre ticks.
     - `combustible_comprado`: tanque inicial (de `config.combustible`) más la suma de `RECARGA.cantidad`.
     - `recargas` y `combustible_minimo`.

     Por agente en `por_agente`; en el nivel superior, totales (es un consumo del sistema).
  3. **Restricciones:** `restricciones` (total) y `restricciones_por_regla`; por agente en `por_agente`.
  4. **Subasta** (solo si hay `SOLICITUD_SERVICIO`):
     - `servicios`, `propuestas_por_servicio` (media), `rechazos_por_motivo`.
     - `respuesta_promedio`: ticks desde la primera llamada de un servicio hasta que empieza su transferencia (la cosechadora pasa a `TRANSFIRIENDO`).
     - `servicios_por_carro` en `por_agente`.
  5. **Grano:** `grano_cosechado_total` suma `cantidad` (en 2.1 es igual que hoy).
  6. **Costo J:** `costo` = `{"terminos": {nombre: λ·x}, "pesos": {...}, "total": J}`, con `ocio_total` = suma del ocio de todas las cosechadoras y `combustible_usado` total (0 si no hay). Pesos de `trace["config"]["costo"]["pesos"]` o los por defecto de la especificación §2.
  7. Las claves nuevas van **al final**, en este orden, para que las pruebas existentes (que comparan el orden) solo necesiten agregar claves.
- **Considerar:**
  - En un trace sin combustible ni subasta, las claves nuevas valen `None` o están vacías; las viejas no cambian (la regresión de Ilan compara solo las de v0.1).
  - `tiempo_ocioso_cosechadora` sigue siendo el promedio por cosechadora; J usa el total.
- **Pruebas:** todas con valores a mano sobre el trace de ejemplo 2.2 (paso 2) y sobre guiones pequeños con `trace_a_mano`; el fixture 2.1 da las mismas métricas viejas que hoy.
- **Listo cuando:** pasan las pruebas y `docs/decisiones.md` tiene la definición de cada métrica nueva y de J.
- **Commit:** `Métricas de combustible, restricciones y subasta, y costo J descompuesto`.

### Paso 4 — Estrategias, experimentos y comparación pareada

- **Parte A ⚡ (corta, la necesita la CLI):** `ESTRATEGIAS` en `datos/experimentos.py`, con la forma de D1 y los valores de la especificación §2, y `aplicar_estrategia(config: dict, nombre) -> dict` (mezcla profunda sobre `config["politica"]`, que puede no existir). PR en cuanto pase, y aviso a Mario Giovanni.
- **Parte B:**
  1. JSON de experimento con `"estrategias": [...]` y `"seeds": {"desde": 0, "cantidad": 20}` (sigue aceptando `repeticiones`). `correr_experimento` recorre escenario × estrategia × barrido × seed; cada fila lleva `estrategia`.
  2. Barrido con claves con punto (`"politica.umbral_aviso": [0.5, 0.6, …, 1.0]`) para parámetros dentro de secciones.
  3. `resumen_por_grupo` agrupa también por `estrategia`; se agregan columnas de J y de combustible.
  4. **Comparación pareada** (D2): `comparar_contra_base(filas, metricas) -> list[dict]`. Por escenario, estrategia y métrica: media base, media estrategia, diferencia media, IC 95 % pareado, cambio % y veredicto (mejora / empeora / no concluyente / informativa) con el sentido de cada métrica, recuperado de `458e39d` y ampliado con las métricas nuevas.
  5. **Ablación de J:** `ablacion_costo(filas)`: para cada término, el orden de las estrategias por J medio con ese peso en 0, y si cambia respecto al orden con todos los pesos.
  6. `config/experimentos/estrategias.json` (D, E, F × 4 estrategias × 20 seeds) y `config/experimentos/umbral_aviso.json` (D con `anticipada`, umbral de 0.5 a 1.0, 20 seeds).
  7. `tools/correr_experimento.py`: escribe además `comparacion.csv` y `ablacion.csv`; opción `--procesos N` (con `concurrent.futures`) si 240 corridas tardan demasiado; el orden de las filas no depende del paralelismo.
- **Considerar:** el simulador de ejemplo no entiende las estrategias; las pruebas de la parte B usan un simulador falso que devuelve métricas conocidas por seed y estrategia, para calcular a mano la comparación pareada.
- **Pruebas:** `aplicar_estrategia` (con y sin política previa); filas por estrategia; IC pareado calculado a mano (por ejemplo, diferencias 2, 4, 6 dan media 4 e IC 4 ± 4.97); veredicto con IC que cruza el 0; ablación con un caso donde un término cambia el orden.
- **Listo cuando:** el experimento corre con el simulador falso y produce `resultados.csv`, `resumen.csv`, `comparacion.csv` y `ablacion.csv` correctos.
- **Commits:** `Estrategias de la segunda entrega` (parte A) y `Experimentos por estrategia, comparación pareada contra la línea base y ablación de J` (parte B).

### Paso 5 — Gráficas

- **Por corrida:** `7_combustible.png`, el nivel de cada agente en el tiempo con línea de reserva y las recargas marcadas (D7). Las otras 6 ya funcionan con N agentes; verificar a ojo con el trace de ejemplo 2.2 (por ejemplo, la línea de tiempo con 4 filas).
- **Por experimento:**
  1. Barras por estrategia con IC 95 % (ocio total, completación, combustible usado, J), un panel por métrica y un color fijo por estrategia.
  2. J apilado por término y estrategia.
  3. Diferencia contra la base con su IC (gráfico de puntos con barras de error y línea en 0).
  4. Sensibilidad al `umbral_aviso` (la gráfica de sensibilidad actual, con su IC).
- **Considerar:** guía de visualización ya usada (paleta validada, títulos, unidades, leyendas) y revisión a ojo de cada imagen.
- **Pruebas:** cada función genera un PNG válido con datos falsos; `main` y `correr_experimento` escriben los archivos esperados.
- **Commit:** `Gráficas de combustible y de la comparación de estrategias con IC 95 %`.

### Paso 6 — Servidor FastAPI ⚡

- **Objetivo:** que Unity pida y reciba traces de la simulación de Python.
- **Cómo:** `src/harvest_sim/servidor.py`:
  - `crear_app(simulador=None, carpeta_config=RAIZ/"config") -> FastAPI` y `app = crear_app()` (D9).
  - Rutas de la especificación §14:
    - `GET /api/salud`.
    - `GET /api/escenarios`: nombre y parámetros principales de cada `config/escenario_*.json`.
    - `GET /api/escenarios/{nombre}/trace?seed=&estrategia=`.
    - `POST /api/simulaciones`: configuración completa, o escenario + estrategia + seed + cambios.
  - Valida con `validar_trace` antes de responder: 422 con la lista de errores si el trace o la configuración son inválidos, 404 si el escenario no existe.
  - Caché en memoria por (escenario, estrategia, seed, cambios).
  - CORS para `http://localhost:*` y `http://127.0.0.1:*`.
  - Dependencias en `requirements.txt` con versión fija (D8). Comprobar con `pip install` que las versiones existen e instalan juntas antes de fijarlas.
- **Considerar:**
  - Hasta que exista la simulación, `simulador_real` lanza `NotImplementedError`: responder 503 con un mensaje claro.
  - Un modo `--ejemplo` (variable de entorno `HARVEST_SIMULADOR=ejemplo`) sirve los traces de ejemplo, para que Unity pruebe desde ya.
  - El servidor **no** decide nada: solo corre la simulación y entrega el trace.
- **Pruebas:** `tests/test_servidor.py` con `TestClient` y un simulador falso. Las cuatro rutas, el 404, el 422 (configuración inválida y trace inválido), el 503, la caché (el simulador se llama una sola vez) y las cabeceras CORS.
- **Listo cuando:** `uvicorn harvest_sim.servidor:app` responde y `curl http://127.0.0.1:8000/api/salud` da `{"estado": "ok", "schema_version": "2.2"}`; aviso a Ilan (CI) y a Mario Giovanni (URL y rutas).
- **Commit:** `Servidor FastAPI que corre simulaciones y entrega traces validados`.

### Paso 7 — Exportar traces a Unity

- `tools/exportar_traces_unity.py <carpeta destino> [--escenarios A..F] [--estrategias ...] [--seed N] [--ejemplo]`: corre (o toma los de ejemplo), **valida** y copia los traces con nombres `escenario_x__estrategia__seed.json`.
- **Prueba:** con el simulador de ejemplo escribe archivos válidos en `tmp_path`.
- **Commit:** `Herramienta para exportar traces validados al proyecto de Unity`.

### Paso 8 — Documentos

- `docs/decisiones.md`:
  - Definición de las métricas nuevas y de J, y la comparación pareada.
  - Payloads obligatorios y avisos de motivos o reglas desconocidos.
  - Que los traces de ejemplo son un guion, y el servidor.
- `docs/ontologia.md`: performativas de Contract Net; `RESTRICCION` como *SafetyConstraint* registrada; `RECARGA` y combustible como evidencia de sostenibilidad (IEEE 7007).
- Especificación (`docs/especificacion_segunda_entrega.md` §7, §10 y §12), con la confirmación de Joel: agregar el motivo `"sin_ruta"` y las reglas que use Oswaldo.
- Documentos personales (fuera de git): la guía de Datos y el plan personal, con el estado.
- **Commit:** `Decisiones y ontología de la parte de Datos de la segunda entrega`.

### Paso 9 — Integración (espera la simulación completa)

1. Traer `development` cuando Carlos, Emilio y Oswaldo hayan fusionado.
2. Correr A, B y C por defecto y comparar contra v0.1 (la prueba de Ilan). Si algo de Datos difiere, se corrige antes de seguir.
3. Correr D, E y F con las 4 estrategias y validar; revisar a ojo las gráficas y el trace de E (0 colisiones, 0 `BLOQUEO`).
4. Agregar `tests/fixtures/trace_real_corto.json` (D6) con una prueba de humo.
5. Correr `estrategias.json` y `umbral_aviso.json` (con `--procesos` si hace falta) y revisar `comparacion.csv` y `ablacion.csv`.
6. Exportar a Unity con el paso 7; probar el servidor con la simulación real.

### Paso 10 — Reporte (PDF)

- Mismo formato que el de la primera entrega (`entrega_pdf/fuente/reporte.js` y LibreOffice), en una carpeta nueva fuera del repo (`tc2008b/entrega2_pdf/`).
- Secciones de Joel: diseño experimental, métricas y resultados (comparación pareada, ablación de J), análisis crítico. Armado con las secciones de los demás.

---

## 5. Riesgos

| Riesgo | Mitigación |
|---|---|
| El formato 2.2 cambia lo que ya escribió Oswaldo | Se adoptan sus textos y motivos (incluido `"sin_ruta"`); lo desconocido es aviso, no error |
| Romper la regresión de v0.1 | Claves nuevas al final, `combustible` solo si viene, fixture 2.1 con las mismas métricas; correr la prueba de Ilan en cada paso |
| 240 corridas tardan mucho | `--procesos`; medir el tiempo de una corrida de F antes de lanzar todo |
| Versiones de FastAPI incompatibles con Python 3.12 | Verificar con `pip install` en un entorno limpio antes de fijarlas |
| La simulación completa llega tarde | Pasos 1–8 no dependen de ella (traces de ejemplo, simuladores falsos y modo `--ejemplo` del servidor) |

## 6. Lista de verificación final

- [ ] D1 a D9 confirmadas.
- [ ] Pasos 1, 2, 4A y 6 fusionados pronto (destraban a otros) y avisados.
- [ ] Pasos 3, 4B, 5, 7 y 8 con pruebas y commits.
- [ ] Regresión contra v0.1 pasando con todo lo de Datos.
- [ ] Integración, experimento completo y reporte (pasos 9 y 10) cuando llegue la simulación.
