# `rutas.py` — qué se hizo y cómo explicarlo

**Autor:** Oswaldo · **Rama:** `branch-oswaldo-rutas` · **Archivos:** `src/harvest_sim/rutas.py`, `tests/test_rutas.py`
**Especificación:** primera entrega §2 (vecindad, R1, R2, R9), §4.2 (conflictos de celda) y §5.2 (BFS y celda objetivo del carro); segunda entrega §5 (reservas espacio-tiempo), §7 (costo de la oferta) y §10 (restricciones).

**Resumen:** `rutas.py` es el módulo que sabe moverse por el mapa. Todas sus funciones son **puras**: no guardan estado, no importan `Mundo` ni a los agentes, y con la misma entrada siempre devuelven lo mismo. Por eso se prueban solas, y el mundo, la cosechadora y el carro las usan sin depender unos de otros.

| Función | Para qué sirve | Quién la usa | Entrega |
|---|---|---|---|
| `vecinos` | Las celdas a las que un agente puede moverse en un paso | `Mundo.vecinos`, `bfs` | 1 |
| `bfs` | La ruta más corta de A a B esquivando celdas bloqueadas | `Mundo.ruta_bfs` (cosechadora y carro) | 1 |
| `elegir_celda_objetivo` | Dónde se estaciona el carro junto a la cosechadora | Carro | 1 |
| `siguiente_paso` | Un paso por la ruta, resolviendo choques (línea base) | Carro con un solo carro en modo `directa` | 1 |
| `distancias` | Distancia BFS desde una celda a todas | `estimar_costo`, combustible del carro | 2 |
| **`bfs_tiempo`** | Ruta en espacio-tiempo que respeta reservas: sin colisiones ni intercambios | Carro y cosechadora (Emilio) | 2 |
| `reservas_de_ruta` | Lo que un agente reserva a partir de su ruta | Carro y cosechadora | 2 |
| **`estimar_costo`** | Costo de la oferta en la subasta | Carro (al responder `SOLICITUD_SERVICIO`) | 2 |
| `clasificar_desvio` | Qué regla del §10 alargó una ruta (R3, R4, R10) | Carro (evento `RESTRICCION`) | 2 |

Estado: **19 pruebas pasan** (9 de la línea base y 10 nuevas). Las 4 funciones de la primera entrega no cambiaron: A, B y C dan el mismo `trace.json` byte a byte que antes. Las secciones 1 a 8 explican la primera entrega; la **segunda entrega empieza en la §9**.

---

## 1. El sistema de coordenadas

```
        x=0   x=1   x=2   x=3        y crece hacia ABAJO
y=0    [Bod]  [Bc]  [Bk]   .         fila 0 = fila de servicio
y=1      .     .     .     .         filas y ≥ 1 = campo
y=2      .     .     .     .
```

- `(x, y)`, con origen arriba a la izquierda. `x` crece a la derecha y `y` hacia abajo.
- Por eso el **norte es `y - 1`** y el sur es `y + 1`. Es el error más fácil de cometer.
- Bodega `(0, 0)`, base del carro `(1, 0)` y base de la cosechadora `(2, 0)`.

En el código, las 4 direcciones están en una constante, en el orden que manda la especificación:

```python
DIRECCIONES = ((0, -1), (1, 0), (0, 1), (-1, 0))   # N, E, S, O
```

**Todo el determinismo sale de este orden.** Si se cambia, cambian las rutas y los traces dejan de ser reproducibles.

---

## 2. `vecinos(celda, ancho, alto)`

Devuelve las celdas vecinas en vecindad de 4 (sin diagonales), en orden **N, E, S, O**, y descarta las que caen fuera del mapa.

```python
vecinos((1, 1), 4, 3)  == [(1, 0), (2, 1), (1, 2), (0, 1)]   # interior: las 4
vecinos((0, 0), 4, 3)  == [(1, 0), (0, 1)]                   # esquina: sin N ni O
```

Garantiza **R1** (nunca se sale del mapa) y **R2** (un paso, 4 vecinos).

