# Especificación técnica — Primera entrega parcial (línea base 2D)

**Proyecto:** Reto agrícola multiagente, Equipo 3 · **Versión del documento:** 1.2 · **Formato del log:** trace 2.1
**Fecha límite:** martes 17 de noviembre de 2026, antes de la clase (anuncio de Canvas en `reto/`)

Este documento es la referencia única para construir la primera entrega. Quien lo lea ya conoce el problema general del reto (cosechadoras y carros recolectores, reducir el tiempo ocioso, comparar contra una línea base). Aquí se define **qué se construye ahora, cómo debe comportarse y con qué herramientas**. Cuando algo no esté especificado, elige la opción más simple y regístrala en `docs/decisiones.md`. Al final hay una sección de preguntas frecuentes (§14).

**Cambios de la versión 1.1 respecto a la 1.0:**

- Cada agente tiene una **casilla de inicio** en la fila de servicio, y regresa a ella al terminar. El ancho mínimo del mapa depende del número de agentes.
- Estados nuevos: `EN_BASE`, `YENDO_A_CAMPO` y `REGRESANDO_A_BASE` (cosechadora); `EN_BASE` y `REGRESANDO_A_BASE` (carro).
- La duración de la transferencia y de la descarga **depende de la cantidad** (tasa en unidades por tick).
- `TRANSFERENCIA_TERMINADA` incluye la `cantidad` transferida. Los mensajes tienen `id`.
- **El combustible queda fuera de esta entrega** (solo una nota para la siguiente).
- Se agregan reglas de resolución de conflictos de celda y la sección de FAQ.

**Cambios de la versión 1.2 respecto a la 1.1 (16 de noviembre):**

- El log es el **trace 2.1** (§6.1): cambios por tick con eventos tipados, checksum por tick, sin `intencion` ni `objetivo`, con las clases de la ontología del curso y la `performativa` de cada mensaje. Decisiones del 2026-11-15 y 2026-11-16 en `docs/decisiones.md`.
- Contrato (§10): `Mundo.drenar_eventos()` y `registrar_bloqueo()` reemplazan a `cambios()` y `tick_actual`; `Buzon.drenar_eventos()` reemplaza a `registro()`.
- Configuración (§3): sección `obstaculos` (vacía en esta entrega) y una sola fórmula del grano esperado.
- Métricas (§6.2) para cualquier número de agentes (promedio y detalle por agente); gráficas (§7.2) sin datos repetidos; experimentos con barrido de parámetros.
- La guía paso a paso de cada persona está en `docs/equipo/`.

---

## 1. Qué es esta entrega

Una simulación 2D, en Python, de **una cosechadora y un carro recolector** en un campo pequeño, que será la **línea base reactiva** contra la que se compararán después las mejoras (despacho anticipado, varios agentes, etc.). Por eso debe ser sencilla, determinista y bien instrumentada.

Entregables (checkpoint de la semana 3 del plan del curso):

1. Simulación 2D funcionando de principio a fin con ambos agentes.
2. Reglas físicas verificadas con un test cada una.
3. Telemetría: log `trace.json` (formato 2.1) y las métricas calculadas.
4. Resultados de la línea base en **3 escenarios fijos** (ver §8).
5. Visor 2D que reproduce el log.
6. Gráficas de datos relevantes.
7. README con instrucciones que funcionen en una máquina limpia.

### Fuera del alcance de esta entrega (no implementar)

Incertidumbre o aleatoriedad de cualquier tipo, recorrer obstáculos (la configuración ya los acepta y valida, §3, pero la simulación los rechaza), terreno variable, rendimiento distinto por parcela, más de una cosechadora o carro, servidor/despachador, WebSocket, Unity, aprendizaje por refuerzo, física realista, pérdida de grano o de mensajes, **combustible**.

El diseño debe permitir agregar esas cosas después sin reescribir lo existente (ver §13), pero no se implementan ahora.

---

## 2. Modelo del mundo

- **Grid** de `ancho × alto` celdas. Coordenadas `(x, y)` con origen arriba a la izquierda; `x` crece a la derecha, `y` hacia abajo.
- **Fila 0 es la fila de servicio.** No es parte del campo. Su distribución se calcula con `n = num_carros` y `m = num_cosechadoras`:

| Celdas de la fila 0 | Uso |
|---|---|
| `(0, 0)` | **Bodega**: donde el carro deposita lo recolectado. Solo la usan los carros. |
| `(1, 0)` … `(n, 0)` | Casillas de inicio de los carros (carro `i` → `(i, 0)`, con `i` de 1 a `n`) |
| `(n+1, 0)` … `(n+m, 0)` | Casillas de inicio de las cosechadoras (cosechadora `j` → `(n+j, 0)`, con `j` de 1 a `m`) |
| El resto | Celdas libres de tránsito |

  En esta entrega `n = m = 1`: bodega `(0,0)`, base del carro `(1,0)`, base de la cosechadora `(2,0)`. El código del mundo debe calcular las casillas con `n` y `m` genéricos (no escribir `(1,0)` ni `(2,0)` a mano), aunque la simulación solo soporte uno de cada uno.

- **Campo:** las celdas con `y ≥ 1`. Todas inician con grano listo para cosechar, `grano_por_celda` unidades cada una (valor igual en todo el campo).
- **Bases:** cada agente empieza el tick 0 en su casilla de inicio, y al terminar su trabajo regresa a ella. (En una entrega futura, las bases también serán el punto de recarga de combustible. Por ahora no se modela.)
- Sin obstáculos en esta entrega (la sección `obstaculos` de la configuración va vacía, §3). El mapa se genera a partir de la configuración.
- Vecindad de 4 direcciones (N, E, S, O) para movimiento y adyacencia. Una celda no es vecina de sí misma ni de sus diagonales.
- **Orientación** de un agente: la dirección del último movimiento (`N|E|S|O`). Inicial: `S` para la cosechadora y `N` para el carro.
- **La bodega `(0,0)` está bloqueada para las cosechadoras**: nunca entran ahí ni la cruzan.

### Reglas físicas (invariantes)

Cada una requiere un test automatizado (§9):

| ID | Regla |
|----|-------|
| R1 | Todo movimiento termina en una celda dentro del mapa. |
| R2 | Los agentes se mueven una celda por tick, en vecindad de 4. |
| R3 | Dos agentes nunca ocupan la misma celda. |
| R4 | Dos agentes nunca intercambian posiciones en un mismo tick. |
| R5 | La transferencia solo ocurre con los agentes en celdas vecinas. |
| R6 | Cantidad transferida `δ = min(q_cosechadora, Q_carro − q_carro)`; ninguna carga supera su capacidad. |
| R7 | Conservación: grano cosechado = grano en cosechadora + grano en carro + grano entregado en bodega. En todo tick. |
| R8 | Una celda se cosecha una sola vez. |
| R9 | Ninguna cosechadora entra a la bodega. |

