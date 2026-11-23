# Datos (Joel) — estado y cómo usar las herramientas

**Estado al martes 17:** todo lo de Datos está hecho e integrado con la simulación real (los tres escenarios validan). Falta escribir las secciones 4, 5 y 7 y armar el PDF.

**Archivos de Datos:** `src/harvest_sim/datos/` (paquete), `src/harvest_sim/telemetria.py` (fachada), `viz/plots.py`, `tools/generar_trace_ejemplo.py`, `tools/validar_trace.py`, `tools/correr_experimento.py`, `config/experimentos/`, `tests/fixtures/`, `tests/ayuda_datos.py`, `tests/test_trace.py`, `tests/test_metricas.py`, `tests/test_campo.py`, `tests/test_validador.py`, `tests/test_generador.py`, `tests/test_plots.py`, `tests/test_experimentos.py`.

## Qué hay

| Pieza | Dónde | Para qué |
|---|---|---|
| Formato y vocabulario | `datos/formato.py` | Versión 2.1, eventos, estados, mensajes, performativas y clases de la ontología, en un solo lugar |
| Armar y escribir el log | `datos/trace.py` | `TraceBuilder` (lo usa `simulacion.ejecutar`), checksum por tick, escritura reproducible y compacta |
| Línea de tiempo | `datos/linea_de_tiempo.py` | Una sola pasada por el trace; `reconstruir` para las pruebas de integración |
| Campo y obstáculos | `datos/campo.py` | `celdas_de_campo`, `grano_esperado`, `expandir_obstaculos` (la fórmula en un solo lugar) |
| Métricas | `datos/metricas.py` | Promedio por tipo de agente + detalle `por_agente`; series por tick; mapas por celda |
| Validador | `datos/validacion.py`, `tools/validar_trace.py` | El contrato del formato, ejecutable |
| Experimentos | `datos/experimentos.py`, `tools/correr_experimento.py` | Escenarios × barrido × repeticiones, resumen con IC 95 % |
| Gráficas y tabla | `viz/plots.py` | 6 gráficas por corrida, comparación, tabla, sensibilidad |
| Datos de ejemplo | `tools/generar_trace_ejemplo.py` | Fixture y escenarios de ejemplo mientras no exista la simulación (no es la simulación) |

Las decisiones (formato 2.1, regla de agregación, fórmula del campo, gráficas) están en `docs/decisiones.md`, entradas del 2026-11-15 y 2026-11-16.

## Comandos

```bash
python tools/validar_trace.py runs/escenario_*/trace.json
python viz/plots.py runs/escenario_*/trace.json                 # + --agente cosechadora_1 para una sola
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json   # --simulador ejemplo para probar
python tools/generar_trace_ejemplo.py                           # regenera el fixture de las pruebas
```

## Pendiente

1. ~~Correr los tres escenarios, validar los traces y generar gráficas, tabla y experimento.~~ Hecho el 17 de noviembre (`bash scripts/correr_todos.sh`).
2. Después de la entrega: cambiar el fixture por una corrida corta de la simulación real (el generador de ejemplo queda como herramienta de prueba).
3. Escribir las secciones 4 (diseño experimental), 5 (métricas y resultados) y 7 (análisis crítico) del PDF.
4. Juntar las secciones de todos (llegan antes del martes a mediodía), armar el documento final y subirlo a Canvas.

## Retirado de esta entrega (en el historial de `branch-joel`)

- Combustible y costo (commit `4c634f4`): fuera del alcance (§1 de la especificación).
- Comparación contra una estrategia mejorada (`viz/comparar.py`, commit `458e39d`): vuelve cuando exista la mejora (semana 4). La comparación entre escenarios de la línea base sí está.
- Reglas físicas dentro del validador (commit `d528372`): pasaron a las pruebas de integración de Ilan.