---

## 3. `bfs(origen, destino, ancho, alto, bloqueadas)`

**BFS (búsqueda en anchura):** explora el mapa por "capas". Primero todas las celdas a 1 paso, luego todas las de 2 pasos, y así. La primera vez que llega al destino, ese camino es el más corto. Funciona porque en el grid todos los pasos cuestan lo mismo (1 tick).

Cómo está hecho:

1. Una fila (`collections.deque`) con las celdas por explorar; empieza con el origen.
2. Un diccionario `padre`: para cada celda descubierta guarda desde cuál celda se llegó a ella. También sirve de lista de "visitadas".
3. Saca una celda de la fila y revisa sus vecinos **en orden N, E, S, O**. Ignora los que ya visitó y los que están en `bloqueadas`. Los demás los anota con su padre y los mete a la fila.
4. Al descubrir el destino, reconstruye la ruta siguiendo los padres hacia atrás y la voltea.

Contrato de lo que devuelve:

| Caso | Devuelve |
|---|---|
| Hay ruta | Lista de celdas **sin el origen y con el destino** |
| `origen == destino` | `[]` |
| No hay ruta | `None` |
| El destino está bloqueado (p. ej. lo ocupa otro agente) | `None` |

```python
bfs((0, 0), (2, 0), 4, 3, set())      == [(1, 0), (2, 0)]
bfs((0, 1), (1, 0), 4, 3, set())      == [(0, 0), (1, 0)]   # cruza la bodega
bfs((0, 1), (1, 0), 4, 3, {(0, 0)})   == [(1, 1), (1, 0)]   # cosechadora: la rodea (R9)
```

**¿Por qué es determinista?** Suele haber varias rutas igual de cortas. Como siempre se exploran los vecinos en el mismo orden, BFS siempre encuentra la misma. Por ejemplo, de `(0, 0)` a `(2, 2)` siempre sale `[(1, 0), (2, 0), (2, 1), (2, 2)]`.

**¿Quién decide qué está bloqueado?** El que llama, no `bfs`. La cosechadora pasa la bodega más los otros agentes; el carro pasa solo los otros agentes, porque él sí entra a la bodega. Así la función sirve para los dos.

---

## 4. `elegir_celda_objetivo(origen, objetivo, ancho, alto, bloqueadas, evitar)`

Cuando la cosechadora se llena manda `LLENA` con su posición. El carro tiene que estacionarse en una **celda vecina** a ella. Esta función decide cuál, con las reglas del §5.2 en orden:

1. **Descarta** las vecinas fuera del mapa y las de `bloqueadas` (la bodega y las ocupadas por otros agentes).
2. **Evita** las de `evitar`, que es la siguiente celda de la serpentina, **salvo que sea la única opción**. Si el carro se estaciona justo ahí, le tapa el camino a la cosechadora cuando reanude.
3. Entre las que quedan, la de **menor distancia BFS** desde donde está el carro.
4. En **empate**, gana el orden N, E, S, O.
5. Si ninguna es alcanzable, devuelve `None`.

Ejemplo (es uno de los tests): mapa 5 × 4, la cosechadora `C` espera en `(2, 1)`, su siguiente celda es `(3, 1)` y el carro `K` está en `(4, 1)`.

```
        x=0   x=1   x=2   x=3   x=4
y=0    [Bod]   .     N     .     .
y=1      .     O    [C]    E    [K]        E = siguiente celda de la serpentina
y=2      .     .     S     .     .
y=3      .     .     .     .     .
```

| Candidata | Distancia BFS desde `K` | ¿Se puede? |
|---|---|---|
| N `(2, 0)` | 3 | sí |
| E `(3, 1)` | 1 | es la siguiente de la serpentina, así que se evita |
| S `(2, 2)` | 3 | sí |
| O `(1, 1)` | 5 (tiene que rodear a la cosechadora) | sí |

Resultado: N y S empatan a 3 y **gana N** por el orden. Sin la regla de "evitar" habría elegido E, que está a 1.