Con una cosechadora y un carro, R3 y R4 se cumplen gracias a las reglas del §4.2, y se verifican igual porque la base se reutilizará con más agentes.

---

## 3. Parámetros (archivo de configuración)

Todos los parámetros viven en un JSON por escenario (`config/escenario_*.json`). **Nada de números mágicos en el código.**

```json
{
  "nombre": "escenario_a",
  "seed": 0,
  "ancho": 8,
  "alto": 7,
  "num_carros": 1,
  "num_cosechadoras": 1,
  "grano_por_celda": 1,
  "capacidad_cosechadora": 10,
  "capacidad_carro": 20,
  "tasa_transferencia": 2,
  "tasa_descarga": 4,
  "max_ticks": 5000,
  "obstaculos": {"celdas": [], "regiones": []}
}
```

`tasa_transferencia` y `tasa_descarga` son **unidades de grano por tick**. La duración se calcula con la cantidad real (ver §4.3). Con `tasa_transferencia = 2`, transferir 10 unidades toma 5 ticks y transferir 3 toma 2 ticks (redondeo hacia arriba).

Validaciones al cargar (fallar con error claro):

- `capacidad_carro >= capacidad_cosechadora`.
- `capacidad_cosechadora` es múltiplo de `grano_por_celda`.
- `ancho >= 1 + num_carros + num_cosechadoras` (el espacio de la fila 0 para la bodega y todas las bases).
- `alto >= 2`.
- `num_carros` y `num_cosechadoras` ≥ 1. En esta entrega, solo se acepta `1`; cualquier otro valor debe fallar con el mensaje «aún no soportado».
- Tasas y todas las cantidades son enteros positivos.
- `obstaculos`: se valida y se expande con `harvest_sim.datos.campo.expandir_obstaculos` (celdas `[x, y]` y regiones `{"inicio": [x, y], "tamano": [ancho, alto]}`; todo dentro del mapa, nada en la fila 0, el campo libre alcanzable desde la bodega). Si la lista resultante no está vacía, falla con «obstáculos aún no soportados».

**Grano esperado (una sola fórmula, en `harvest_sim/datos/campo.py`):** celdas de campo = celdas con `y ≥ 1` dentro del mapa, menos los obstáculos; grano esperado = celdas de campo × `grano_por_celda`. Nadie la vuelve a escribir: `Mundo.grano_total`, las métricas, las gráficas y las pruebas usan `grano_esperado`.

`seed` se guarda en el log aunque hoy no cambie el resultado (la simulación es determinista). Cuando se agregue incertidumbre, ya estará en su lugar.

---

## 4. Tiempo, mensajería y conflictos

### 4.1 Orden de un tick

Cada tick `t` ejecuta, en este orden fijo:

1. **Entrega de mensajes:** los mensajes enviados en el tick `t-1` pasan a los buzones de sus receptores.
2. **Paso de la cosechadora.**
3. **Paso del carro.**
4. **Snapshot** de ambos agentes al log (estado al final del tick).
5. Se revisa la condición de término (§5.4).

Un mensaje enviado en el tick `t` se lee a partir del tick `t+1`. Esto elimina condiciones de carrera y hace la ejecución reproducible.

**Convención de las tablas de estados (§5):** cada fila describe lo que pasa en un tick: condición, acción y siguiente estado. Salvo que se indique, una transición de estado **no incluye movimiento** en ese mismo tick; el movimiento es una acción del estado en que se encuentra el agente.

### 4.2 Conflictos de celda

Los agentes se mueven en el orden del tick (primero la cosechadora, después el carro), y cada uno ve las posiciones ya actualizadas. Reglas:

1. Un agente nunca se mueve a una celda ocupada por otro. Si la siguiente celda de su ruta está ocupada, **recalcula la ruta** con BFS tratando las celdas ocupadas por otros agentes como bloqueadas. Si no existe ruta, **espera un tick** (se queda en su celda).
2. La cosechadora sigue un camino fijo (la serpentina), así que no recalcula: si la siguiente celda de su camino está ocupada, espera. Estos ticks se cuentan en la métrica `ticks_bloqueados` y no se confunden con el tiempo ocioso.
3. Con esas reglas, un intercambio de posiciones es imposible (R4), porque cada agente ve la celda del otro como ocupada.
4. Para evitar que el carro se estacione justo en la siguiente celda de la serpentina (lo que frenaría a la cosechadora al reanudar), la celda objetivo del carro excluye la siguiente celda del camino de la cosechadora, siempre que haya otra opción (ver §5.2).

### 4.3 Duraciones

La duración de transferencia y de descarga depende de la cantidad:

```
duracion = ceil(cantidad / tasa)        # al menos 1 tick
```

Se calcula al **entrar** al estado temporal (la cantidad ya se conoce en ese momento).

Un estado temporal con duración `N` aparece en **exactamente `N` snapshots consecutivos** del log, empezando por el tick en que se entra al estado. La acción de salida ocurre en el tick siguiente al último de esos snapshots. Fija esta convención con tests, pues las métricas dependen de ella.

### 4.4 Buzón

Un objeto `Buzon` intermedia **todos** los mensajes, aunque la comunicación sea directa. Así, más adelante, un despachador podrá insertarse entre agentes sin modificar las máquinas de estados.

- Cada agente tiene una fila **FIFO** de entrada.
- El buzón asigna a cada mensaje un **`id` entero único y creciente** (1, 2, 3, …) al enviarlo.
- El buzón genera un evento por cada envío (`MENSAJE_ENVIADO`) y cada entrega (`MENSAJE_ENTREGADO`) y los entrega con `drenar_eventos()` para el log (§6.1). Además imprime cada envío y cada entrega en la consola (ver §6.3).

Hoy ningún mensaje se pierde, así que el `id` no se usa para decidir nada. Se incluye desde ahora porque es barato y porque lo necesitarán los acuses de recibo y la detección de duplicados (ver §13).

### 4.5 Mensajes de esta entrega

| Tipo | Emisor → Receptor | Payload | Cuándo |
|------|-------------------|---------|--------|
| `LLENA` | cosechadora → carro | `x`, `y` (posición de la cosechadora), `carga` actual | La cosechadora entra a `LLENA_ESPERANDO`. |
| `TRANSFERENCIA_TERMINADA` | cosechadora → carro | `cantidad`: unidades transferidas realmente | Termina la transferencia. |

Campos de todo mensaje: `id`, `tipo`, `emisor`, `receptor`, `tick_envio`, `payload`. En el log, cada envío lleva además su **performativa** (el acto comunicativo, como en KQML / FIPA-ACL): `LLENA` es `request` y `TRANSFERENCIA_TERMINADA` es `inform` (`harvest_sim.datos.formato.PERFORMATIVAS`; ver `docs/ontologia.md`).

**Sobre `cantidad`:** es exactamente lo que cedió la cosechadora, no un valor fijo ni la capacidad. Cuando la cosechadora entrega una carga parcial al final, `cantidad` es menor que su capacidad. El carro no actúa con ese valor (la transferencia física ya ocurrió en el mundo, ver §5.1), pero lo registra y los tests verifican que coincide con su carga. Importa porque el mismo mensaje tendrá que cubrir después el caso en que la cosechadora deposita ella misma en la bodega (ver §13).

