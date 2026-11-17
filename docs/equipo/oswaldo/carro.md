# `carro.py` — qué se hizo y cómo explicarlo

**Autor:** Oswaldo · **Rama:** `branch-oswaldo-rutas` · **Archivos:** `src/harvest_sim/carro.py`, `tests/test_carro.py`
**Especificación:** §5.2 (tabla de estados), §4.2 (conflictos), §4.3 (duraciones), §5.3 (reposo) y §6.1 (registro).
**Antes lee:** [rutas.md](rutas.md); el carro usa esas funciones para moverse.

**Resumen:** el carro es un **agente reactivo con estado**, hecho como máquina de estados. No planea ni aprende. En cada tick ve en qué estado está, revisa una condición, hace una acción y quizá cambia de estado. Va por el grano solo cuando la cosechadora le avisa que está llena (`LLENA`). Esto es la **línea base reactiva** contra la que se van a comparar las mejoras.

Estado:
- **7 de 7 tests pasan.** Son los 6 de la guía más uno de bloqueos.
- **Probado de punta a punta.** Se juntó con el `Mundo` y la simulación de Carlos, el buzón y la cosechadora de Emilio y las pruebas de Ilan. Corren los 3 escenarios, el validador de Joel da `OK` en los tres y pasan las 39 pruebas de integración (ver §7).

---

## 1. La máquina de estados

```
            LLENA en la fila
 EN_BASE ───────────────────► YENDO_A_COSECHADORA
    ▲                                 │ llegó a la celda objetivo
    │ llegó a su base                 ▼
 REGRESANDO_A_BASE           ESPERANDO_TRANSFERENCIA
    ▲                                 │ llega TRANSFERENCIA_TERMINADA
    │ terminó de descargar            ▼
 DESCARGANDO ◄─────────────── YENDO_A_BODEGA
               llegó a (0, 0)
```

| Estado | Qué hace en cada tick | Cuándo cambia |
|---|---|---|
| `EN_BASE` | Revisa su fila de mensajes (**solo aquí**) | Si hay un `LLENA`: elige la celda objetivo, calcula la ruta y pasa a `YENDO_A_COSECHADORA` (ese tick no se mueve) |
| `YENDO_A_COSECHADORA` | Un paso por la ruta (§4.2 si hay choque) | Llegó a la celda objetivo, así que en ese mismo tick pasa a `ESPERANDO_TRANSFERENCIA` |
| `ESPERANDO_TRANSFERENCIA` | Espera inmóvil (no cuenta como bloqueo) | Llega `TRANSFERENCIA_TERMINADA`: registra `cantidad`, calcula la ruta a la bodega y pasa a `YENDO_A_BODEGA` |
| `YENDO_A_BODEGA` | Un paso por la ruta | Llegó a `(0, 0)`: calcula la duración y pasa a `DESCARGANDO` |
| `DESCARGANDO` | Cuenta los ticks | Se acabó la cuenta: `mundo.depositar` (la carga queda en 0, evento `DEPOSITO`), calcula la ruta a su base y pasa a `REGRESANDO_A_BASE` |
| `REGRESANDO_A_BASE` | Un paso por la ruta | Llegó a su base y pasa a `EN_BASE` (es también su estado de reposo final, §5.3) |

**Memoria del agente** (§5.2): `carga`, `ruta` (celdas que faltan), `objetivo` (celda donde se estaciona), el contador de la descarga, su base y `cantidad_recibida`.

---

## 2. Un ciclo completo, tick por tick

Así lo prueba `test_carro_ciclo_completo_de_estados`. Mapa 4 × 3; la cosechadora `C` está llena en `(2, 1)` y su siguiente celda es `(3, 1)`. La carga es 4 y la tasa de descarga es 2.

```
        x=0   x=1   x=2   x=3
y=0    [Bod]  [K]    .     .
y=1      .     .    [C]    .
y=2      .     .     .     .
```

| Tick | Estado al final del tick | Posición | Carga | Qué pasó |
|---|---|---|---|---|
| 0 | `EN_BASE` | (1, 0) | 0 | Inicio, orientación `N` |
| 1 | `YENDO_A_COSECHADORA` | (1, 0) | 0 | Lee `LLENA` y elige `(2, 0)` (N y O empatan a 1 paso y gana N; E se evita porque es la siguiente de la serpentina) |
| 2 | `ESPERANDO_TRANSFERENCIA` | (2, 0) | 0 | Un paso al E y llegó |
| 3 | `ESPERANDO_TRANSFERENCIA` | (2, 0) | 0 | Espera (aquí la cosechadora lo ve y empieza a transferir) |
| 4 | `YENDO_A_BODEGA` | (2, 0) | 4 | Llegó `TRANSFERENCIA_TERMINADA` con `cantidad = 4` |
| 5 | `YENDO_A_BODEGA` | (1, 0) | 4 | Un paso |
| 6 | `DESCARGANDO` | (0, 0) | 4 | Llegó; duración `ceil(4 / 2) = 2` |
| 7 | `DESCARGANDO` | (0, 0) | 4 | Segundo tick de descarga |
| 8 | `REGRESANDO_A_BASE` | (0, 0) | 0 | El mundo deposita las 4 unidades |
| 9 | `EN_BASE` | (1, 0) | 0 | Llegó a su base |

