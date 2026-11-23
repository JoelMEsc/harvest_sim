# Guía de Carlos — Mundo (segunda entrega)

**Tu parte en una frase:** la configuración nueva, el mundo con varios agentes, obstáculos, reservas, azar y combustible, y el bucle de simulación que junta todo.

**Por qué importa:** todos los demás usan tu API del mundo (README del equipo §3.2). Es el criterio de modelado del entorno (15 puntos) y la base de los dos escenarios de conflicto.

**Archivos tuyos:** `src/harvest_sim/config.py`, `src/harvest_sim/mundo.py`, `src/harvest_sim/simulacion.py`, `config/escenario_*.json` (incluidos los nuevos D, E y F).

**Lee antes:** [README del equipo](../README.md); especificación de la segunda entrega §2, §3, §4, §5, §8, §9, §10 y §13.

**Condición que no se puede romper:** con la configuración por defecto, A, B y C dan las mismas métricas que `v0.1-entrega1` (prueba de regresión de Ilan).

---

## Tareas (en orden)

### 1. Configuración nueva (`config.py`) ⚡

- Quita el «aún no soportado» de `num_carros`, `num_cosechadoras` y obstáculos.
- Agrega al `Config` cuatro campos con valores por defecto (`dataclasses.field(default_factory=...)`): `politica`, `incertidumbre`, `combustible`, `costo` (dicts con las claves y valores por defecto de la especificación §2). Una función `_con_defectos(seccion, defectos)` que complete las claves que falten y rechace las desconocidas.
- Validaciones con `ValueError` y mensaje claro (tabla de la especificación §2): `asignacion` en {directa, subasta}; `0 < umbral_aviso ≤ 1`; enteros ≥ 2 y ≥ 1 en `espera_propuestas` y `reintento_subasta`; `1 ≤ minimo ≤ maximo` en rendimiento; `0 ≤ probabilidad ≤ 1`; tanques y consumos > 0; `0 ≤ reserva < 1`; pesos ≥ 0.
- Con rendimiento variable ya no exijas `capacidad_cosechadora % grano_por_celda == 0` (la cosechadora se llena antes si la siguiente celda no cabe).
- **Listo cuando:** los 3 JSON actuales cargan igual que antes, y una configuración con cada sección inválida falla con un mensaje que nombra el campo.

### 2. Franjas y obstáculos en el mundo (`mundo.py`) ⚡

- `mundo.obstaculos`: conjunto de celdas (ya lo expandes en `__init__`).
- `bloqueadas_fijas(agent_id)`: obstáculos para todos; además la bodega para las cosechadoras.
- `camino(agent_id) -> list[Celda]`: divide las celdas libres del campo en m franjas de filas contiguas con número de celdas lo más parejo posible; devuelve la serpentina de la franja de esa cosechadora, sin obstáculos. `camino_serpentina()` queda como `camino("cosechadora_1")` para no romper código existente.
- **Listo cuando:** las franjas cubren cada celda libre una sola vez (prueba `test_franjas` de Ilan) y ninguna incluye un obstáculo.

### 3. Reservas espacio-tiempo ⚡

```python
mundo.reservar(agent_id, ruta: list[tuple[Celda, int]])   # reemplaza las reservas futuras de ese agente
mundo.reservas(excepto: str) -> dict[tuple[Celda, int], str]
```

- Guarda `{(celda, tick): agent_id}`. Al reservar, borra las reservas de ese agente con tick ≥ el primero de la ruta.
- Limpia las reservas con tick < tick actual al inicio de cada tick (`mundo.nuevo_tick(t)`, lo llama `simulacion.py`).
- **Listo cuando:** una prueba reserva dos rutas y `reservas(excepto=a)` devuelve solo las del otro.

### 4. Azar, rendimiento y duraciones

- `azar(fuente) -> random.Random`: crea y guarda un generador por fuente, con semilla derivada (`random.Random(f"{config.seed}-{fuente}")`).
- Rendimiento: en `__init__`, si `minimo == maximo`, todas las celdas valen ese número; si no, sorteas cada celda libre del campo con `azar("rendimiento").randint(minimo, maximo)` en orden fijo (y, x). `rendimiento(celda) -> int`. `descripcion()` agrega `"rendimiento"` (matriz alto × ancho, 0 en servicio y obstáculos) **solo si** es variable.
- `grano_total`: sigue saliendo de `datos.campo.grano_esperado(self.descripcion())` (Joel la actualiza para sumar la matriz).
- `cosechar` suma `rendimiento(celda)` a la carga, devuelve esa cantidad y agrega `"cantidad"` al evento `CELDA_COSECHADA`.
- `duracion(cantidad, tasa)`: `max(1, ceil(cantidad/tasa)) + azar("duracion").randint(0, extra)` (extra = `duracion_extra_maxima`; con 0 no llames al generador).