---

## 5. Agentes

Ambos son agentes reactivos con estado interno, implementados como máquinas de estados. Sin planeación más allá de lo descrito, sin aprendizaje.

### 5.1 Cosechadora (`cosechadora_1`)

**Memoria:** índice actual en su camino, carga actual, contador de estado temporal, su casilla de inicio.

**Camino predefinido:** serpentina sobre el campo (filas `y = 1 … alto-1`): la fila 1 de izquierda a derecha, la fila 2 de derecha a izquierda, y así. Se genera una vez al inicio. El primer punto del camino es `(0, 1)`.

**Estados:** `EN_BASE`, `YENDO_A_CAMPO`, `COSECHANDO`, `LLENA_ESPERANDO`, `TRANSFIRIENDO`, `REGRESANDO_A_BASE`, `FIN`.

| Estado actual | Condición | Acción | Siguiente estado |
|---|---|---|---|
| `EN_BASE` (estado inicial) | Siempre, en el tick 0 | — | `YENDO_A_CAMPO` |
| `YENDO_A_CAMPO` | No ha llegado a `path[0]` | Un paso por la ruta BFS hacia `path[0]` (§4.2 si hay conflicto) | — |
| `YENDO_A_CAMPO` | Llegó a `path[0]` | Cosecha esa celda en el mismo tick (carga `+= grano_por_celda`) y evalúa la carga (ver abajo) | `COSECHANDO` o `LLENA_ESPERANDO` |
| `COSECHANDO` | Quedan celdas en el camino | Avanza a la siguiente celda y la cosecha en el mismo tick; evalúa la carga (ver abajo) | `COSECHANDO` o `LLENA_ESPERANDO` |
| `LLENA_ESPERANDO` | El carro está en una celda vecina **y** en estado `ESPERANDO_TRANSFERENCIA` | Calcula `cantidad = δ` y la duración (§4.3) | `TRANSFIRIENDO` |
| `LLENA_ESPERANDO` | En cualquier otro caso | Espera, inmóvil | — |
| `TRANSFIRIENDO` | Contador no agotado | Decrementa | — |
| `TRANSFIRIENDO` | Contador agotado | Ejecuta la transferencia en el mundo (`δ` pasa de la cosechadora al carro, R6), envía `TRANSFERENCIA_TERMINADA` con `cantidad` | `COSECHANDO` si quedan celdas en el camino; si no, `REGRESANDO_A_BASE` |
| `REGRESANDO_A_BASE` | No ha llegado a su casilla | Un paso por la ruta BFS (la bodega está bloqueada, R9) | — |
| `REGRESANDO_A_BASE` | Llegó a su casilla | — | `FIN` |

**Evaluación de la carga** (después de cosechar una celda): si `carga == capacidad_cosechadora`, **o** si era la última celda del camino (entonces la carga es parcial), envía `LLENA` y pasa a `LLENA_ESPERANDO`. En otro caso sigue en `COSECHANDO`.

Notas:

- **La transferencia física la hace el mundo, de forma atómica**, en el tick de salida de `TRANSFIRIENDO` (mediante una función del mundo, no modificando directamente la carga del otro agente). El mensaje `TRANSFERENCIA_TERMINADA` informa del hecho. Así, el grano nunca se pierde aunque en el futuro se pierdan mensajes, y R7 se cumple en cada tick.
- Como el carro siempre llega vacío (viene de su base, tras descargar) y su capacidad es mayor o igual, `δ` es siempre toda la carga de la cosechadora. La fórmula con `min` se mantiene porque más adelante la base será reutilizada con otras capacidades.
- Detectar que el carro está vecino y listo es **percepción directa del mundo** (se leen posición y estado del carro), no un mensaje. Se acepta como simplificación. Se exige el estado `ESPERANDO_TRANSFERENCIA` para que un carro que solo pasa junto a la cosechadora no dispare la transferencia.
- Si la cosechadora llena su carga justo en la última celda, solo envía `LLENA` una vez; al terminar la transferencia pasa a `REGRESANDO_A_BASE`.

### 5.2 Carro (`carro_1`)

**Memoria:** carga, ruta actual, celda objetivo, contador de estado temporal, su casilla de inicio. Empieza el tick 0 en su casilla de inicio.

**Estados:** `EN_BASE`, `YENDO_A_COSECHADORA`, `ESPERANDO_TRANSFERENCIA`, `YENDO_A_BODEGA`, `DESCARGANDO`, `REGRESANDO_A_BASE`.

| Estado actual | Condición | Acción | Siguiente estado |
|---|---|---|---|
| `EN_BASE` | Fila de entrada vacía | Nada | — |
| `EN_BASE` | Fila con un `LLENA` | Extrae el mensaje (FIFO), elige la celda objetivo, calcula la ruta con BFS | `YENDO_A_COSECHADORA` |
| `YENDO_A_COSECHADORA` | No ha llegado | Un paso por la ruta (§4.2 si hay conflicto) | — |
| `YENDO_A_COSECHADORA` | Llegó al objetivo | — | `ESPERANDO_TRANSFERENCIA` |
| `ESPERANDO_TRANSFERENCIA` | Llega `TRANSFERENCIA_TERMINADA` | Lee `cantidad`, la registra y calcula la ruta hacia la bodega | `YENDO_A_BODEGA` |
| `YENDO_A_BODEGA` | No ha llegado a `(0,0)` | Un paso por la ruta | — |
| `YENDO_A_BODEGA` | Llegó a `(0,0)` | Calcula la duración de descarga (§4.3) | `DESCARGANDO` |
| `DESCARGANDO` | Contador no agotado | Decrementa | — |
| `DESCARGANDO` | Contador agotado | Entrega la carga a la bodega (`carga = 0`), calcula la ruta hacia su casilla | `REGRESANDO_A_BASE` |
| `REGRESANDO_A_BASE` | No ha llegado | Un paso por la ruta | — |
| `REGRESANDO_A_BASE` | Llegó a su casilla | — | `EN_BASE` |

**Regla clave (carro ocupado):** si llegan mensajes `LLENA` mientras el carro no está en `EN_BASE`, **se quedan en la fila**, nunca se descartan. El carro solo los revisa estando en `EN_BASE`, es decir, después de descargar todo y regresar a su casilla. Los ticks que la cosechadora pasa en `LLENA_ESPERANDO` por esta causa son tiempo ocioso real y la métrica principal.

**Celda objetivo:** una celda vecina (4-vecindad) a la posición recibida en el mensaje, dentro del mapa y libre. Reglas para elegir, en orden:

1. Se excluye la celda bloqueada (la bodega) y las ocupadas por otros agentes.
2. Se excluye la **siguiente celda del camino de la cosechadora**, salvo que sea la única opción (§4.2, regla 4).
3. Entre las restantes, la de menor distancia BFS desde la posición actual del carro.
4. En empate, el orden `N, E, S, O`.

