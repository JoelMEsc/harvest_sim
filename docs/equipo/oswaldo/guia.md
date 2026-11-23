# Guía de Oswaldo — Rutas y carro (segunda entrega)

**Tu parte en una frase:** rutas en el tiempo que no chocan ni se bloquean, y el carro como **contratista** de la subasta: oferta, acompaña a la cosechadora y atiende su fila de servicios.

**Por qué importa:** cumple lo que prometimos en la propuesta («2 carros en un pasillo: 0 colisiones y 0 bloqueos») y la mitad del protocolo de comunicación (Contract Net).

**Archivos tuyos:** `src/harvest_sim/rutas.py`, `src/harvest_sim/carro.py`, `tests/test_rutas.py`, `tests/test_carro.py`, y tus notas en `docs/equipo/oswaldo/` (`rutas.md`, `carro.md`: actualízalas).

**Lee antes:** [README del equipo](../README.md); especificación de la segunda entrega §5, §6, §7 y §9.

**Condición:** con `asignacion: "directa"` el carro se comporta **exactamente** como en v0.1 (regresión).

---

## Tareas (en orden)

### 1. `rutas.bfs_tiempo` ⚡ (función pura)

```python
def bfs_tiempo(origen: Celda, destino: Celda, tick: int, ancho: int, alto: int,
               bloqueadas: set[Celda], reservas: dict[tuple[Celda, int], str],
               horizonte: int = 10) -> list[tuple[Celda, int]] | None:
    """Ruta en espacio-tiempo desde (origen, tick). Cada paso: moverse a un vecino (N, E, S, O) o esperar.
    Nunca usa (celda, t) reservada por otro, ni se intercambia: si otro tiene (c2, t) y (c1, t+1),
    no se puede ir de c1 a c2 entre t y t+1. Devuelve [(celda, t), ...] sin el origen, hasta el destino;
    [] si origen == destino; None si no hay ruta dentro de un límite (por ejemplo 4 × (ancho + alto) ticks)."""
```

- BFS sobre estados `(celda, t)`; expandir en orden fijo: esperar, N, E, S, O (determinista).
- Después del horizonte las reservas ya no cuentan (planea libremente, pero sigue sin obstáculos).
- **Listo cuando:** pruebas nuevas: en un pasillo de 1 celda, dos rutas opuestas → la segunda espera y ninguna `(celda, t)` se repite ni hay intercambio; destino inalcanzable → None.

### 2. `rutas.estimar_costo` ⚡ (función pura)

```python
def estimar_costo(desde: Celda, ticks_ocupado: int, hacia: Celda, ancho: int, alto: int,
                  bloqueadas: set[Celda]) -> int | None:
    """ticks_ocupado + distancia BFS desde `desde` hasta una celda vecina de `hacia`. None si no hay ruta."""
```

### 3. Carro en modo subasta (`carro.py`)

Atributos nuevos: `servicios` (fila FIFO de servicios ganados: `servicio`, cosechadora, carga anunciada), `combustible`, `tanque`.

- **Lee el buzón en cada tick** (en cualquier estado) cuando `mundo.config.politica["asignacion"] == "subasta"`:
  - `SOLICITUD_SERVICIO` → si le cabría la carga y le alcanza el combustible (`mundo.combustible_para`, respetando la reserva), responde `PROPUESTA` con `costo = rutas.estimar_costo(...)` (el `ticks_ocupado` es lo que le falta de su fila: traslados, transferencias y descargas con `mundo.duracion`); si no, `RECHAZO` con `motivo`. Si rechazó por combustible, `mundo.registrar_restriccion(id, "combustible_reserva", ...)`.
  - `ACEPTACION` → agrega el servicio a `servicios`. `RECHAZO_PROPUESTA` → nada.
  - `TRANSFERENCIA_TERMINADA` → quita el servicio atendido de la fila.
- **Atender el primer servicio de la fila:** va hacia la posición **actual** de esa cosechadora (`mundo.posicion`), recalculando el objetivo cada tick con `elegir_celda_objetivo` (evitando la siguiente celda de su camino). Al quedar vecino → `ESPERANDO_TRANSFERENCIA`; si ella se aleja → `YENDO_A_COSECHADORA` y la sigue.
- **Al terminar la transferencia:** si `encadenar_servicios` y le cabe la carga anunciada del siguiente servicio, va por él; si no, a la bodega.
- **Al terminar de descargar:** si `atender_desde_bodega` y tiene servicios, va directo al siguiente; si no, regresa a su base.
- **Movimiento:** con `rutas.bfs_tiempo` y `mundo.reservas(excepto=id)`; reserva su ruta con `mundo.reservar`. Si una ruta reservada se invalida y no hay alternativa: `mundo.registrar_bloqueo(id)` (no debe pasar). Si la ruta rodeó un obstáculo o esquivó a otro agente, registra la restricción correspondiente (especificación §10) **una vez por desvío**, no en cada tick.
- **Combustible:** si con su nivel no puede ir, atender y volver sin bajar de la reserva, primero va a recargar a su base.
- **Listo cuando:** pruebas con dobles (mundo y buzón falsos): responde propuesta y rechazo correctos; con dos servicios en fila los atiende en orden; con `encadenar_servicios` atiende dos antes de la bodega; nunca transfiere un servicio que no ganó.

### 4. `registro()` con combustible

Agrega `"combustible": round(self.combustible, 2)`.

### 5. Modo `directa` intacto

Con `asignacion: "directa"`, el carro solo lee su buzón en `EN_BASE` y atiende `LLENA` como en v0.1, usando su BFS de siempre si hay un solo carro. Corre `pytest tests/test_carro.py` y la regresión de Ilan.

### 6. Notas y PDF

Actualiza `docs/equipo/oswaldo/rutas.md` y `carro.md` con el diseño nuevo (rutas en el tiempo y contratista). Sección del PDF: rutas sin colisiones y asignación por subasta (para Joel).

---

## Dependencias

- **Dependes de:** nadie para `rutas.py`; del mundo (reservas, combustible) y del buzón (tipos nuevos) para el carro real. Mientras, dobles en `tests/test_carro.py`.
- **Dependen de ti:** Emilio (la cosechadora usa `bfs_tiempo` y espera tus propuestas), Carlos (escenario E), Ilan (prueba del pasillo).

## Cómo probar

```bash
pytest tests/test_rutas.py tests/test_carro.py -q
python -m harvest_sim.cli config/escenario_e.json --sin-plots && python tools/validar_trace.py runs/escenario_e/trace.json
```

## Definición de listo

- [ ] `bfs_tiempo` y `estimar_costo` con pruebas, deterministas.
- [ ] Carro contratista completo; modo `directa` igual que en v0.1.
- [ ] Escenario E: 0 colisiones y 0 `BLOQUEO`.

## Errores comunes

- Expandir el BFS en orden distinto: rompe el determinismo.
- Olvidar el chequeo de intercambio (dos carros que se cruzan en el mismo paso).
- Contar una espera planeada como `BLOQUEO`.
