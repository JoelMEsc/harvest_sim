# `carro.py` — qué se hizo y cómo explicarlo

**Autor:** Oswaldo · **Rama:** `branch-oswaldo-rutas` · **Archivos:** `src/harvest_sim/carro.py`, `tests/test_carro.py`
**Especificación:** primera entrega §5.2 (tabla de estados), §4.2 (conflictos), §4.3 (duraciones), §5.3 (reposo) y §6.1 (registro); segunda entrega §5, §6, §7, §9 y §10.
**Antes lee:** [rutas.md](rutas.md); el carro usa esas funciones para moverse.

> **Segunda entrega:** el carro ahora es el **contratista** de la subasta (§9 a §13 de este documento). Con `asignacion: "directa"` y un solo carro se comporta exactamente como en las secciones 1 a 8 (mismo `trace.json` byte a byte en A, B y C).

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

---

# Segunda entrega: el carro contratista

## 9. Dos modos

| | `asignacion: "directa"` (línea base) | `asignacion: "subasta"` |
|---|---|---|
| Lee su buzón | Solo en `EN_BASE` | **En cada tick, en cualquier estado** |
| Quién le asigna trabajo | `LLENA` de su cosechadora asignada | Gana servicios en la subasta (Contract Net) |
| A dónde va | A la posición que decía `LLENA` | A la posición **actual** de la cosechadora (la sigue) |
| Movimiento | `siguiente_paso` con 1 carro; **rutas en el tiempo** con varios | Rutas en el tiempo |

Las rutas en el tiempo se usan con subasta **o** con más de un carro, así la estrategia `base` del escenario E (directa con 2 carros) tampoco choca. Con un solo carro en directa no se reserva nada y todo es v0.1.

## 10. El protocolo, del lado del carro (§7)

```
 cosechadora                         carro
     │── SOLICITUD_SERVICIO (cfp) ────►│  ¿le cabe? ¿le alcanza el combustible?
     │◄──── PROPUESTA (propose) ───────│  costo = rutas.estimar_costo(...)
     │◄──── o RECHAZO (refuse) ────────│  motivo: sin_capacidad | combustible
     │── ACEPTACION (accept-proposal) ►│  agrega el servicio a su fila (FIFO)
     │── o RECHAZO_PROPUESTA ─────────►│  lo olvida
     │        ... el carro la acompaña y espera junto a ella ...
     │── TRANSFERENCIA_TERMINADA ─────►│  quita ese servicio de la fila
```

- **Costo de la oferta:** se simula su fila (lo que falta del estado actual, y por cada servicio: traslado + transferencia + bodega + descarga, y la vuelta a la base si no `atender_desde_bodega`); el costo es `estimar_costo(donde_queda, ticks_de_la_fila, cosechadora)`. Ejemplos calculados en [rutas.md](rutas.md) §13.
- **Las duraciones de la estimación usan `ceil(cantidad / tasa)`** y no `mundo.duracion`: esa función sortea el extra aleatorio (§8) y llamarla solo para estimar cambiaría la secuencia del generador. La descarga real sí usa `mundo.duracion`.
- **Rechazo por combustible:** si para ir, transferir, descargar y volver bajaría de `reserva × tanque`. Registra `RESTRICCION` con `regla: "combustible_reserva"`.
- **Los tipos de mensaje se comparan por su texto** (`"PROPUESTA"`, …): el carro no depende de que el enum del buzón ya los tenga. Al enviar usa `TipoMensaje("PROPUESTA")` si existe.
- **Nunca transfiere un servicio que no ganó:** solo se pone en `ESPERANDO_TRANSFERENCIA` junto a la cosechadora de su **primer** servicio.

## 11. Acompañar, encadenar y atender desde la bodega (§6)

- **Acompañar:** en cada tick recalcula la celda objetivo con `elegir_celda_objetivo` sobre la posición actual de la cosechadora, evitando su siguiente celda del camino (`mundo.camino(id)`). Si ya está en esa celda → `ESPERANDO_TRANSFERENCIA`; si la cosechadora se aleja → `YENDO_A_COSECHADORA` y la sigue. Mientras ella está en `LLENA_ESPERANDO` o `TRANSFIRIENDO` y él es vecino, **no se mueve** (la transferencia exige que sigan vecinos).
- **`encadenar_servicios`:** al terminar una transferencia, si tiene otro servicio y le cabe, va por él antes de la bodega. Para «le cabe» usa la **capacidad** de esa cosechadora (viene en la llamada), no la carga anunciada: con despacho anticipado ella sigue cosechando hasta llenarse.
- **`atender_desde_bodega`:** al terminar de descargar, si tiene servicios va directo; si no, regresa a su base.
- **Combustible:** antes de salir revisa que le alcance sin bajar de la reserva; si no, espera en su base a que el mundo recargue (una sola `RESTRICCION` por espera). Si el mundo no tiene combustible (o el tanque es el de por defecto), nunca se activa.

## 12. Moverse sin chocar ni bloquearse

El carro usa `bfs_tiempo` en cada tick y reserva su ruta con `mundo.reservar`. Hacerlo bien con varios agentes obligó a resolver, una por una, las formas en que dos carros pueden quedarse esperándose para siempre (las encontró la prueba de estrés del §13):