Como la cosechadora está inmóvil mientras espera, el objetivo no cambia durante el viaje.

**BFS:** la ruta trata como bloqueadas las celdas ocupadas por otros agentes. El carro puede cruzar cualquier otra celda del campo (no se modela daño al cultivo). BFS determinista: expande vecinos en el orden `N, E, S, O`.

### 5.3 Estado `FIN` y reposo

- La cosechadora queda en `FIN` en su casilla de inicio.
- El carro vuelve a `EN_BASE`, que también es su estado de reposo final.

### 5.4 Fin de la simulación

La simulación termina cuando se cumplen a la vez: cosechadora en `FIN`, carro en `EN_BASE`, fila de entrada del carro vacía, carga del carro igual a 0 y grano entregado igual al grano total del campo. También termina con error registrado si se alcanza `max_ticks`.

---

## 6. Telemetría

### 6.1 Formato del log (`runs/<escenario>/trace.json`, formato 2.1)

Un único archivo JSON por corrida. **Lo arma `TraceBuilder`** (`harvest_sim/datos/trace.py`); nadie lo escribe a mano. La definición ejecutable está en `harvest_sim/datos/formato.py` y la valida `tools/validar_trace.py`. Ejemplo real: `tests/fixtures/trace_ejemplo.json`. Decisiones: entradas del 2026-11-15 y 2026-11-16 en `docs/decisiones.md`.

```json
{
  "schema_version": "2.1",
  "meta": {"escenario": "escenario_a", "seed": 0, "total_ticks": 49, "clase": "AccountabilityRecord"},
  "config": {"...": "copia de la configuración usada"},
  "mundo": {"ancho": 8, "alto": 7, "bodega": [0, 0], "bases": {"carro_1": [1, 0], "cosechadora_1": [2, 0]},
            "grano_por_celda": 1, "obstaculos": [], "clase_celdas": "SemanticMapCell"},
  "agentes": [{"id": "cosechadora_1", "tipo": "cosechadora", "clase": "AutonomousAgriculturalRobot", "capacidad": 10, "base": [2, 0]}],
  "ticks": [{"tick": 0, "cambios": [{"tipo": "AGENTE", "id": "cosechadora_1", "set": {"pose": {"x": 2, "y": 0, "orientacion": "S"}, "estado": "EN_BASE", "carga": 0}}], "checksum": "..."}],
  "metricas": {"...": "§6.2"}
}
```

- `ticks` es un arreglo ordenado con **solo los ticks que tienen cambios** (el 0 siempre, con el estado inicial completo). `meta.total_ticks` es el último tick. El tick 0 es el estado inicial, antes del primer paso; los pasos empiezan en el tick 1.
- `cambios` es una lista de **eventos tipados**, en este orden dentro del tick: `MENSAJE_ENTREGADO`, `AGENTE`, (`CELDA_COSECHADA` | `DEPOSITO` | `BLOQUEO`), `MENSAJE_ENVIADO`.

| Evento | Campos | Lo genera |
|---|---|---|
| `AGENTE` | `id`, `set` (solo los campos que cambiaron entre `pose`, `estado` y `carga`) | `TraceBuilder`, comparando los `registro()` de cada tick |
| `CELDA_COSECHADA` | `celda`, `agente` | `Mundo.cosechar` |
| `DEPOSITO` | `agente`, `cantidad`, `entregado_total` | `Mundo.depositar` |
| `BLOQUEO` | `agente` | `Mundo.registrar_bloqueo` (el agente no pudo moverse porque la celda estaba ocupada) |
| `MENSAJE_ENVIADO` | `id`, `tipo_mensaje`, `performativa`, `de`, `a`, `payload`, `entrega_en` | `Buzon.enviar` |
| `MENSAJE_ENTREGADO` | `id`, `a` | `Buzon.entregar` |

- **Checksum por tick:** primeros 16 caracteres hexadecimales de SHA-256 sobre el JSON canónico (claves ordenadas, sin espacios) de `{tick, cambios}`.
- **Registro de agente** (`agente.registro(tick)`, lo que el agente entrega en cada tick): `tick`, `agent_id`, `tipo`, `pose {x, y, orientacion}`, `estado` (texto) y `carga {actual, capacidad}`. Sin `intencion`, sin `objetivo`, sin `checksum`.
- **Solo hechos explícitos:** el log no guarda rutas ni intenciones; el visor no interpreta nada (decisión del 2026-11-15).
- **Clases de la ontología** (`meta.clase`, `agentes[].clase`, `mundo.clase_celdas`): las pone `TraceBuilder` (ver `docs/ontologia.md`).
- Reproducibilidad: dos corridas con el mismo config producen el mismo `trace.json` byte a byte (primer nivel indentado, un tick por línea).

### 6.2 Métricas

Se calculan **desde el log** con `calcular_metricas(trace)` (`harvest_sim/datos/metricas.py`) y se guardan en `metricas`. Funcionan con cualquier número de agentes: las magnitudes de cada agente van como **promedio entre los agentes de ese tipo** y el detalle de cada uno en `por_agente`; las del sistema, como total. Definiciones completas en `docs/decisiones.md` (2026-11-15 y 2026-11-16).

| Métrica | Definición |
|---------|------------|
| `tiempo_ocioso_cosechadora` | Ticks en `LLENA_ESPERANDO`, promedio por cosechadora. **Métrica principal.** No incluye `TRANSFIRIENDO`. |
| `porcentaje_ocioso` | Lo anterior entre los ticks totales, en %. |
| `tiempo_transfiriendo` | Ticks en `TRANSFIRIENDO`, promedio por cosechadora. |
| `espera_promedio_por_ciclo` | Largo medio de las esperas (rachas de `LLENA_ESPERANDO`); la lista de cada cosechadora está en `por_agente`. |
| `tick_fin_cosecha` | Tick del último `TRANSFERENCIA_TERMINADA`. Compara sin el ruido del regreso a bases. |
| `tiempo_completacion` | Tick en que termina la simulación (`meta.total_ticks`). |
| `distancia_cosechadora`, `distancia_carro` | Movimientos (cambios de celda), promedio por agente del tipo. |
| `distancia_total` | Suma de todos los agentes. |
| `distancia_cosechadora_carro_promedio` / `_minima` / `_maxima` | Distancia Manhattan de cada cosechadora al carro más cercano, en cada tick. |
| `utilizacion_carro` | Fracción de ticks fuera de `EN_BASE`, promedio por carro. |
| `ticks_bloqueados` | Eventos `BLOQUEO` (total). |
| `colisiones` | Ticks en que se viola R3 o R4. Debe ser 0, pero se mide. |
| `num_ciclos`, `mensajes_enviados` | Mensajes `LLENA` enviados; mensajes por tipo. |
| `grano_cosechado_total`, `grano_total_entregado`, `grano_esperado_total`, `porcentaje_entregado` | Grano cosechado, depositado, esperado (§3) y entregado entre esperado. |
| `por_agente` | Detalle de cada agente (incluye `ticks_por_estado` y `espera_por_ciclo`). |