Detalles de implementación:
- Las distancias se miden tratando la celda de la cosechadora (`objetivo`) como bloqueada, porque el carro no puede pasar por encima de ella.
- Se recorren las vecinas en orden N, E, S, O y solo se cambia la elegida si la nueva es **estrictamente** más cercana (`<`). Así el desempate sale solo.
- Se guardan dos "mejores": la mejor fuera de `evitar` y la mejor dentro de `evitar` (respaldo). El respaldo solo se usa si no hay ninguna de las primeras.

---

## 5. `siguiente_paso(pos, ruta, destino, ancho, alto, ocupadas, bloqueadas_fijas)`

Es la resolución de conflictos del §4.2: cómo se mueve un agente un tick cuando puede haber otro agente en medio.

```
¿Ya estoy en el destino? ──sí──► (None, [])            ya llegó, no es bloqueo
        │ no
¿La siguiente celda de mi ruta está libre? ──sí──► (esa celda, resto de la ruta)
        │ no (ocupada)
Recalcular BFS tratando ocupadas + bloqueadas_fijas como bloqueadas
        │
¿Hay ruta nueva? ──sí──► (primer paso de la nueva ruta, resto)
        │ no
   (None, ruta)   → el agente espera este tick (y registra un BLOQUEO)
```

Ejemplo (mapa 4 × 3): el agente está en `(0, 1)`, va a `(2, 1)` y su ruta era `[(1, 1), (2, 1)]`, pero hay otro agente `X` en `(1, 1)`.

```
        x=0   x=1   x=2   x=3
y=0    [Bod]   .     .     .
y=1     [A]   [X]   dest   .
y=2      .     .     .     .
```

- Si **puede** pasar por la bodega (carro): recalcula y sale por arriba, `(0, 0) → (1, 0) → (2, 0) → (2, 1)`.
- Si **no** puede (cosechadora, R9): sale por abajo, `(0, 2) → (1, 2) → (2, 2) → (2, 1)`.
- Si además `(0, 2)` estuviera ocupada: no hay ruta y devuelve `(None, ruta)`, así que espera.

**¿Por qué así se cumplen R3 y R4?** Un agente nunca da un paso a una celda de `ocupadas`, así que dos agentes nunca terminan en la misma celda (R3). Tampoco pueden intercambiarse en un tick (R4): el que se mueve primero ve la celda del otro como ocupada y no puede entrar ahí.

Casos de borde que se decidieron (no venían en la especificación):
- **Ruta vacía o vieja** (su primera celda ya no es vecina de `pos`): se recalcula como si estuviera ocupada. Así un agente con una ruta desactualizada no da saltos.
- **No modifica la lista que recibe**: siempre devuelve una lista nueva. Así una función pura no le cambia el estado al agente a escondidas.

---

## 6. Los 9 tests (`tests/test_rutas.py`)

| Test | Qué verifica | Regla |
|---|---|---|
| `test_movimiento_dentro_del_mapa` | Todo vecino y toda celda de **todas** las rutas posibles, en 4 tamaños de mapa, están dentro del mapa | R1 |
| `test_movimiento_un_paso_cuatro_vecinos` | Celdas consecutivas de cada ruta (y de cada paso de `siguiente_paso`) están a distancia Manhattan 1: sin diagonales ni saltos | R2 |
| `test_vecinos_orden_nesw` | Orden N, E, S, O; esquinas y bordes; mapa de 1 celda; una celda no es vecina de sí misma | §2 |
| `test_bfs_ruta_mas_corta_y_determinista` | Para todos los pares de celdas de un mapa 5 × 4: longitud = distancia Manhattan (la mínima), sin el origen, con el destino, y misma ruta si se repite; además una ruta que rodea un muro | §5.2 |
| `test_bfs_respeta_bloqueadas_y_devuelve_none` | Nunca pisa una bloqueada; rodea la bodega si está bloqueada; `None` con destino encerrado, origen encerrado, destino bloqueado y mapa partido | R9, §5.2 |
| `test_bfs_origen_igual_destino` | Devuelve `[]`, aun rodeado | §5.2 |
| `test_celda_objetivo_excluye_siguiente_de_serpentina` | Evita la siguiente de la serpentina; la usa si es la única, o la única alcanzable; nunca devuelve la bodega ni una ocupada; `None` si no queda nada | §4.2 regla 4, §5.2 |
| `test_celda_objetivo_desempate_nesw` | N le gana a E, E a S, S a O; la distancia pesa más que el orden; si el carro ya es vecino, se queda | §5.2 |
| `test_siguiente_paso_recalcula_o_espera` | Paso libre; recalcula al estar ocupada (con y sin bodega bloqueada); espera si no hay ruta o el destino está ocupado; ruta vacía o vieja; ya llegó; no hay intercambio (R4) | §4.2, R3, R4 |

