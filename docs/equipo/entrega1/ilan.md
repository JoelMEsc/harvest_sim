# Guía de Ilan — Pruebas, CI, scripts y README

**Tu parte en una frase:** escribes las pruebas que comprueban que el mundo y la simulación cumplen la especificación, mantienes el CI en verde, y dejas el repositorio reproducible en una máquina limpia.

**Por qué importa:** la rúbrica da 10 puntos a reproducibilidad y documentación (criterio 8) y 15 a implementación (criterio 3, «incluye validaciones»). Tus pruebas son lo que demuestra que las reglas físicas R1–R9 se cumplen.

**Fecha límite:** martes 17, antes de la clase. **No esperas a nadie para empezar.**

**Archivos tuyos:** `tests/test_mundo.py`, `tests/test_config.py`, `tests/test_integracion.py`, `.github/workflows/ci.yml`, `scripts/`, `README.md`, `docs/autoevaluacion.md`.

**Lee antes:** [README del equipo](README.md) completo; especificación §2 (reglas físicas), §3, §5.4, §9 y §12.

---

## Tareas (en orden)

### 1. CI — 30 min (primero: da la señal verde o roja a todos)

`.github/workflows/ci.yml`: en cada push y PR, Python 3.12, `pip install -r requirements.txt`, `pip install -e .`, `SDL_VIDEODRIVER=dummy MPLBACKEND=Agg pytest -q`.
- **Listo cuando:** corre en GitHub sobre `development` y da verde (hoy: 105 pasan y 53 en `skip`).

### 2. Pruebas de configuración y del mundo — 1 h 30 min

- `tests/test_config.py`: agrega `"obstaculos"` a `CAMPOS` (Carlos agrega la sección a los JSON). Escribe `test_config_invalida` parametrizado: una configuración inválida por cada validación del §3 (incluidas `num_carros = 2` → «aún no soportado», un obstáculo fuera del mapa y un obstáculo no vacío → «aún no soportados»), comprobando con `pytest.raises(ValueError, match=...)`.
- `tests/test_mundo.py`: escribe los cuerpos de los 11 tests a partir de sus docstrings. Para `test_cosechar_registra_cambio`, verifica que `mundo.drenar_eventos()` devuelve `{"tipo": "CELDA_COSECHADA", "celda": [x, y], "agente": id}` y, tras `depositar`, `{"tipo": "DEPOSITO", "agente": id, "cantidad": n, "entregado_total": total}`; y que una segunda llamada a `drenar_eventos()` devuelve `[]`. Agrega `test_registrar_bloqueo` (`{"tipo": "BLOQUEO", "agente": id}`). En `test_descripcion_del_mundo`, que trae `obstaculos` (lista vacía).
- Escríbelas **ya**, con `skip`, y quítalo cuando `mundo.py` llegue a `development` (un PR pequeño por módulo).
- **Listo cuando:** en `development` no queda ningún `skip` en estos dos archivos.

### 3. Pruebas de integración (`tests/test_integracion.py`) — 2 h

Sobre una corrida completa de cada escenario (`ejecutar(cargar_config(...))`), usando el log. Herramientas que ya existen:

```python
from harvest_sim.datos import reconstruir, linea_de_tiempo, validar_trace, verificar_checksums, celdas_de_campo
for estado in reconstruir(trace):          # estado completo de cada tick 0..total_ticks
    estado["agentes"]["carro_1"]["pose"]   # {"x", "y", "orientacion"}
    estado["celdas_cosechadas"], estado["entregado_total"], estado["eventos"]
```