**El combustible no se mide en esta entrega.** Se deja como nota para la siguiente (§13).

### 6.3 Log de consola

Mientras corre la simulación se imprime un registro legible de lo que pasa. Es distinto del `trace.json`: el `trace.json` es para máquinas (visor, métricas, tests); la consola es para personas (seguir y depurar una corrida). Los mensajes **siguen** guardándose en `trace.json`: la propuesta se compromete a mostrar un log de corrida con cada mensaje completo y versionado, y las métricas `num_ciclos` y `tick_fin_cosecha` lo usan.

- Se usa el módulo estándar `logging`, con loggers `harvest_sim.*` (sin dependencias nuevas).
- Nivel `INFO` (por defecto): cada envío y cada entrega de mensaje, cada cambio de estado de un agente y cada `DEPOSITO`. Nivel `DEBUG`: además, cada celda cosechada y cada movimiento.
- Formato fijo, sin fecha ni hora real (así dos corridas imprimen exactamente lo mismo):

```
t=014 | cosechadora_1 | COSECHANDO -> LLENA_ESPERANDO
t=014 | MSG #1 LLENA cosechadora_1 -> carro_1 {x: 5, y: 1, carga: 10} (se entrega en t=015)
t=015 | MSG #1 entregado a carro_1
t=015 | carro_1 | EN_BASE -> YENDO_A_COSECHADORA
t=031 | carro_1 deposita 10 en la bodega (entregado: 10/48)
```

- **Quién imprime qué:** el `Buzon` imprime los mensajes; `simulacion.py` imprime los cambios de estado (compara el estado de cada agente antes y después de su paso) y los depósitos. Los agentes no imprimen.
- **CLI:** `INFO` por defecto; `--silencioso` (solo advertencias y errores); `--detallado` (`DEBUG`).
- El log de consola no afecta la simulación ni el contenido de `trace.json`.

---

## 7. Visualización y gráficas

### 7.1 Visor 2D (`viz/viewer.py`)

Lee un `trace.json` y lo reproduce. **No importa nada de la simulación**: así el mismo log servirá luego para Unity.

Del log toma `mundo` (para dibujar el grid, la bodega y las bases) y va aplicando los `cambios` a medida que avanza el tick (para pintar las celdas cosechadas). **No deduce reglas del juego**: no infiere qué se cosechó a partir de las posiciones de la cosechadora.

Debe mostrar: el grid; celdas cosechadas vs. por cosechar (colores distintos); la bodega y las casillas de inicio (marcadas distinto); ambos agentes con su orientación; una barra de carga por agente; el estado actual de cada uno como texto; el número de tick y la trayectoria reciente (estela). Controles: pausa/reanudar, avance paso a paso, velocidad ajustable.

Herramienta sugerida: `pygame`. Si alguien prefiere `matplotlib.animation`, es válido mientras cumpla lo anterior y lea el log.

### 7.2 Gráficas (`viz/plots.py`)

Con `matplotlib`, desde el log, en `runs/<escenario>/plots/` (una pregunta por gráfica; con varios agentes muestran promedios y `--agente <id>` muestra una cosechadora):

1. **Línea de tiempo de estados** de todos los agentes (tipo Gantt). La más informativa para ver el tiempo ocioso.
2. **Tiempo ocioso acumulado.**
3. **Distancia cosechadora–carro más cercano**, por tick.
4. **Flujo del grano:** en la bodega + en tránsito = cosechado, contra el total esperado.
5. y 6. **Mapas de calor** de la espera y del tráfico por celda.

Entre escenarios (`runs/comparacion/`): comparación de 6 indicadores y tabla resumen (`resumen.csv` con todas las métricas, `resumen.md` con las principales). Experimentos (`tools/correr_experimento.py`): barrido de parámetros con resumen estadístico y gráfica de sensibilidad. El **dashboard** (Giovanni, `viz/dashboard.py`) junta el entorno, los indicadores y lo experimental.

Todas con título, ejes con unidades y leyenda legible.

---

## 8. Escenarios de evaluación

Tres configuraciones fijas, deterministas. Los valores son sugerencias; ajústalos si hace falta, pero cada escenario debe producir resultados distintos y todos deben incluir al menos un ciclo con carga parcial final:

| Escenario | `ancho × alto` | `capacidad_cosechadora` | `capacidad_carro` | `tasa_transferencia` | `tasa_descarga` |
|---|---|---|---|---|---|
| A | 8 × 7 | 10 | 20 | 2 | 4 |
| B | 10 × 9 | 15 | 30 | 3 | 5 |
| C | 8 × 7 | 5 | 10 | 1 | 1 |

`grano_por_celda = 1`, `num_carros = num_cosechadoras = 1`, `seed = 0` en todos.

El escenario C (capacidad pequeña, transferencia y descarga lentas) busca provocar que la cosechadora se vuelva a llenar mientras el carro todavía no regresa a su base, para observar espera por carro ocupado. Si con una cosechadora esto no ocurre en ningún escenario, es un resultado válido de la línea base; regístralo en `docs/decisiones.md`.

Documenta en el README que la simulación es determinista a propósito.

---

## 9. Pruebas

Con `pytest`. Mínimo:

| Test | Verifica |
|------|----------|
| `test_movimiento_dentro_del_mapa` | R1 |
| `test_movimiento_un_paso_cuatro_vecinos` | R2 |
| `test_no_comparten_celda` | R3 |
| `test_no_intercambian_posicion` | R4 |
| `test_conflicto_espera_o_recalcula` | Si la siguiente celda está ocupada, el agente recalcula o espera (§4.2) |
| `test_transferencia_solo_entre_vecinos` | R5, incluido que un carro vecino que solo pasa (sin estar en `ESPERANDO_TRANSFERENCIA`) no activa la transferencia |
| `test_transferencia_respeta_capacidad` | R6 (incluye el caso en que `Q_carro − q_carro < q_cosechadora`, con capacidades de prueba) |
| `test_conservacion_de_grano` | R7, en cada tick de una corrida completa |
| `test_celda_cosechada_una_vez` | R8 |
| `test_cosechadora_no_entra_a_bodega` | R9 |
| `test_casillas_de_inicio` | Bodega en `(0,0)`, bases de carros en `(1..n, 0)`, de cosechadoras en `(n+1..n+m, 0)`, con `n` y `m` genéricos |
| `test_inicio_y_regreso_a_base` | Ambos agentes empiezan en su casilla y terminan en ella |
| `test_serpentina_cubre_todo_el_campo` | El camino visita cada celda del campo exactamente una vez |
| `test_carga_parcial_final` | Si el campo no es múltiplo de la capacidad, se atiende la última carga parcial |
| `test_cantidad_en_mensaje` | `TRANSFERENCIA_TERMINADA` lleva `cantidad` igual a lo cedido, y coincide con la carga del carro (incluida la carga parcial) |
| `test_duracion_depende_de_cantidad` | `ceil(cantidad / tasa)` en transferencia y descarga; una carga parcial dura menos |
| `test_mensaje_pendiente_no_se_pierde` | Con el carro ocupado, el `LLENA` espera en la fila y el carro sale al volver a `EN_BASE` |
| `test_fifo` | La fila de entrada respeta el orden de llegada |
| `test_ids_de_mensaje` | Los `id` son únicos y crecientes, y aparecen en el log |
| `test_mensaje_se_lee_al_tick_siguiente` | Un mensaje enviado en `t` no es visible en `t` |
| `test_duracion_estados` | Un estado de duración `N` dura `N` snapshots |
| `test_reproducibilidad` | Dos corridas iguales producen `trace.json` idéntico |
| `test_checksum_de_todo_el_log` | El checksum de cada tick se verifica al recalcularlo y `validar_trace` no da errores |
| `test_config_invalida` | Las validaciones de §3 fallan con mensaje claro (incluido el ancho mínimo y `num_*` ≠ 1) |
| `test_terminacion` | La corrida termina y cumple las condiciones de §5.4 |
| `test_cosechar_registra_cambio` | `Mundo.cosechar` genera un `CELDA_COSECHADA` (celda y agente) y `depositar` un `DEPOSITO` (con `entregado_total`), entregados por `drenar_eventos()` |
| `test_cambios_reconstruyen_el_mapa` | Con `reconstruir(trace)`, al final están cosechadas exactamente las `celdas_de_campo(mundo)`, cada una una sola vez |
| Pruebas de Datos | El formato, las métricas, el campo, el validador, las gráficas y los experimentos tienen sus propias pruebas (`test_trace.py`, `test_metricas.py`, `test_campo.py`, `test_validador.py`, `test_plots.py`, `test_experimentos.py`) |
| `test_log_de_consola_de_mensajes` | El `Buzon` emite un registro de log por cada envío y por cada entrega (con `caplog`) |

---

## 10. Arquitectura del código y herramientas

**Herramientas:** Python 3.12, solo biblioteca estándar para la simulación; `pytest` para pruebas; `matplotlib` y `pygame` para visualización. Dependencias con versiones fijas en `requirements.txt`. Entorno virtual (`venv`). Las instrucciones deben funcionar en una máquina limpia (Linux, macOS, Windows).

**Estructura de carpetas:**

```
harvest_sim/
├── README.md
├── requirements.txt
├── config/
│   ├── escenario_a.json
│   ├── escenario_b.json
│   └── escenario_c.json
├── docs/
│   └── decisiones.md          # registro de decisiones de diseño
├── src/harvest_sim/
│   ├── config.py              # carga y validación
│   ├── mundo.py               # grid, bodega, bases, serpentina, BFS, transferencia
│   ├── mensajes.py            # TipoMensaje, Mensaje, Buzon
│   ├── cosechadora.py         # estados y lógica
│   ├── carro.py               # estados y lógica
│   ├── simulacion.py          # bucle de ticks, condición de término
│   ├── datos/                 # trace 2.1, métricas, campo, validador, experimentos (Joel)
│   ├── telemetria.py          # fachada de datos/ (compatibilidad)
│   └── cli.py                 # python -m harvest_sim.cli config/escenario_a.json
├── viz/
│   ├── viewer.py
│   ├── dashboard.py
│   └── plots.py
├── tools/                     # validar_trace, correr_experimento, generar_trace_ejemplo
├── tests/
└── runs/                      # salidas (no versionar)
```

**Principios:**

- `mundo`, `agentes`, `mensajes`, `simulacion`, `telemetria` y `viz` son módulos separados. Los agentes no conocen la telemetría ni la visualización.
- La simulación es la única fuente de verdad. Visor y gráficas solo leen `trace.json`.
- Los agentes no se leen entre sí, salvo la percepción de posición y estado del §5.1, que pasa a través del objeto `Mundo`.
- El grano solo cambia de manos mediante funciones del `Mundo` (cosechar, transferir, depositar). Eso hace que R6, R7 y R8 se verifiquen en un solo lugar.

### Contrato de interfaces

Fija estos nombres en la primera reunión; todos los bloques dependen de ellos.

```python
from enum import Enum
from dataclasses import dataclass, field

class EstadoCosechadora(str, Enum):
    EN_BASE = "EN_BASE"
    YENDO_A_CAMPO = "YENDO_A_CAMPO"
    COSECHANDO = "COSECHANDO"
    LLENA_ESPERANDO = "LLENA_ESPERANDO"
    TRANSFIRIENDO = "TRANSFIRIENDO"
    REGRESANDO_A_BASE = "REGRESANDO_A_BASE"
    FIN = "FIN"

class EstadoCarro(str, Enum):
    EN_BASE = "EN_BASE"
    YENDO_A_COSECHADORA = "YENDO_A_COSECHADORA"
    ESPERANDO_TRANSFERENCIA = "ESPERANDO_TRANSFERENCIA"
    YENDO_A_BODEGA = "YENDO_A_BODEGA"
    DESCARGANDO = "DESCARGANDO"
    REGRESANDO_A_BASE = "REGRESANDO_A_BASE"

class TipoMensaje(str, Enum):
    LLENA = "LLENA"
    TRANSFERENCIA_TERMINADA = "TRANSFERENCIA_TERMINADA"

@dataclass
class Mensaje:
    tipo: TipoMensaje
    emisor: str
    receptor: str
    tick_envio: int
    payload: dict = field(default_factory=dict)
    id: int = 0                      # lo asigna el Buzon al enviar

class Buzon:
    def enviar(self, mensaje: Mensaje) -> int: ...                  # asigna id; se entrega en tick+1; evento MENSAJE_ENVIADO
    def entregar(self, tick: int) -> None: ...                      # inicio de cada tick; evento MENSAJE_ENTREGADO
    def leer(self, agent_id: str) -> "Mensaje | None": ...          # saca el siguiente (FIFO)
    def hay_pendientes(self, agent_id: str) -> bool: ...
    def drenar_eventos(self) -> list[dict]: ...                     # eventos del tick para el log; vacía la lista

class Mundo:
    config: Config                                                   # los agentes leen aquí tasa_transferencia y tasa_descarga
    bodega: tuple[int, int]                                          # (0, 0)
    grano_total: int                                                 # = datos.campo.grano_esperado(descripcion())
    def base_de(self, agent_id: str) -> tuple[int, int]: ...
    def camino_serpentina(self) -> list[tuple[int, int]]: ...
    def posicion(self, agent_id: str) -> tuple[int, int]: ...
    def estado_de(self, agent_id: str) -> str: ...                   # percepción del estado de otro agente
    def ruta_bfs(self, origen, destino, bloqueadas: set) -> "list | None": ...
    def vecinos(self, celda) -> list[tuple[int, int]]: ...
    def cosechar(self, agent_id: str, celda) -> int: ...             # devuelve unidades cosechadas
    def transferir(self, de: str, a: str, cantidad: int) -> int: ... # devuelve δ realmente transferida
    def depositar(self, agent_id: str) -> int: ...                   # entrega la carga a la bodega; evento DEPOSITO
    def registrar_bloqueo(self, agent_id: str) -> None: ...          # evento BLOQUEO (no pudo moverse: celda ocupada)
    def drenar_eventos(self) -> list[dict]: ...                      # CELDA_COSECHADA, DEPOSITO y BLOQUEO del tick; vacía la lista
    def descripcion(self) -> dict: ...                               # ancho, alto, bodega, bases, grano_por_celda, obstaculos (va en trace["mundo"])

# Interfaz común de agente
class Agente:
    agent_id: str
    def paso(self, tick: int, mundo: Mundo, buzon: Buzon) -> None: ...
    def registro(self, tick: int) -> dict: ...                       # tick, agent_id, tipo, pose, estado, carga (§6.1)

# Datos (Joel): TraceBuilder(config, mundo.descripcion(), catalogo); agregar_tick(t, registros, eventos) en cada tick;
# construir(); calcular_metricas(trace). Ver docs/equipo/README.md §3.
```