```bash
pytest tests/test_rutas.py -v
```

---

## 7. Cómo se conecta con lo de los demás

- **Carlos (`Mundo`)**: `Mundo.vecinos` y `Mundo.ruta_bfs` ya llaman a `rutas.vecinos` y `rutas.bfs`. Hasta ahora fallaban con `NotImplementedError`; con esto ya funcionan.
- **Emilio (cosechadora)**: usa `mundo.ruta_bfs` con `bloqueadas_fijas | ocupadas`. Cuenta con que `bfs` devuelva `None` si no hay ruta y `[]` si ya llegó, que es justo este contrato.
- **Carro (lo siguiente)**: al recibir `LLENA` llama `elegir_celda_objetivo(pos_carro, pos_cosechadora, ..., bloqueadas=ocupadas | {bodega}, evitar={siguiente de la serpentina})`. Cada tick de movimiento llama `siguiente_paso(...)`. Si devuelve `None` sin haber llegado, llama `mundo.registrar_bloqueo`.

---

## 8. Preguntas que te pueden hacer (y la respuesta corta)

- **¿Por qué BFS y no A\* o Dijkstra?** Todos los pasos cuestan lo mismo (1 tick), y en ese caso BFS ya da la ruta más corta. Es más simple y, con el orden fijo de vecinos, determinista. A\* convendría en mapas grandes o con costos distintos.
- **¿Por qué funciones puras?** Se prueban sin armar el mundo ni los agentes. Pudieron hacerse en paralelo con el trabajo de los demás y no tienen efectos escondidos.
- **¿Cómo garantizan que la simulación sea reproducible?** No hay aleatoriedad y todas las decisiones se desempatan con el mismo orden fijo, N, E, S, O. La misma configuración da el mismo trace.
- **¿Qué pasa si dos agentes quieren la misma celda?** Se mueven en orden (primero la cosechadora y luego el carro), y el segundo ya ve al primero en su nueva celda. Para él está ocupada: recalcula o espera. Esa espera cuenta como `ticks_bloqueados`, no como tiempo ocioso.
- **¿Por qué el carro no se estaciona en la siguiente celda de la serpentina?** Porque al terminar la transferencia la cosechadora querría avanzar justo ahí y quedaría bloqueada.
- **¿Qué cuesta?** Cada BFS visita cada celda a lo más una vez: `O(ancho × alto)`. `elegir_celda_objetivo` corre a lo más 4 BFS, uno por vecina.

---

# Segunda entrega: rutas en el tiempo

## 9. El problema: dos carros en un pasillo

Con un solo carro bastaba «si la siguiente celda está ocupada, recalcula». Con dos carros en un pasillo de una celda eso falla: los dos recalculan, ninguno cede y se bloquean mutuamente. La propuesta prometió **0 colisiones y 0 bloqueos con 2 carros en un pasillo**. La solución es planear en el **tiempo**: cada agente dice de antemano en qué celda va a estar en cada tick (lo **reserva**) y los demás planean alrededor de esas reservas. Es la idea de *Cooperative A\** (Silver, 2005), con BFS porque todos los pasos cuestan 1.

## 10. Convención de tiempo