---

## 3. Las reglas importantes y cómo se cumplen

**Regla del carro ocupado (§5.2), la que hace que exista el tiempo ocioso.**
- Si llega un `LLENA` mientras el carro anda fuera, **se queda en la fila**. El carro solo lee su fila en `EN_BASE`.
- Los ticks que la cosechadora pasa esperando por esto son el **tiempo ocioso**, la métrica principal.
- Caso raro: en `ESPERANDO_TRANSFERENCIA` el carro sí lee la fila, porque ahí le llega el `TRANSFERENCIA_TERMINADA`. El buzón no deja "ver sin sacar". Si saca un `LLENA`, lo aparta en una lista interna y lo atiende primero al volver a `EN_BASE`, así que **nunca se descarta**. Con una sola cosechadora este caso no pasa, pero queda cubierto.

**FIFO.** Con varios `LLENA` en la fila, atiende primero el más antiguo, uno a la vez.

**Celda objetivo (§5.2).** La decide `rutas.elegir_celda_objetivo`:
- Excluye la bodega y las celdas ocupadas.
- Evita la siguiente celda de la serpentina, que el carro calcula con `mundo.camino_serpentina()`.
- De las que quedan, escoge la más cercana por BFS, y en empate gana el orden N, E, S, O.

**Movimiento y conflictos (§4.2).**
- Cada paso lo da `rutas.siguiente_paso`. Si la siguiente celda está ocupada, recalcula la ruta esquivando y avanza.
- Si no hay ruta, **espera** y llama `mundo.registrar_bloqueo`, que se vuelve un evento `BLOQUEO` en el log.
- Solo en ese caso. Esperar la transferencia **no** es un bloqueo.

**Duraciones (§4.3).**
- La descarga dura `ceil(carga / tasa_descarga)` ticks, como mínimo 1. Se calcula al **entrar** a `DESCARGANDO`.
- El estado aparece en **exactamente** ese número de ticks del log, empezando por el tick de entrada.
- La carga se deposita el tick siguiente al último.
- Una carga parcial (la última de la cosecha) dura menos.

**Conservación del grano (R7).**
- El carro **nunca** se cambia la carga a sí mismo: lo hace el mundo, con `mundo.transferir` (lo llama la cosechadora) y `mundo.depositar`.
- El mensaje `TRANSFERENCIA_TERMINADA` solo informa. El carro registra `cantidad` y avisa en el log si no coincide con su carga.

**Orientación.** Es la dirección del último movimiento (`N`, `E`, `S` u `O`); al inicio es `N`.

---

## 4. `registro(tick)`, lo que va al log

Exactamente 6 claves, sin `intencion` ni `objetivo` (decisión del 2026-11-15). Son listas y textos, no tuplas ni `Enum`:

```python
{"tick": 6, "agent_id": "carro_1", "tipo": "carro",
 "pose": {"x": 0, "y": 0, "orientacion": "O"},
 "estado": "DESCARGANDO", "carga": {"actual": 4, "capacidad": 20}}
```

El `TraceBuilder` de Joel lo convierte en eventos `AGENTE` con solo los campos que cambiaron.

---

## 5. Los 7 tests (`tests/test_carro.py`)

Usan un `MundoFalso` y un `BuzonFalso` escritos en el mismo archivo, con la misma lógica que los reales. Así se prueba el carro solo. Un "guion" dice qué pasa en cada tick, por ejemplo "en el tick 4 llega `TRANSFERENCIA_TERMINADA`".