| Prueba | Qué comprobar (en cada tick) |
|---|---|
| `test_no_comparten_celda` | R3: dos agentes nunca en la misma celda |
| `test_no_intercambian_posicion` | R4: nunca se intercambian entre `t-1` y `t` |
| (nueva) `test_un_paso_por_tick` | R2: cada agente se mueve a lo más una celda (Manhattan ≤ 1) |
| `test_conservacion_de_grano` | R7: `len(celdas_cosechadas) × grano_por_celda == suma de cargas + entregado_total` |
| `test_terminacion` | §5.4 al final: cosechadora en `FIN`, carro en `EN_BASE`, carga 0, `entregado_total == grano_esperado(mundo)` |
| `test_inicio_y_regreso_a_base` | Tick 0 y último tick: cada agente en su base |
| `test_duracion_de_estados_en_el_log` | Un `TRANSFIRIENDO` dura `ceil(cantidad / tasa)` ticks |
| `test_mensaje_pendiente_no_se_pierde` | Cada `MENSAJE_ENVIADO` tiene su `MENSAJE_ENTREGADO` en `entrega_en` |
| `test_mensajes_viajan_al_tick_siguiente` | `entrega_en == tick + 1` |
| `test_checksum_de_todo_el_log` | `verificar_checksums(trace)` y `validar_trace(trace) == []` |
| `test_reproducibilidad` | Dos corridas → `texto_del_trace` idéntico |
| `test_grano_entregado_igual_al_del_campo` | `metricas["grano_total_entregado"] == metricas["grano_esperado_total"]` |
| `test_cambios_reconstruyen_el_mapa` | Al final, `set(celdas_cosechadas) == celdas_de_campo(mundo)`, sin repetidas |

Las reglas R2, R3, R4 y R7 las revisas tú sobre corridas completas (el validador de Joel solo revisa el formato; decisión del 2026-11-16).
- **Listo cuando:** pasan los 3 escenarios, sin `skip`.

### 4. Scripts — 45 min

- `scripts/correr_todos.sh`: corre los tres escenarios con la CLI, valida los traces (`python tools/validar_trace.py runs/escenario_*/trace.json`), genera las gráficas y la comparación (`python viz/plots.py runs/escenario_*/trace.json`), corre el experimento (`python tools/correr_experimento.py config/experimentos/tasa_transferencia.json`) y el dashboard. Termina con error si algo falla (`set -euo pipefail`).
- `scripts/verificar_instalacion.sh`: entorno virtual nuevo en una carpeta temporal, instala, corre `pytest` y `correr_todos.sh`.

### 5. README — 30 min

El README ya documenta la instalación, la estructura, el reparto y cómo usar la parte de Datos (lo actualizó Joel el 16 de noviembre). Tú lo mantienes al día: cuando funcionen la CLI, el visor y el dashboard, quita las marcas «[por implementar]», agrega `scripts/correr_todos.sh` como forma de correr todo, dónde quedan los resultados y la sección de verificación en un entorno limpio.

### 6. Autoevaluación — 30 min (martes)

`docs/autoevaluacion.md`: la rúbrica nueva (8 criterios, [README del equipo](README.md) §5) con lo que cumple el proyecto y dónde se ve cada cosa.

### 7. PDF: secciones 3 «Implementación» y 8 «Reproducibilidad» — 45 min (martes)

---

## Dependencias

- **Dependes de:** Carlos (config, mundo y `ejecutar`) para quitar los `skip`.
- **Dependen de ti:** todos (CI); el PDF (reproducibilidad).

## Cómo probar

```bash
SDL_VIDEODRIVER=dummy pytest -q
bash scripts/verificar_instalacion.sh
```

## Definición de listo

- [ ] CI verde en `development`.
- [ ] Ningún `skip` en tus pruebas; R1–R9 probadas.
- [ ] `verificar_instalacion.sh` pasa en una carpeta limpia.
- [ ] README y autoevaluación al día.

## Errores comunes

- Probar sobre el fixture de ejemplo en lugar de una corrida real (el fixture no es la simulación).
- Escribir `ancho * (alto - 1)` en las pruebas: usa `grano_esperado(mundo)` o `celdas_de_campo(mundo)`.
- Dejar el CI sin `SDL_VIDEODRIVER=dummy` (el visor falla sin pantalla).