Una entrada `(celda, t)` significa «el agente está en `celda` **al final** del tick `t`». En el `paso` del tick `t`, el agente está en `(pos, t − 1)`, así que llama `bfs_tiempo(pos, destino, t − 1, ...)` y el primer elemento de la ruta es la celda donde termina el tick `t`. Esto coincide con `mundo.nuevo_tick(t)`, que borra las reservas con tick `< t`.

## 11. `bfs_tiempo(origen, destino, tick, ancho, alto, bloqueadas, reservas, horizonte=10, permanencia=None)`

**Los nodos son pares `(celda, tick)`.** Desde cada nodo hay hasta 5 acciones, en el orden fijo **esperar, N, E, S, O** (determinista). Un paso de `c1` a `c2` entre `t` y `t + 1` es válido si:

1. `c2` está en el mapa y no en `bloqueadas` (obstáculos, bodega para cosechadoras): **R1, R10**;
2. mientras `t + 1 ≤ tick + horizonte`: `(c2, t + 1)` **no está reservada** por otro (**R3**) y **no hay intercambio**: si otro agente X tiene `(c2, t)` y `(c1, t + 1)`, no se puede ir de `c1` a `c2` (**R4**: se cruzarían en medio).

```
   t=0   A . B        A quiere ir a la derecha y B a la izquierda por un pasillo.
   t=1   . A B   ✗    B reservó (1,0) en t=2: A no puede ir de (1,0) a (2,0)
   t=2   . B A   ✗    mientras B va de (2,0) a (1,0) → sería un intercambio (R4).
```

**Llegada válida (permanencia).** No basta con llegar: el agente se va a quedar. Solo se acepta llegar al destino en `t` si nadie más lo tiene reservado en los `permanencia` ticks siguientes. Con `permanencia=None` (se estaciona: base, junto a la cosechadora) se revisa todo el horizonte; en la bodega el carro pasa `permanencia = ceil(carga / tasa_descarga)` ticks, así otro carro puede planear entrar en cuanto él se va.

**Después del horizonte las reservas ya no cuentan.** Los estados se colapsan a uno por celda (`(celda, None)`) y la búsqueda sigue como BFS normal, sin esperas, pero siempre sin obstáculos. Por eso **siempre termina**: hay a lo más `celdas × (horizonte + 1)` estados con tiempo más uno por celda. No hace falta el límite artificial de «4 × (ancho + alto) ticks» que sugería la guía, que además podía cortar rutas válidas en un laberinto.

**Contrato:** `[(celda, t), ...]` sin el origen y con el destino, un elemento por tick (una espera es la misma celda repetida); `[]` si `origen == destino`; `None` si el destino está bloqueado o no hay ruta. Sin reservas, la llegada es exactamente la distancia de `bfs`.

**¿Qué cuesta?** `O(ancho × alto × horizonte)`. En el escenario E (9 × 8) son ≈ 800 estados por búsqueda.

## 12. `reservas_de_ruta(origen, ruta, tick, horizonte, permanencia)`

Convierte una ruta en lo que se reserva: `(origen, tick)`, los pasos hasta `tick + horizonte` y, si la ruta termina antes, la celda final repetida (`permanencia` ticks **completos** aunque pasen del horizonte, o hasta el horizonte si se estaciona). Con `ruta == []` reserva quedarse en `origen`: así un agente quieto también avisa que ahí está.

## 13. `estimar_costo(desde, ticks_ocupado, hacia, ancho, alto, bloqueadas)`

El costo de la oferta en la subasta (§7): `ticks_ocupado` (lo que le falta al carro de su fila de servicios) más la distancia BFS desde `desde` hasta la **vecina libre más cercana** de la cosechadora (no se puede pasar por encima de ella). `0` pasos si ya es vecino; `None` si ninguna vecina es alcanzable.

Ejemplo de las pruebas (mapa 4 × 3): el carro en su base `(1, 0)` ya ganó un servicio en `(2, 1)` y llega una llamada desde `(3, 2)`:

