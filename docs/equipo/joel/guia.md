# Guía de Joel — Datos (segunda entrega)

**Tu parte en una frase:** el contrato (trace 2.2 y mensajes), las métricas nuevas (combustible, restricciones, subasta) y el costo J, los experimentos con 20 repeticiones contra la línea base, el servidor FastAPI y el reporte.

**Por qué importa:** convierte la coordinación en resultados comparables con intervalos de confianza, y conecta Python con Unity.

**Archivos tuyos:** `src/harvest_sim/datos/`, `src/harvest_sim/servidor.py` (nuevo), `viz/plots.py`, `tools/`, `config/experimentos/`, `tests/fixtures/`, `requirements.txt` (dependencias del servidor) y las pruebas de Datos (`test_trace`, `test_metricas`, `test_campo`, `test_validador`, `test_generador`, `test_plots`, `test_experimentos`, `test_servidor` nuevo).

**Lee antes:** especificación de la segunda entrega completa (eres dueño del contrato).

---

## Tareas (en orden)

### 1. Formato 2.2 ⚡

- `formato.py`: `SCHEMA_VERSION = "2.2"`; tipos de mensaje y `PERFORMATIVAS` nuevas (`cfp`, `propose`, `refuse`, `accept-proposal`, `reject-proposal`); eventos `RECARGA` y `RESTRICCION` (categoría 2); `combustible` en los campos de `AGENTE`; `cantidad` en `CELDA_COSECHADA`; lista de reglas de `RESTRICCION`.
- `TraceBuilder`: sigue el `combustible` del registro como los demás campos.
- `validacion.py`: acepta 2.1 y 2.2; valida los campos nuevos, `mundo.rendimiento` (dimensiones, ceros fuera del campo) y `entrega_en` con `retraso_maximo` tomado de la configuración del trace.
- `campo.py`: `grano_esperado` suma `mundo.rendimiento` si existe.
- Traces 2.2 de ejemplo para Mario Giovanni mientras llega la simulación.

### 2. Métricas nuevas

- **Combustible** (ya desde el log, campo `combustible`): usado y comprado (tanque inicial + recargas) por agente y total, recargas, nivel mínimo.
- **Restricciones:** conteo por regla y por agente.
- **Subasta:** servicios, propuestas por servicio, rechazos por motivo, tiempo de respuesta (ticks de la llamada a la llegada del carro) y espera por servicio.
- **Costo J** (especificación §11): cada término `λ·x`, J total y ablación (J con cada término en 0).
- Actualiza `decisiones.md` y la especificación si cambias una definición.

### 3. Experimentos de la entrega

- `ESTRATEGIAS` en `datos/experimentos.py` (las 4 del README del equipo §3.1) y soporte de `estrategias` en el JSON del experimento.
- `config/experimentos/estrategias.json`: D, E, F × 4 estrategias × 20 seeds.
- Recupera y adapta la comparación contra la línea base (commit `458e39d`): diferencia y cambio % de cada métrica contra `base`, con IC 95 %.
- Gráficas: barras por estrategia con IC 95 % (ocio, completación, combustible, J), J por término apilado y sensibilidad al `umbral_aviso` (0.5–1.0).

### 4. Servidor FastAPI (`src/harvest_sim/servidor.py`)

- Rutas de la especificación §14 (`/api/salud`, `/api/escenarios`, `/api/escenarios/{nombre}/trace`, `POST /api/simulaciones`), validando el trace antes de responder (422 con errores si no es válido).
- Caché por (escenario, estrategia, seed). CORS para `localhost`.
- `requirements.txt`: `fastapi`, `uvicorn` y `httpx` (para `TestClient`) con versión fija; avisa a Ilan para el CI.
- `tests/test_servidor.py` con `TestClient`.

### 5. Herramientas

- `tools/exportar_traces_unity.py <carpeta Assets/Data/Traces>`: corre y valida los escenarios y copia los traces (para el repo de Unity).
- Fixture de las pruebas generado con una corrida corta de la simulación real (el generador de ejemplo queda como herramienta de prueba).

### 6. Reporte (PDF) y ontología

- Junta las secciones de todos en el formato del reporte anterior (`entrega_pdf/fuente/reporte.js`).
- `docs/ontologia.md`: agrega las performativas de la subasta y `RESTRICCION` como *SafetyConstraint* registrada.
- Nota de trabajo futuro (OpenClaw/NemoClaw, WebGL): especificación §15.

---

## Dependencias

- **Dependes de:** Carlos, Emilio y Oswaldo para las corridas reales; mientras, traces de ejemplo y el generador.
- **Dependen de ti:** todos (formato 2.2 y performativas), Mario Giovanni (servidor y traces), Ilan (dependencias del CI).

## Definición de listo

- [ ] Formato 2.2 y validador con pruebas; traces de ejemplo para Unity.
- [ ] Métricas de combustible, restricciones, subasta y costo J con valores calculados a mano en pruebas.
- [ ] Experimento D, E, F × 4 × 20 con IC 95 % y comparación contra `base`.
- [ ] Servidor con pruebas; Unity lo usa.
- [ ] PDF armado.