| Regla | Problema que evita |
|---|---|
| **R3 conservadora:** el primer paso nunca entra a una celda ocupada ahora | Chocar con alguien que no reservó (o actúa después en el tick) |
| **Compromiso con el plan:** si el plan del tick anterior sigue valiendo, lo cumple; solo cambia por uno que llegue *antes* | Como el BFS prefiere esperar, un carro podía posponer «un tick más» para siempre el movimiento que otro esperaba |
| **Reserva un tick más de lo que revisa** (`tick + H + 1`) | Quien actúa antes en el tick veía un hueco al final de la reserva del otro y le «robaba» el destino |
| **Estancia en la bodega:** reserva solo lo que dura la descarga (completa, aunque pase del horizonte) y, mientras descarga, también **su salida** | La bodega no es un estacionamiento: otro carro debe poder planear entrar en cuanto él se va, y nadie debe planear entrar si él no tiene por dónde salir |
| **Los quietos se quedan:** a un agente en su base, esperando o transfiriendo se le supone en su celda todo el horizonte | Que otro carro planee «atravesar» a un carro estacionado en el borde del horizonte y se quede esperando a que se quite |
| **Pedir y ceder el paso:** si un carro está encerrado o solo llega después del horizonte porque un carro **en viaje** está en su camino, le reclama esa celda; el otro se hace a un lado (de preferencia a un hueco que nadie usa). Si se reclaman los dos, gana el de id menor | Dos carros de frente en un pasillo, o uno esperando justo en la única salida de la bodega |

Además, cada desvío registra **una** `RESTRICCION` (`R3_celda_ocupada`, `R4_intercambio` o `R10_obstaculo`, con `rutas.clasificar_desvio`) por tramo, no una por tick.

## 13. Pruebas

**En `tests/test_carro.py`** (con mundo, buzón y cosechadoras falsos; las 7 de la línea base siguen igual):

| Prueba | Qué verifica |
|---|---|
| `test_subasta_propone_con_estimar_costo_y_rechaza` | propose con el costo de `estimar_costo`; refuse por capacidad y por combustible (con su `RESTRICCION`); reject-proposal → nunca sale |
| `test_subasta_costo_cuenta_la_fila` | El costo suma la fila: 12, 4 y 12 según la política (calculados a mano) |
| `test_subasta_dos_servicios_en_orden_fifo` | Dos servicios en orden; solo espera junto a la cosechadora del servicio que atiende |
| `test_subasta_encadenar_servicios` | Atiende dos antes de la bodega (un depósito de 8); si no le cabe, va entre los dos |
| `test_subasta_atender_desde_bodega` | De la bodega va directo al siguiente, sin pasar por su base |
| `test_subasta_acompana_a_la_cosechadora` | Sigue a una cosechadora que se mueve, siempre a su lado y sin taparle el camino |
| `test_pasillo_dos_carros_sin_colisiones_ni_bloqueos` | Dos carros cruzándose por un hueco de 1 celda (en el centro y en la orilla), 4 políticas: 0 colisiones, 0 intercambios, 0 `BLOQUEO`, nadie desaloja a nadie, restricciones una vez por desvío |
| `test_va_a_recargar_si_no_le_alcanza` | Espera en la base a recargar (subasta y directa) y luego sale |

**Prueba de estrés** (fuera del repositorio, con los mismos dobles): 300 mapas aleatorios con semilla (6 × 5 a 9 × 8, muro con hueco en cualquier lugar, 2–3 carros, 2–3 cosechadoras) × 4 estrategias = 1128 corridas.

| | Corridas | Terminan sin `BLOQUEO` | Colisiones |
|---|---|---|---|
| 2 carros | 608 | **608** | **0** |
| 3 carros | 520 | 470 (14 terminan con algún `BLOQUEO`, 36 no terminan) | **0** |

**Limitación conocida (3 carros o más):** con `carro_1` estacionado en `(1, 0)`, la bodega queda con una sola entrada, `(0, 1)`. Si un tercer carro reserva entrar antes de que el que está adentro haya planeado su salida, se esperan para siempre. Los escenarios de la entrega usan como máximo 2 carros (D: 1, E y F: 2), donde no pasa. Arreglarlo del todo requiere reservar la salida desde el viaje hacia la bodega; queda anotado en `docs/decisiones.md`.

## 14. Preguntas que te pueden hacer (segunda entrega)

- **¿Por qué el carro decide su oferta y no un despachador central?** Porque solo él sabe cuánto trabajo pendiente tiene y cuánto combustible le queda: es información local, y la subasta es un protocolo entre agentes (Contract Net).
- **¿Por qué estimar con la fórmula y no con `mundo.duracion`?** Porque `mundo.duracion` sortea un extra aleatorio: llamarla para estimar consumiría números del generador y cambiaría las corridas.
- **¿Por qué la capacidad y no la carga anunciada para encadenar?** Con despacho anticipado la cosechadora avisa al 70 % y sigue cosechando; si el carro solo dejara lugar para lo anunciado, no le cabría todo.
- **¿Qué pasa si dos carros se esperan mutuamente?** Las reglas del §12 lo evitan; si aun así uno queda encerrado, registra `BLOQUEO` y le pide paso al que estorba. Con 2 carros no pasó en ninguna de las 608 corridas de estrés.
- **¿Y si un mensaje llega tarde?** El carro no asume nada: lee su buzón cada tick y procesa lo que haya. El grano lo mueve el mundo, no los mensajes.