| Test | Qué verifica |
|---|---|
| `test_carro_solo_revisa_su_fila_en_en_base` | Un `LLENA` que llega mientras va a la bodega queda intacto en la fila hasta volver a `EN_BASE`, y entonces lo atiende. Uno que llega mientras espera la transferencia tampoco se pierde |
| `test_carro_atiende_en_orden_fifo` | Con dos `LLENA`, va primero con el más antiguo; el otro sigue en la fila |
| `test_carro_ciclo_completo_de_estados` | La secuencia exacta de la tabla del §2: estados, posiciones, orientación, carga, un solo depósito y cero bloqueos |
| `test_carro_duracion_de_descarga` | `ceil(carga / tasa)` ticks consecutivos para 6 combinaciones (incluye cargas parciales); deposita el tick siguiente; la tasa también puede venir en el constructor |
| `test_carro_registra_cantidad_del_mensaje` | `cantidad_recibida == cantidad == carga`, con carga completa y parcial |
| `test_carro_registra_bloqueo_solo_si_no_puede_moverse` | Celda tapada con desvío: rodea sin bloqueo. Base ocupada: espera y registra un `BLOQUEO` por tick. Esperando la transferencia: ninguno |
| `test_carro_registro` | Exactamente las 6 claves, tipos correctos, serializable a JSON (antes se llamaba `test_carro_registro_v1_0`) |

```bash
pytest tests/test_carro.py -v
```

---

## 6. Decisiones que no venían en la especificación

Están en `docs/decisiones.md` (2026-11-17):

1. **Al llegar, cambia de estado en el mismo tick.** Por ejemplo, da el último paso y en ese tick ya queda `ESPERANDO_TRANSFERENCIA`. Así lo hace el simulador de referencia de Joel (`tools/generar_trace_ejemplo.py`) y no se desperdicia un tick parado en la meta. Las transiciones que salen de estados quietos (`EN_BASE`, `ESPERANDO_TRANSFERENCIA`, `DESCARGANDO`) no incluyen movimiento.
2. **De dónde sale `tasa_descarga`.** Carlos crea el carro como `Carro("carro_1", capacidad)`, sin tasa. El carro acepta `tasa_descarga` opcional en el constructor; si no viene, la lee de `mundo.config.tasa_descarga`, igual que la cosechadora de Emilio lee `mundo.config.tasa_transferencia`.
3. **`LLENA` apartados.** Si en `ESPERANDO_TRANSFERENCIA` sale un `LLENA` de la fila, se guarda y se atiende primero al volver a `EN_BASE` (ver §3).
4. **Fórmula de duración local.** `duracion_descarga` en `carro.py` es la misma fórmula que `mundo.duracion_ticks`. Se usa la local porque en `development` esa función todavía es un esqueleto. Cuando llegue el `mundo.py` de Carlos se puede cambiar por la suya; es una línea.

---

## 7. Integración con lo de los demás

Se probó juntando en una copia temporal las ramas de Carlos, Emilio e Ilan con este código:

| Escenario | Ticks | Validador | Tiempo ocioso | Bloqueos |
|---|---|---|---|---|
| A | 134 | OK | 50 | 0 |
| B | 193 | OK | 72 | 0 |
| C | 262 | OK | 153 | 0 |

Las 39 pruebas de integración de Ilan pasan (sin `skip`), y la suite completa da 176 pasados y 0 fallos.

**Pero hubo que agregar una línea en el `Mundo` de Carlos**, solo en la copia temporal: `self.config = config` en `Mundo.__init__`. Sin ella, la cosechadora de Emilio truena con `'Mundo' object has no attribute 'config'`. Ese archivo no es nuestro: **hay que pedírselo a Carlos**. La otra opción es que Carlos pase las tasas al crear los agentes, `Carro("carro_1", config.capacidad_carro, config.tasa_descarga)`; el carro acepta las dos formas.

---

## 8. Preguntas que te pueden hacer

- **¿Por qué "reactivo"?** Porque no anticipa nada: espera a que la cosechadora esté llena para salir. Las mejoras futuras (salir antes, despachador) se compararán contra esto.
- **¿Por qué el carro no atiende un `LLENA` mientras va a la bodega?** Lo dice la especificación (regla del carro ocupado): primero termina su ciclo. Eso genera el tiempo ocioso que se quiere medir y reducir después.
- **¿Cómo sabe la cosechadora que el carro ya llegó?** Por percepción directa del mundo: ve que el carro está en una celda vecina **y** en `ESPERANDO_TRANSFERENCIA`. No usa un mensaje. Por eso el carro debe estar en ese estado exacto, y uno que solo pasa al lado no dispara la transferencia.
- **¿Quién mueve el grano?** El mundo, de forma atómica (`transferir` y `depositar`). Los mensajes solo informan, así que si un día se pierde un mensaje, el grano no se pierde (R7).
- **¿Qué es un bloqueo y qué no?** Bloqueo es querer moverse y no poder porque otro agente tapa todas las rutas. Esperar la transferencia es parte del trabajo, no un bloqueo. Se cuentan aparte (`ticks_bloqueados` contra tiempo ocioso).
- **¿Por qué está dividido entre `rutas.py` y `carro.py`?** `rutas.py` es geometría pura, reutilizable y fácil de probar. `carro.py` es solo la lógica de decisión (la máquina de estados).
