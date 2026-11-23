# Guía de Ilan — Calidad (segunda entrega)

**Tu parte en una frase:** pruebas que demuestran que la coordinación funciona sin romper la línea base, CI con las dependencias nuevas, scripts para correr todo, la autoevaluación contra las dos rúbricas y el video.

**Por qué importa:** la regresión garantiza que la comparación contra la línea base es justa; las pruebas de los escenarios de conflicto son la evidencia de «0 colisiones y 0 bloqueos» que prometimos.

**Archivos tuyos:** `tests/test_config.py`, `tests/test_mundo.py`, `tests/test_integracion.py`, `tests/test_regresion.py` (nuevo), `.github/`, `scripts/`, `docs/autoevaluacion.md`, el video.

**Lee antes:** [README del equipo](../README.md); especificación de la segunda entrega §2, §13 y §16.

---

## Tareas (en orden)

### 1. CI ⚡

Agrega al workflow lo que Joel suma a `requirements.txt` (FastAPI, uvicorn, httpx). Que corra `pytest -q` igual que hoy.

### 2. Regresión contra la línea base ⚡ (`tests/test_regresion.py`)

- Guarda en `tests/fixtures/metricas_v0_1.json` las métricas de A, B y C de `v0.1-entrega1` (las del `resumen.csv` de esa etiqueta; quita `por_agente` si cambian sus claves, deja las del nivel superior).
- La prueba corre A, B y C con la configuración por defecto y compara: mismas métricas del nivel superior que existían en v0.1.
- **Esta prueba no se desactiva nunca.** Si falla, alguien cambió la línea base.

### 3. Configuración (`test_config.py`)

Un caso por validación nueva de la especificación §2 (sección, campo y mensaje esperado), valores por defecto cuando faltan las secciones, y que `num_carros > 1` y obstáculos ya no fallan.

### 4. Mundo (`test_mundo.py`)

`test_franjas`, reservas (`reservar` reemplaza las futuras; `reservas(excepto)`), `azar` reproducible por fuente, rendimiento fijo vs sorteado, `duracion` con y sin extra, combustible (consumo, recarga solo en base, nunca negativo) y eventos `RECARGA` y `RESTRICCION`.

### 5. Integración (`test_integracion.py`)

Parametriza las pruebas actuales sobre A–F (y sobre las 4 estrategias en D, E, F). Agrega:

| Prueba | Qué revisa |
|---|---|
| `test_no_entra_a_obstaculo` | R10 en cada tick |
| `test_pasillo_sin_colisiones_ni_bloqueos` | E: `colisiones == 0` y ningún evento `BLOQUEO`, en las 4 estrategias y 20 seeds |
| `test_subasta_secuencia` | Cada `servicio`: un cfp por carro, una propuesta o rechazo por carro, una aceptación, los demás rechazados, un inform final |
| `test_transferencia_solo_contratado` | Cada `TRANSFERENCIA_TERMINADA` va al carro aceptado |
| `test_semilla_reproducible` | F: misma seed → mismo texto del trace; seeds distintas → distinto |
| `test_retraso_mensajes` | `entrega_en` en `[t+1, t+1+máximo]` y entrega en ese tick |
| `test_combustible_nunca_negativo` | R11 en cada tick de F |
| `test_recargas_solo_en_base` | Cada `RECARGA` ocurre con el agente en su base |
| `test_conservacion_de_grano` | R7 con rendimiento variable (usa `cantidad` de los eventos) |

Herramientas: `harvest_sim.datos` (`reconstruir`, `linea_de_tiempo`, `validar_trace`, `celdas_de_campo`).

### 6. Scripts

- `scripts/correr_todos.sh`: agrega D, E y F, el experimento de la entrega (`config/experimentos/estrategias.json`, de Joel) y los cuadros del visor de los escenarios nuevos.
- `scripts/servidor.sh`: levanta `uvicorn harvest_sim.servidor:app` (para Unity).

### 7. Autoevaluación (`docs/autoevaluacion.md`)

Contra las **dos** rúbricas: la de Canvas (8 criterios) y la del documento del curso (`reto/EntregaMartes10Nov21hrs.pdf`: modelo matemático, implementación algorítmica, arquitectura, calidad de simulación, ontología, ética y sostenibilidad, diseño de costo, reflexión) y su lista previa a la entrega. Para cada punto: qué lo cumple, dónde se ve y qué falta. Solo afirmaciones comprobables (números de las corridas, número real de pruebas).

### 8. Video

Guion de 3 minutos: D (la subasta reparte el carro), E (pasillo sin choques), F (recargas y restricciones), y la comparación de estrategias. Con material de Mario Giovanni (Unity y visor).

### 9. PDF: implementación, validación y reproducibilidad (para Joel)

---

## Cómo probar

```bash
SDL_VIDEODRIVER=dummy pytest -q
bash scripts/verificar_instalacion.sh
```

## Definición de listo

- [ ] CI verde con las dependencias nuevas.
- [ ] Regresión contra v0.1 activa y pasando.
- [ ] Pruebas de R10, R11, subasta, reproducibilidad y pasillo, sin `skip`.
- [ ] Autoevaluación contra las dos rúbricas; video.

## Errores comunes

- Comparar contra métricas recalculadas con el código nuevo en vez de las guardadas de v0.1.
- Escribir números en la autoevaluación que no salen de una corrida o de `pytest`.