Pueden ajustar firmas si lo necesitan, pero cualquier cambio se anuncia al equipo y se anota en `docs/decisiones.md`.

---

## 11. Bloques de trabajo y dependencias

Cada bloque puede trabajarse en paralelo una vez acordado el contrato del §10.

| Bloque | Contenido | Archivos | Depende de |
|---|---|---|---|
| **A. Mundo y rutas** | Grid, bodega, bases, serpentina, BFS con celdas bloqueadas, funciones de grano, validación de config, tests R1, R2, R8, R9, serpentina, casillas, config inválida | `config.py`, `mundo.py`, `config/*.json` | Contrato |
| **B. Agentes y mensajería** | Máquinas de estados de ambos agentes, buzón FIFO con ids, resolución de conflictos, bucle de ticks, condición de término | `mensajes.py`, `cosechadora.py`, `carro.py`, `simulacion.py` | Contrato; API de `Mundo` del bloque A (puede usar un stub al inicio) |
| **C. Telemetría y métricas** | Trace 2.1, checksum, escritura de `trace.json`, métricas, gráficas, experimentos | `datos/`, `viz/plots.py`, `tools/` | Contrato; datos de B (puede probar con registros falsos) |
| **D. Visor y calidad** | Visor desde `trace.json`, tests de flujo y de reglas, README, `requirements.txt`, `cli.py` | `viz/viewer.py`, `tests/`, `README.md` | Contrato; `trace.json` de C (puede empezar con uno hecho a mano) |

**Primer hito (sábado):** una corrida de extremo a extremo, aunque sea fea. Mejor un esqueleto que corre que piezas perfectas aisladas.

---

## 12. Definición de terminado

La entrega está lista cuando:

- [ ] `python -m harvest_sim.cli config/escenario_X.json` corre y produce `trace.json` y gráficas para los tres escenarios.
- [ ] `pytest` pasa completo.
- [ ] El visor reproduce un log de principio a fin.
- [ ] Las métricas de los tres escenarios están calculadas y comparadas (tabla y gráfica de comparación), y el dashboard las muestra.
- [ ] La conservación de grano (R7) se cumple en las tres corridas.
- [ ] Dos corridas del mismo escenario dan logs idénticos.
- [ ] El README explica instalación y ejecución, y se probó en un entorno virtual nuevo.
- [ ] `docs/decisiones.md` registra cada decisión no cubierta por este documento.

---

## 13. Notas para entregas siguientes (no implementar ahora)

Para que el diseño no las bloquee:

- **Combustible.** Se ignora por completo en esta entrega: ni parámetros, ni métrica, ni gráfica. Más adelante, las casillas de inicio de cada agente serán también su punto de recarga, y la métrica de combustible servirá como métrica de sostenibilidad de la rúbrica. Estará disponible sin cambiar la estructura de las bases.
- **Mensajería no confiable.** Cuando los mensajes puedan perderse, duplicarse o llegar tarde, habrá que manejar algo parecido a redes: acuses de recibo (`ACK`), reintentos con límite de tiempo, y detección de duplicados usando el `id` de mensaje. El `id` y el buzón central ya existen para eso. También habrá que definir el estado de respaldo del agente cuando no llegue respuesta.
- **Cosechadora que descarga ella misma.** Hay dos formas de vaciar la cosechadora: (1) el carro viene y recibe la carga (la que se implementa ahora) o (2) la cosechadora lleva la carga a la bodega y regresa a su base. Si se implementa la segunda, el mensaje de fin de transferencia tendrá que cubrir ese caso (por ejemplo, con `cantidad` igual a 0 o con un tipo nuevo), y la descarga en bodega pasará a ser también un estado de la cosechadora.
- **Varios agentes.** La bodega es una sola celda: con varios carros habrá competencia por `(0,0)` (cuello de botella), que es un caso de conflicto por un recurso. Las casillas de inicio ya están definidas para `n` carros y `m` cosechadoras.
- **Resto de extensiones:** obstáculos y terreno variable en `Mundo`; rendimiento por parcela; un despachador entre agentes a través del `Buzon`; A\* con reserva de celdas en el tiempo; despacho anticipado del carro (la mejora que se comparará contra esta línea base); visualización en Unity leyendo el mismo `trace.json`.

---

## 14. Preguntas frecuentes

**¿Por qué solo una cosechadora y un carro si el reto es multiagente?**
Porque esta es la línea base: el caso más simple que ya contiene el problema de coordinación (la cosechadora espera mientras el carro viaja). Con un agente de cada tipo pueden validarse las reglas físicas, los mensajes y las métricas antes de agregar conflictos entre agentes del mismo tipo. El diseño (bases, ids de agente, buzón) está pensado para crecer.

**¿Qué es exactamente lo que vamos a mejorar después?**
El tiempo ocioso de la cosechadora (`tiempo_ocioso_cosechadora`). Lo que se implementa aquí es la versión *reactiva*: el carro sale solo cuando la cosechadora ya está llena. La mejora será que el carro salga antes, anticipando el llenado, y se medirá contra los valores de esta línea base en los mismos escenarios.

**¿Por qué no hay aleatoriedad? ¿Para qué sirve la seed?**
La incertidumbre está fuera del alcance y la línea base debe ser repetible. La seed se guarda en el config y en el log para que, cuando se agregue variación, las corridas sigan siendo reproducibles. Por ahora, los tres escenarios distintos (A, B, C) hacen el papel de las tres «seeds» que pide el checkpoint.

**¿Qué pasa si la cosechadora se llena cuando el carro todavía no vuelve?**
El mensaje `LLENA` queda en la fila de entrada del carro y la cosechadora espera detenida. El carro no revisa su fila hasta estar en `EN_BASE`, es decir, después de descargar y regresar a su casilla. Esos ticks de espera son el tiempo ocioso que queremos medir.

