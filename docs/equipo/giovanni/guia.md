# Guía de Mario Giovanni — Interfaz (segunda entrega)

**Tu parte en una frase:** Unity reproduce la coordinación multiagente pidiendo los traces al servidor FastAPI, y el visor, la CLI y el dashboard de Python muestran lo nuevo (varios agentes, obstáculos, subasta, combustible y estrategias).

**Por qué importa:** es lo que se ve en la demo y el video, y la base de la integración 3D/WebGL de la entrega final. Python sigue siendo la única fuente de verdad: Unity solo reproduce.

**Archivos tuyos:** en `harvest-simu-visualization` (tu repo de Unity) todo; en `harvest_sim`: `viz/viewer.py`, `viz/dashboard.py`, `src/harvest_sim/cli.py`, `tests/test_viewer.py`, `tests/test_dashboard.py`.

**Lee antes:** [README del equipo](../README.md); especificación de la segunda entrega §7 (mensajes), §12 (trace 2.2) y §14 (servidor).

---

## Tareas en Unity (`harvest-simu-visualization`)

### 1. Leer el trace 2.2 ⚡

- `TraceLoader`: acepta `schema_version` `"2.1"` y `"2.2"`.
- Campos nuevos: `AGENTE.set.combustible`, `CELDA_COSECHADA.cantidad`, `mundo.rendimiento` (opcional), eventos `RECARGA` y `RESTRICCION`, los 7 tipos de mensaje y `entrega_en` mayor que t + 1.
- Actualiza `expected_states.json` y las pruebas con los traces nuevos (Joel te da `tools/exportar_traces_unity.py`, que copia traces ya validados a `Assets/Data/Traces/`).
- **Listo cuando:** las pruebas de datos pasan con los traces de D, E y F.

### 2. Varios agentes, obstáculos y combustible

- Agentes desde el catálogo (sin ids fijos): color por tipo y un tono distinto por id; etiqueta con el id.
- Obstáculos como cubos grises (ya están en el mundo del trace).
- Barra de combustible por agente en el HUD; marca visual en el tick de una `RECARGA`.
- Celdas con más grano (rendimiento) un poco más oscuras, si `mundo.rendimiento` existe.

### 3. Que se vea la coordinación

- **Subasta:** al enviarse `SOLICITUD_SERVICIO`, líneas de la cosechadora a cada carro; `PROPUESTA` con su costo como texto sobre el carro; la línea del ganador (`ACEPTACION`) se queda hasta la `TRANSFERENCIA_TERMINADA`.
- **Restricciones:** el agente parpadea o muestra un icono con el nombre de la regla del evento `RESTRICCION`.
- **Panel de eventos:** mensajes con su performativa (`cfp`, `propose`, `accept-proposal`…).

### 4. Movimiento y cámara 3D

- Interpolación entre celdas (lerp de posición y giro dentro del tick); los datos lógicos siguen cambiando solo al cambiar de tick.
- Cámara en perspectiva con órbita y zoom (y un botón para volver a la cenital).

### 5. Cliente del servidor FastAPI

- `TraceClient` con `UnityWebRequest` (corrutina o `async`): `GET /api/salud`, `GET /api/escenarios`, `GET /api/escenarios/{nombre}/trace?seed=&estrategia=` (especificación §14). URL base configurable en el Inspector (por defecto `http://127.0.0.1:8000`).
- HUD: selector de escenario, estrategia y seed, botón «Simular». Al recibir el trace, se carga como hoy; si el servidor no responde, muestra el error y carga el trace local.
- **Listo cuando:** con `uvicorn harvest_sim.servidor:app` corriendo, eliges E / `anticipada` / seed 3, y Unity reproduce ese trace.

### 6. README del repo de Unity

Cómo levantar el servidor y conectar, versiones, y qué queda para WebGL en la entrega final.

## Tareas en `harvest_sim`

### 7. CLI

`--seed N` y `--estrategia {base, subasta, anticipada, anticipada_plus}` sobrescriben la configuración (los valores de cada estrategia están en el README del equipo §3.1; Joel expone un diccionario `ESTRATEGIAS` en `datos/experimentos.py` que puedes importar).

### 8. Visor pygame y dashboard

- Visor: varios agentes con color por id, obstáculos, barra de combustible, mensajes de la subasta en el panel lateral.
- Dashboard: panel experimental nuevo con la comparación por estrategia (gráficas con IC 95 % que genera Joel) y la tabla de J por término; parámetros de los escenarios nuevos.

### 9. Video y PDF

Grabaciones de Unity y del visor para el video (Ilan lo edita) y la sección de visualización del PDF (para Joel).

---

## Dependencias

- **Dependes de:** Joel (formato 2.2, servidor y traces exportados). Para avanzar desde ya: Joel genera traces 2.2 de ejemplo y el servidor responde con traces de prueba antes de que esté la simulación completa.
- **Dependen de ti:** la demo y el video.

## Cómo probar

```bash
uvicorn harvest_sim.servidor:app --reload          # en harvest_sim
curl http://127.0.0.1:8000/api/salud
SDL_VIDEODRIVER=dummy pytest tests/test_viewer.py tests/test_dashboard.py -q
```

En Unity: Test Runner (EditMode y PlayMode) y reproducir D, E y F desde el servidor.

## Definición de listo

- [ ] Unity lee 2.2, muestra N agentes, obstáculos, combustible, subasta y restricciones.
- [ ] Unity pide traces al servidor y los reproduce; si falla, error visible y trace local.
- [ ] Interpolación y cámara 3D.
- [ ] CLI con `--seed` y `--estrategia`; visor y dashboard actualizados.

## Errores comunes

- Decidir algo en Unity (por ejemplo, inferir el ganador de la subasta): se toma del evento `ACEPTACION`.
- Bloquear el hilo principal con la petición HTTP.
- Cambiar cargas o cosecha durante la interpolación (solo cambian al cambiar de tick).