| Política | Fila | Desde dónde sale | Costo |
|---|---|---|---|
| base | 1 paso + 2 transferir + 3 a la bodega + 2 descargar + 1 a su base = 9 | su base, 3 pasos | **12** |
| `encadenar_servicios` | 1 + 2 = 3 (le cabe, no pasa por la bodega) | junto a `(2, 1)`, 1 paso | **4** |
| `atender_desde_bodega` | 1 + 2 + 3 + 2 = 8 | la bodega, 4 pasos | **12** |

## 14. `clasificar_desvio(...)`

Para el evento `RESTRICCION` (§10, IEEE 7007) hay que saber **qué regla cambió la ruta**. Se compara cuánto tarda en llegar en cuatro versiones del problema:

| Comparación | Regla |
|---|---|
| BFS con obstáculos más largo que sin obstáculos | `R10_obstaculo` |
| ruta en el tiempo (sin chequeo de intercambio) más larga que la espacial | `R3_celda_ocupada` |
| ruta en el tiempo completa más larga que sin chequeo de intercambio | `R4_intercambio` |

Rodear la bodega no es R10 (no es un obstáculo). Si no hay ruta, no es un desvío: es un `BLOQUEO`.

## 15. Las pruebas nuevas (`tests/test_rutas.py`)

| Prueba | Qué verifica |
|---|---|
| `test_bfs_tiempo_sin_reservas_es_la_ruta_mas_corta` | Para todos los pares de un mapa 5 × 4, con y sin muro: llegada = distancia BFS, determinista, `[]` y `None` como `bfs` |
| `test_bfs_tiempo_respeta_reservas` | **El pasillo**: dos rutas opuestas por un hueco de 1 celda; la segunda espera, ninguna `(celda, t)` se repite y no hay intercambio |
| `test_bfs_tiempo_no_se_intercambia` | R4 en un mapa 2 × 1 (no hay ruta) y en 3 × 2 (rodea por abajo) |
| `test_bfs_tiempo_espera_y_horizonte` | Espera en vez de entrar a una celda reservada; reservas fuera del horizonte no cuentan |
| `test_bfs_tiempo_nunca_pisa_bloqueadas_ni_reservas` | Propiedad R1, R2, R3, R4, R10 en todas las rutas de un mapa con obstáculos y otro agente |
| `test_bfs_tiempo_permanencia` | Con permanencia corta cabe antes de que llegue otro; con larga, no |
| `test_reservas_de_ruta_recorta_y_rellena` | Recorta en el horizonte, rellena la celda final y reserva la estancia completa |
| `test_distancias`, `test_estimar_costo`, `test_clasificar_desvio` | Casos calculados a mano |

## 16. Preguntas que te pueden hacer (segunda entrega)

- **¿Por qué BFS en el tiempo y no A\*?** Todos los pasos cuestan 1 tick, así que BFS ya da la ruta que llega antes. A\* convendría en mapas grandes; el espacio aquí es de cientos de estados.
- **¿Por qué el orden «esperar primero»?** Entre dos rutas que llegan al mismo tiempo, prefiere esperar a dar una vuelta: gasta menos combustible y se mueve menos.
- **¿Qué es el horizonte?** Cuántos ticks hacia adelante cuentan las reservas (10). Más allá el futuro es incierto: cada agente replanea en cada tick, así que no tiene sentido planear el tick 50 con precisión.
- **¿Una espera es un bloqueo?** No. Esperar porque la ruta en el tiempo lo decidió es parte del plan. `BLOQUEO` es solo cuando no hay ninguna ruta aunque sin otros agentes sí la habría.
- **¿Cómo garantizan que no chocan?** Tres capas: las reservas (nadie planea entrar a una `(celda, t)` ajena), el chequeo de intercambio, y una regla conservadora en el carro: su primer paso nunca entra a una celda ocupada ahora mismo, aunque ese agente no haya reservado. Con esto se probaron 1128 corridas aleatorias con dobles (2 y 3 carros, las 4 estrategias) sin una sola colisión (ver `carro.md` §13).