### 5. Combustible y restricciones

- `registrar(agente)`: pone `agente.tanque` y `agente.combustible` según su tipo.
- `actualizar_combustible(agente, se_movio)`: resta `consumo_por_celda_*` si se movió, o `consumo_por_tick_encendido` si no se movió y no está en `EN_BASE` ni `FIN`. Si está en su base y en `EN_BASE` o `FIN` y no tiene el tanque lleno, recarga (todo, o `tasa_recarga` por tick) y agrega `{"tipo": "RECARGA", "agente", "cantidad", "nivel"}`. Redondea a 2 decimales. Nunca negativo (R11).
- `combustible_para(agent_id, celdas, ticks_encendido) -> float`: litros estimados (lo usan los agentes para la reserva).
- `registrar_restriccion(agent_id, regla, detalle)`: agrega `{"tipo": "RESTRICCION", "agente", "regla", "detalle"}`.

### 6. `simulacion.ejecutar` con N agentes

- Crea `cosechadora_1..m` y `carro_1..n` (con sus capacidades), regístralos y arma el catálogo en ese orden (cosechadoras y luego carros).
- Crea el `Buzon` con el generador de mensajes y los parámetros de retraso (`Buzon(azar=mundo.azar("mensajes"), probabilidad, maximo)`; Emilio).
- Cada tick: `mundo.nuevo_tick(t)` → `buzon.entregar(t)` → cada cosechadora por id → cada carro por id → `mundo.actualizar_combustible(agente, se_movio)` para cada agente → registro → término.
- Término: todas las cosechadoras en `FIN`, todos los carros en `EN_BASE`, sin carga, sin mensajes pendientes, sin servicios en cola (`carro.servicios` vacío) y `entregado == grano_total`.
- Log de consola: igual que antes, más `RECARGA` y `RESTRICCION` en nivel INFO.
- **Listo cuando:** A, B, C dan las métricas de v0.1 (`test_regresion_linea_base`) y D, E, F terminan y validan.

### 7. Escenarios D, E y F (`config/escenario_d.json`, `_e`, `_f`)

Con los valores de la especificación §13. E: muro en y = 3 con hueco en x = 4 (`"regiones": [{"inicio": [0, 3], "tamano": [4, 1]}, {"inicio": [5, 3], "tamano": [4, 1]}]`). F: tanques chicos para que haya recargas (prueba con 60 y 40 L) e incertidumbre activa (rendimiento 1–2, duración extra 2, retraso de mensajes 0.2 / 2). Ajusta F hasta que haya al menos una recarga y una restricción por combustible.

### 8. PDF: secciones de modelo del entorno y escenarios (para Joel)

---

## Dependencias

- **Dependes de:** nadie para las tareas 1–5. Para la 6, de los agentes de Emilio y Oswaldo (mientras, agentes falsos).
- **Dependen de ti:** Emilio y Oswaldo (API del mundo), Ilan (pruebas), Joel (corridas para experimentos).

## Cómo probar

```bash
pytest tests/test_config.py tests/test_mundo.py tests/test_integracion.py -q
python -m harvest_sim.cli config/escenario_e.json && python tools/validar_trace.py runs/escenario_e/trace.json
```

## Definición de listo

- [ ] Regresión: A, B, C con las mismas métricas que v0.1.
- [ ] D, E, F terminan, validan y no tienen colisiones; E sin `BLOQUEO`.
- [ ] Ningún número mágico (bases, franjas y fórmulas calculadas).
- [ ] Mismo seed → mismo trace; seeds distintas → traces distintos en F.

## Errores comunes

- Sortear el rendimiento en un orden que dependa de un `set` (no es determinista): recorre en orden (y, x).
- Llamar al generador de duración cuando `extra == 0`: cambia la secuencia y rompe la regresión.
- Recargar combustible fuera de la base o en un estado distinto de `EN_BASE`/`FIN`.