**¿Por qué el carro regresa a su base antes de atender el siguiente mensaje, y no sale directo desde la bodega?**
Es una simplificación deliberada para la línea base: una sola regla de decisión, en un solo estado. Optimizar eso (por ejemplo, desviarse al terminar de descargar) es el tipo de mejora que se hará después.

**¿Quién mueve el grano: la simulación o el mensaje?**
La simulación (el `Mundo`), de forma atómica al terminar la transferencia. El mensaje `TRANSFERENCIA_TERMINADA` solo informa al carro, y lleva la `cantidad` para que quede registrada y para cubrir después otros casos. Así, aunque se pierda un mensaje en el futuro, el grano no desaparece y la conservación (R7) se mantiene.

**¿Por qué la transferencia dura distinto según la cantidad?**
Para que cargas parciales (por ejemplo, la última carga del campo) no tarden lo mismo que una carga completa. `duracion = ceil(cantidad / tasa)`, con la tasa en el config.

**¿Por qué la cosechadora sabe que el carro llegó sin recibir un mensaje?**
Porque solo se definieron dos mensajes (`LLENA` y `TRANSFERENCIA_TERMINADA`), y la cosechadora percibe su entorno: ve si el carro está en una celda vecina y en el estado correcto. Es una simplificación aceptada. Si más adelante se agrega un mensaje de llegada, solo cambiaría esa condición.

**¿Por qué la cosechadora no recalcula su ruta cuando algo le bloquea el paso?**
Su camino (la serpentina) es fijo por diseño: es un agente reactivo simple con estado. Si la siguiente celda está ocupada, espera. El carro, en cambio, sí recalcula con BFS. La celda donde el carro se estaciona se elige para que casi nunca bloquee a la cosechadora.

**¿Por qué BFS y no A\*?**
En un grid sin costos variables ni obstáculos, BFS da el camino más corto y es lo más simple. A\* con reserva de celdas en el tiempo llegará cuando haya varios carros (problema 3 de la propuesta). La función `ruta_bfs` está separada para poder reemplazarla.

**¿Por qué el orden del tick es primero la cosechadora y luego el carro?**
Para que el resultado sea determinista y que no haya ambigüedad cuando los dos compiten por una celda: el segundo en moverse ve la posición ya actualizada del primero. Cualquier orden fijo sirve; lo importante es que no cambie.

**¿Por qué un mensaje enviado en el tick `t` se lee hasta `t+1`?**
Para evitar que el resultado dependa del orden de ejecución dentro del tick. Es la misma convención que se usa en simulaciones por pasos discretos.

**¿Por qué los mensajes tienen `id` si no se pierden?**
Porque cuando se simule la pérdida o duplicación de mensajes, los acuses de recibo y la deduplicación necesitarán un identificador. Cuesta una línea hoy y evita cambiar el esquema después. Además ayuda a seguir un mensaje en el log.

**¿Qué es el checksum del log y para qué sirve?**
Un hash de cada tick del log (`{tick, cambios}`, sin el propio campo `checksum`). Permite detectar ticks dañados o editados a mano. `verificar_checksums` y el validador lo recalculan y lo comparan.

**¿Por qué el visor y las gráficas no importan la simulación?**
Para que la simulación sea la única fuente de verdad y el visor funcione con cualquier `trace.json`, incluido el que, más adelante, leerá Unity. Si el visor necesita un dato que no está en el log, hay que agregarlo al log, no importarlo.

**¿Y el combustible? La rúbrica pide una métrica de sostenibilidad.**
Se deja para la siguiente entrega (§13). La estructura de bases ya prevé que sean puntos de recarga. No agregues parámetros ni métricas de combustible por ahora.

**¿Dónde queda el modelo matemático que pide la rúbrica?**
Este documento define el comportamiento; el modelo formal debe escribirse en el reporte y coincidir con el código. Un resumen para partir: el estado del sistema es, por agente, `(pose, estado, carga)` más la máscara de celdas cosechadas y el contenido de los buzones; las acciones son las de las tablas del §5; las transiciones son esas mismas tablas; las restricciones son R1 a R9; y el costo es `J = λ1·T_completación + λ2·D_total + λ3·N_colisiones + λ4·W_ocioso` (sin el término de combustible por ahora). Las métricas del §6.2 son los términos de `J`.

**Algo no está especificado. ¿Qué hago?**
Elige la opción más simple que respete las reglas físicas y los nombres del contrato, impleméntala y anótala en `docs/decisiones.md` (qué decidiste, qué alternativa consideraste, por qué la descartaste). Si afecta a otro bloque, avísale al equipo.

**¿Puedo cambiar el nombre de un estado, un campo o una función del contrato?**
Solo si lo anuncias al equipo y lo anotas en `docs/decisiones.md`. Los nombres del §10 son lo único de lo que dependen todos los bloques a la vez.

**¿Puedo agregar dependencias?**
Evítalo. La simulación usa solo la biblioteca estándar. Para visualización y pruebas ya están `pygame`, `matplotlib` y `pytest`. Si necesitas otra, justifícala en `docs/decisiones.md` y fija su versión en `requirements.txt`.

**¿Cómo pruebo mi bloque sin esperar a los demás?**
Usa stubs o datos de mano que respeten el contrato del §10: un `Mundo` falso para B, registros inventados para C, un `trace.json` escrito a mano para D. El primer hito es una corrida completa, aunque tosca.

**¿Cómo corro un solo escenario o un solo test?**
Un escenario: `python -m harvest_sim.cli config/escenario_a.json`. Un test: `pytest tests/test_nombre.py::test_funcion`. Todo: `pytest`.

**¿Por qué el mapa se guarda como cambios y no como una foto por tick?**
Por dos motivos. (1) **Quién procesa el entorno:** es la simulación (Python), que ya sabe exactamente cuándo se cosecha una celda; el visor, hoy pygame y mañana Unity, solo recibe la instrucción «esta celda se cosechó en el tick `t`» y no necesita reimplementar reglas ni deducirlas de las posiciones. (2) **Tamaño:** una foto por tick crece como `ticks × celdas`; los cambios crecen solo con lo que realmente ocurre (cada celda cambia una vez). En un mapa de 8×7 la diferencia es pequeña, pero en un mapa grande y en 3D sí importa, y no cuesta nada hacerlo bien desde ahora. Los agentes también se guardan como cambios: solo los campos que cambiaron en cada tick (§6.1).

**¿Para qué el log de consola si ya existe `trace.json`?**
Son para cosas distintas. El `trace.json` es el registro completo y exacto, pensado para que lo lean programas (visor, métricas, tests). La consola es para que una persona siga la corrida en vivo y encuentre rápido qué pasó («¿cuándo se llenó? ¿por qué el carro no salió?»). Los mensajes se guardan en ambos: en el `trace.json` porque la propuesta se compromete a un log de corrida con cada mensaje completo, y en la consola para leerlos en vivo.
