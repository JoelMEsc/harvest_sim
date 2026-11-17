# `rutas.py` — qué se hizo y cómo explicarlo

**Autor:** Oswaldo · **Rama:** `branch-oswaldo-rutas` · **Archivos:** `src/harvest_sim/rutas.py`, `tests/test_rutas.py`
**Especificación:** §2 (vecindad, R1, R2, R9), §4.2 (conflictos de celda) y §5.2 (BFS y celda objetivo del carro).

**Resumen:** `rutas.py` es el módulo que sabe moverse por el mapa. Tiene 4 funciones **puras**: no guardan estado, no importan `Mundo` ni a los agentes, y con la misma entrada siempre devuelven lo mismo. Por eso se prueban solas, y el mundo, la cosechadora y el carro las usan sin depender unos de otros.

| Función | Para qué sirve | Quién la usa |
|---|---|---|
| `vecinos` | Las celdas a las que un agente puede moverse en un paso | `Mundo.vecinos`, `bfs` |
| `bfs` | La ruta más corta de A a B esquivando celdas bloqueadas | `Mundo.ruta_bfs` (cosechadora y carro) |
| `elegir_celda_objetivo` | Dónde se estaciona el carro junto a la cosechadora | Carro, al recibir `LLENA` |
| `siguiente_paso` | Un paso por la ruta, resolviendo choques con otros agentes | Carro (y cualquier agente que recalcule ruta) |

Estado: **9 de 9 tests pasan** y la suite completa queda en 114 pasados y 44 en skip (antes 105 y 53). Además, se probó con las ramas de Carlos, Emilio e Ilan sin romper nada nuevo.

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
