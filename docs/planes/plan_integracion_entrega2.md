# Plan de integración de la segunda entrega (ramas aux y PR)

> **Copia versionada, histórica:** el plan de integración de la segunda entrega (ya entregada). Las rutas al «scratchpad» eran carpetas temporales de trabajo y ya no existen.

> Documento personal de Joel, **fuera del repositorio**. Simula paso a paso el trabajo, como si se estuviera haciendo, para encontrar problemas **antes** de tocar el código. No lleva fechas (las maneja el equipo).
> Referencias: `harvest_sim/docs/especificacion_segunda_entrega.md` (la «spec»), `docs/equipo/<persona>/guia.md`, `docs/decisiones.md` y `tc2008b/plan_datos_entrega2.md` (mi parte, ya hecha).

---

## 0. Punto de partida (verificado al leer el código)

| Rama | Estado real | Pruebas |
|---|---|---|
| `development` (= `main`) | Primera entrega + docs del plan. `config.py` rechaza `num_* ≠ 1`, obstáculos y cualquier campo nuevo (`politica` da «campo desconocido»). `Mundo` sin reservas, azar, rendimiento, combustible ni restricciones. `simulacion.py` crea solo `cosechadora_1` y `carro_1`. `mensajes.py` solo con `LLENA` y `TRANSFERENCIA_TERMINADA`, entrega en `t+1` fijo. `cosechadora.py` con `carro_1` fijo y `camino_serpentina()` | verdes |
| `origin/branch-oswaldo-rutas` (2 commits) | `rutas.py`: `bfs_tiempo`, `reservas_de_ruta`, `estimar_costo`, `clasificar_desvio`, `distancias`, `HORIZONTE = 10`. `carro.py`: directa (v0.1) y contratista de la subasta, reservas, ceder paso y combustible. Todo **defensivo** (`getattr`/`hasattr`): sin la API nueva del mundo se comporta como v0.1 | **248 pasan**; A/B/C **idénticos byte a byte** a `development` |
| `origin/mario_giovanni_branch` (harvest_sim, 4 commits propios) | Visor y dashboard aceptan 2.1/2.2 (combustible y alertas). CLI con `--seed` y `--estrategia` | **234 pasan** sobre `development`. Su prueba `test_cli_rechaza_seed_negativa_y_estrategia_sin_contrato` **fallará** en cuanto exista `experimentos.ESTRATEGIAS` (mi rama): espera el texto «ESTRATEGIAS» en el error |
| Unity `origin/mario_giovanni_branch` (15 commits) | Lee 2.1/2.2, `TraceClient` habla con `/api/salud`, `/api/escenarios` (lee `escenarios[].nombre`) y `/api/escenarios/{n}/trace?seed=&estrategia=`: **coincide** con mi servidor. Único desajuste: `TraceLoader.cs:177` exige `cantidad` en `CELDA_COSECHADA` 2.2 (la spec la deja opcional) | EditMode tests propios; Unity 6000.3.7f1 está instalado localmente |
| `branch-joel` (local, 9 commits sin push) | Formato 2.2, validador, ejemplo 2.2, `ESTRATEGIAS`, servidor FastAPI, métricas y costo J, experimentos pareados, gráficas, exportador a Unity, decisiones | 269 pasan; 2 fallan solo hasta que entre lo de Mario (viewer/dashboard 2.1) |
| `branch-carlos`, `branch-emilio`, `branch-ilan` | Nada nuevo desde el 17 de noviembre | — |

Permisos: admin en `JoelMEsc/harvest_sim`; **push** en `GioMax102/harvest-simu-visualization`.

## 1. Reglas de trabajo para todo el plan

1. Nunca commit ni push directo a `development` ni `main`. Cada parte llega por **PR a `development`**.
2. **Cada PR debe quedar verde por sí solo** (`SDL_VIDEODRIVER=dummy MPLBACKEND=Agg pytest -q`), y la **regresión v0.1** (A/B/C con las mismas métricas) se revisa en cada PR que toque la simulación.
3. Antes de cada push, PR y merge, **pregunto a Joel** (el clasificador lo exige y es la regla del equipo). En el plan, cada punto donde hay que pedir permiso está marcado con 🔒.
4. Ramas aux: nacen de `development` actualizado; el nombre dice de quién es la parte (`branch-carlos-aux`, `branch-emilio-aux`, `mario-aux`). En cada commit se dice en el mensaje que se hizo «en nombre de» esa persona, para que la autoría de la parte quede clara en el reporte.
5. Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; descripciones de PR con `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
6. Los docs personales siguen fuera de git. Los docs de cada persona (`docs/equipo/<persona>/…`) se actualizan **en su rama aux** con lo que se hizo, para que la persona pueda explicarlo.
7. Trabajo en worktrees temporales del scratchpad para no mover `branch-joel`; se borran al terminar cada paso.

## 2. Orden y por qué no es el orden en que se pidió

Joel pidió: Carlos-aux → Emilio-aux → Oswaldo → Mario. El **trabajo** se piensa en ese orden (abajo está todo), pero el **orden de merge** tiene que seguir las dependencias para que `development` nunca quede rojo:

```
1. mario-aux (Python)   ─┐  arreglo de 1 prueba; no depende de nadie
2. branch-oswaldo-rutas ─┤  listo tal cual (defensivo, regresión idéntica)
3. branch-joel          ─┘  formato 2.2 / servidor / ESTRATEGIAS; resuelve el conflicto de decisiones.md en MI rama
4. ilan-aux (regresión) ──  red de seguridad ANTES de tocar mundo/simulación
5. branch-carlos-aux    ──  config + mundo + simulación N agentes + D/E/F (A/B/C v0.1)
6. branch-emilio-aux    ──  buzón + cosechadora administradora → D/E/F terminan
7. ilan-aux (integración) ─ pruebas de D/E/F, scripts
8. Unity mario-aux      ──  cantidad opcional; prueba con el servidor real
9. Datos (Joel)         ──  experimento real, traces a Unity, figuras y PDF
10. development → main  ──  release v0.2-entrega2
```

- **Oswaldo va antes que Carlos** (la pregunta «o si iba antes lo de Oswaldo»): sí. Su rama ya funciona sola, y que esté en `development` permite a carlos-aux probar el mundo nuevo **contra el carro real** y no contra dobles.
- **Mario antes que Joel**: así ni su rama ni la mía necesitan tocar archivos del otro. Mi rama arregla 2 pruebas solo con traer `development`.
- **Oswaldo antes que Joel**: el único conflicto (`docs/decisiones.md`, los dos agregamos al final) se resuelve en **mi** rama, sin tocar la suya.
- **Carlos antes que Emilio**, pero con un límite: con la cosechadora vieja, D/E/F **no pueden terminar** (dos cosechadoras recorrerían la misma serpentina y la segunda fallaría con «celda ya cosechada»). Por eso carlos-aux entrega D/E/F como **configuraciones válidas** (cargan y validan), y las corridas completas de D/E/F se activan en emilio-aux.
- **Ilan:** Joel no lo pidió explícitamente. Lo propongo porque la regresión debe existir **antes** de cambiar el mundo, y la spec §16 exige pruebas sin `skip`. **Pregunta para Joel (P1):** ¿hacemos también ilan-aux? Si no, en el paso 5 la regresión se revisa con un script fuera del repo (`reg.py`, ya usado) y las pruebas de integración de D/E/F van dentro de emilio-aux.

---

## Paso 1 — mario-aux (Python): revisar y arreglar la prueba de la CLI

**Revisión** (hecha): 234 pruebas pasan; visor y dashboard aceptan 2.2; la CLI aplica `ESTRATEGIAS[nombre].get("politica", …)`, compatible con mi formato `{"politica": {...}}`. Bien hecho. Un solo problema: la prueba supone que `ESTRATEGIAS` **no existe**.

**Lo que hago:**
```bash
git worktree add $S/wt_mario -b mario-aux origin/mario_giovanni_branch
```
En `tests/test_viewer.py::test_cli_rechaza_seed_negativa_y_estrategia_sin_contrato`, antes de la llamada con `--estrategia`:
```python
from harvest_sim.datos import experimentos
monkeypatch.delattr(experimentos, "ESTRATEGIAS", raising=False)  # la prueba es del caso «sin contrato»
```
(agrego `monkeypatch` a los parámetros). Así pasa con y sin mi rama. Agrego una segunda aserción para el caso con `ESTRATEGIAS` y una config sin `politica`: error que contiene «politica».

**Verifico:** `pytest -q` → 234 + 0 nuevas fallas en `development`; y cruzado: `git merge --no-commit branch-joel` en un worktree desechable → la prueba de la CLI pasa (luego `git merge --abort`).

🔒 push de `mario-aux` y PR «Visor, dashboard y CLI para el trace 2.2 (Mario Giovanni)» → `development`. En la descripción: qué es de Mario (todo) y qué se agregó (la prueba, 1 commit). 🔒 merge.

## Paso 2 — branch-oswaldo-rutas: revisión y PR sin aux

**Revisión** (hecha):
- 248 pruebas pasan; A/B/C idénticos byte a byte (mismo md5 de los ticks: `649f80ee2b`, `4c837c3d46`, `6b621d716e`).
- Cumple la guía y la spec §5–§7, §9 y §10: protocolo del contratista, costo con `estimar_costo`, rechazos `sin_capacidad`/`combustible`/`sin_ruta`, RESTRICCION por tramo, combustible con reserva, `registro()` con combustible opcional.
- API del mundo que **espera** (la tiene que dar carlos-aux, nombres exactos): `mundo.reservar(id, [(celda, t), …])`, `mundo.reservas(excepto=id)`, `mundo.camino(id)`, `mundo.duracion(cantidad, tasa)`, `mundo.combustible_para(id, celdas, ticks_encendido)`, `mundo.registrar_restriccion(id, regla, detalle)`, `mundo.obstaculos` (iterable de celdas), `mundo.config.politica` (dict), `mundo.config.combustible["reserva"]`, `mundo.posicion(id)` con `KeyError` si el id no existe, y que el mundo ponga `carro.tanque` y `carro.combustible`.
- Lo que espera de Emilio: `SOLICITUD_SERVICIO` con `servicio, x, y, carga, capacidad`; `TRANSFERENCIA_TERMINADA` con `servicio` (si falta, empareja por emisor); que la cosechadora reserve su celda cuando está quieta.
- Limitación documentada (3+ carros); ningún escenario la usa.

**Conclusión:** no necesita aux. 🔒 PR `branch-oswaldo-rutas` → `development` «Rutas en el tiempo y carro contratista (Oswaldo)». No hay conflictos contra `development` (las únicas líneas compartidas son el final de `decisiones.md`, y mi entrada todavía no está en `development`). 🔒 merge.

## Paso 3 — branch-joel: traer development y abrir mi PR

```bash
git checkout branch-joel && git fetch && git merge origin/development
```
- **Conflicto esperado:** `docs/decisiones.md` (Oswaldo 2026-11-23 y yo 2026-11-24 agregamos al final). Se resuelve dejando **las dos entradas en orden de fecha** (Oswaldo primero).
- **Pruebas esperadas:** las 269 mías + las de Oswaldo + las de Mario, **0 fallas** (las 2 del viewer/dashboard se arreglan con lo de Mario; su prueba de la CLI ya no depende de `ESTRATEGIAS`). Referencia: la integración de prueba del día anterior dio 292 pasan con 1 falla, que es justamente esa prueba ya arreglada en el paso 1.
- Regresión A/B/C con `reg.py`: mismas métricas (`134/50/126`, `193/72/194`, `262/153/186`). Mi formato agrega `combustible` solo si el registro lo trae: hoy nadie lo pone, así que sin cambios.

🔒 push `branch-joel` (9 commits + merge) y PR «Datos de la segunda entrega: trace 2.2, servidor, métricas, costo J y experimentos (Joel)» (texto en `tc2008b/pr_textos.md`). 🔒 merge.

## Paso 4 — ilan-aux, parte 1: la red de seguridad (si P1 = sí)

```bash
git worktree add $S/wt_v01 v0.1-entrega1          # el código de la primera entrega, tal cual
git worktree add $S/wt_ilan -b branch-ilan-aux origin/development
```
1. En `wt_v01` corro A, B y C y guardo las **métricas del nivel superior** (sin `por_agente`) en `tests/fixtures/metricas_v0_1.json` de `wt_ilan`. No se recalculan nunca con el código nuevo.
2. `tests/test_regresion.py`:
```python
@pytest.mark.parametrize("nombre", ["escenario_a", "escenario_b", "escenario_c"])
def test_regresion_linea_base(nombre):
    esperadas = json.loads(FIXTURE.read_text())[nombre]
    metricas = ejecutar(cargar_config(CONFIG / f"{nombre}.json"))["metricas"]
    for clave, valor in esperadas.items():
        assert metricas[clave] == pytest.approx(valor), clave
```
   Solo compara las claves que existían en v0.1 (las nuevas, como `costo_total`, se ignoran).
3. Verifico: pasa hoy en `development`. Y la prueba de que sirve: cambio a propósito `tasa_descarga` en una copia del escenario A → falla (y lo deshago).

🔒 push y PR «Regresión contra v0.1 (en nombre de Ilan)». 🔒 merge.

---

## Paso 5 — branch-carlos-aux: config, mundo, simulación y escenarios

```bash
git worktree add $S/wt_carlos -b branch-carlos-aux origin/development   # ya trae Oswaldo, Mario, Joel e ilan-aux
```
Commits pequeños, uno por tarea de la guía de Carlos; después de **cada** commit corro `pytest -q` y la regresión.

### 5.1 `config.py` (tarea 1)

```python
POLITICA_POR_DEFECTO = {"asignacion": "directa", "umbral_aviso": 1.0, "atender_desde_bodega": False,
                        "encadenar_servicios": False, "espera_propuestas": 2, "reintento_subasta": 3}
INCERTIDUMBRE_POR_DEFECTO = {"rendimiento": None,   # None = {minimo: grano_por_celda, maximo: grano_por_celda}
                             "duracion_extra_maxima": 0,
                             "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}}
COMBUSTIBLE_POR_DEFECTO = {"tanque_cosechadora": 100000, "tanque_carro": 100000,
                           "consumo_por_celda_cosechadora": 2.0, "consumo_por_celda_carro": 1.0,
                           "consumo_por_tick_encendido": 0.5, "reserva": 0.15, "tasa_recarga": 0}
COSTO_POR_DEFECTO = {"pesos": dict(PESOS_COSTO)}   # importado de datos.metricas para no duplicar números
```
- `Config` gana `politica`, `incertidumbre`, `combustible`, `costo` con `field(default_factory=...)`. Los **campos obligatorios** siguen siendo los 12 de v0.1 + `obstaculos`; los 4 nuevos son **opcionales** (cambio en la revisión de sobrantes/faltantes: `faltantes` se calcula solo sobre los obligatorios).
- `_con_defectos(nombre, valor, defectos)`: recursiva para los dicts anidados (`rendimiento`, `retraso_mensajes`, `pesos`); rechaza claves desconocidas con `config: politica.xxx desconocido`; devuelve un dict **nuevo** (no muta los defectos compartidos).
- `rendimiento` por defecto = `{minimo: grano_por_celda, maximo: grano_por_celda}` (depende de otro campo, por eso `None` en la tabla).
- Validaciones (mensaje con la ruta del campo, p. ej. `config: politica.umbral_aviso debe estar en (0, 1]`):
  `asignacion ∈ {directa, subasta}`; `0 < umbral_aviso ≤ 1` (número, no `bool`); booleanos estrictos; `espera_propuestas` entero ≥ 2; `reintento_subasta` entero ≥ 1; `1 ≤ minimo ≤ maximo` enteros; `duracion_extra_maxima` entero ≥ 0; `0 ≤ probabilidad ≤ 1`; `maximo` entero ≥ 0; tanques y consumos > 0; `0 ≤ reserva < 1`; `tasa_recarga ≥ 0`; pesos ≥ 0 y las 6 claves de `TERMINOS_COSTO`.
- Quito los tres «aún no soportado». Nueva: `alto − 1 ≥ num_cosechadoras` (cada franja necesita al menos una fila).
- El «múltiplo» de `capacidad_cosechadora` se exige solo si `minimo == maximo` (contra ese valor); con rendimiento variable la cosechadora se considera llena antes (spec §8).
- Obstáculos: `expandir_obstaculos` (ya valida mapa, fila 0 y alcanzabilidad) y se aceptan.

**Pruebas que se rompen y cómo quedan** (`tests/test_config.py`, archivo de Ilan; el cambio es obligado por la spec): los 3 casos «aún no soportado» pasan a ser casos **válidos** (`num_carros: 2` carga; obstáculos cargan). Agrego un caso por validación nueva y uno de «secciones ausentes = defectos». Los 3 JSON actuales cargan y `asdict` da lo mismo de antes **más** las 4 secciones con defectos.

### 5.2 Franjas y obstáculos (tarea 2)

- `self.obstaculos: frozenset[Celda]` (quito el `raise`).
- `bloqueadas_fijas(id) = obstaculos | ({bodega} si es cosechadora)`.
- `ruta_bfs` agrega `self.obstaculos` a `bloqueadas` siempre (defensivo; con 0 obstáculos no cambia nada).
- `franjas()`: filas `1..alto−1`, cuento celdas libres por fila, total `N`. Para `k = 1..m−1` el corte va después de la fila donde la suma acumulada queda **más cerca** de `k·N/m`; en empate, la franja de arriba se queda con la fila (spec: «las primeras franjas se quedan con la fila sobrante»). Cada franja ≥ 1 fila y ≥ 1 celda, o `ValueError`.
  - D (10×8, 70 celdas, m=2): objetivo 35; acumulados 10, 20, 30, 40…; 30 y 40 empatan a 5 → corte después de la fila 4: franjas de 40 y 30.
  - E (9×8, muro en y=3 con hueco en x=4): filas 1–7 con 9, 9, 1, 9, 9, 9, 9 = 55; objetivo 27.5; acumulados 9, 18, 19, 28 → corte después de la fila 4: 28 y 27.
- `camino(id)`: serpentina de la franja **con la paridad global** (fila impar → x creciente), sin obstáculos. Con m = 1 y sin obstáculos es **exactamente** la serpentina de v0.1. `camino_serpentina()` = `camino("cosechadora_1")`.

### 5.3 Reservas (tarea 3)

```python
def reservar(self, agent_id, ruta):            # ruta: [(celda, t), ...]
    if not ruta: return
    desde = min(t for _, t in ruta)
    self._reservas = {k: a for k, a in self._reservas.items() if not (a == agent_id and k[1] >= desde)}
    for celda, t in ruta:
        dueño = self._reservas.get((tuple(celda), t))
        if dueño is None: self._reservas[(tuple(celda), t)] = agent_id   # no pisa a otro (prioridad = quien reservó antes)
def reservas(self, excepto=None): return {k: a for k, a in self._reservas.items() if a != excepto}
def nuevo_tick(self, t): self._reservas = {k: a for k, a in self._reservas.items() if k[1] >= t}
```
Decisión: si dos agentes piden la misma `(celda, t)`, **gana quien reservó primero** (es el orden del tick: cosechadoras, luego carros). No debería pasar porque cada uno planea con las reservas de los demás, pero así nunca se sobrescribe a otro en silencio.

### 5.4 Azar, rendimiento y duraciones (tarea 4)

- `azar(fuente)`: `self._azar.setdefault(fuente, random.Random(f"{config.seed}-{fuente}"))`.
- Rendimiento: si `minimo == maximo`, todas valen eso **sin** llamar al generador; si no, recorro las celdas libres del campo en orden `(y, x)` y sorteo `randint(minimo, maximo)`. `rendimiento(celda)` (0 fuera del campo). `descripcion()` agrega la matriz `rendimiento` **solo si** es variable (si no, la descripción queda igual que en v0.1 → `test_descripcion_del_mundo` no cambia).
- `grano_total = grano_esperado(descripcion())` (mi `campo.py` ya suma la matriz). Con rendimiento fijo distinto de `grano_por_celda` (p. ej. `minimo = maximo = 2` y `grano_por_celda = 1`), la descripción **sí** debe llevar la matriz: la regla queda «la matriz va si algún valor ≠ `grano_por_celda`».
- `cosechar`: `cantidad = rendimiento(celda)`; capacidad con esa cantidad; evento con `"cantidad"`. `grano_cosechado()` = suma de las cantidades.
- `duracion(cantidad, tasa)`: `duracion_ticks(cantidad, tasa) + (azar("duracion").randint(0, extra) if extra > 0 else 0)`.

`test_cosechar_registra_cambio` (Ilan) compara el evento exacto: agrego `"cantidad": 1` a lo esperado (cambio pedido por la spec §12).

### 5.5 Combustible y restricciones (tarea 5)

- `registrar(agente)`: además de la posición, `agente.tanque = agente.combustible = float(tanque_<tipo>)` (tipo por el prefijo del id).
- `actualizar_combustible(agente, se_movio)`:
  1. si se movió: resta `consumo_por_celda_<tipo>`; si no se movió y su estado no es `EN_BASE` ni `FIN`: resta `consumo_por_tick_encendido`;
  2. `combustible = max(0.0, round(c, 2))`; si llegó a 0, `logger.warning` (R11 se cumple, pero es señal de mala configuración);
  3. si está en **su** base, en `EN_BASE` o `FIN`, y `combustible < tanque`: recarga todo (`tasa_recarga == 0`) o `min(tasa, faltante)`; evento `{"tipo": "RECARGA", "agente", "cantidad", "nivel"}` redondeados.
- `combustible_para(id, celdas, ticks_encendido) = celdas · consumo_por_celda_<tipo> + ticks_encendido · consumo_por_tick_encendido`.
- `registrar_restriccion(id, regla, detalle)`: evento `RESTRICCION`; valida `regla ∈ formato.REGLAS_RESTRICCION`.

**Decisión D-A (la anoto en `decisiones.md`):** con los tanques por defecto (100 000 L) los agentes **sí** recargan al volver a su base (la regla del §9 no distingue), así que A/B/C tendrán eventos `RECARGA` y `combustible` en el log. **No cambia ninguna métrica de v0.1** (las métricas de v0.1 salen de estados, posiciones y depósitos) y la reserva nunca se activa. La spec dice «(nunca recargan)»: lo corrijo a «(nunca se acercan a la reserva)». Alternativa descartada: no registrar combustible con los valores por defecto (dos comportamientos distintos según si la sección existe; más confuso).

### 5.6 `simulacion.ejecutar` con N agentes (tarea 6)

```python
cosechadoras = [Cosechadora(f"cosechadora_{j}", config.capacidad_cosechadora) for j in 1..m]
carros       = [Carro(f"carro_{i}", config.capacidad_carro) for i in 1..n]
agentes = cosechadoras + carros                         # orden del tick y del catálogo (= v0.1 con 1 + 1)
buzon = Buzon()            # emilio-aux cambia esta línea por Buzon(mundo.azar("mensajes"), p, máximo)
...
for tick in 1..max_ticks:
    mundo.nuevo_tick(tick); buzon.entregar(tick)
    inicio = {a.agent_id: a.posicion for a in agentes}
    for a in agentes: a.paso(tick, mundo, buzon)          # + logs como hoy
    for a in agentes: mundo.actualizar_combustible(a, a.posicion != inicio[a.agent_id])
    eventos = buzon.drenar_eventos() + mundo.drenar_eventos()   # mismo orden que v0.1
    ...RECARGA y RESTRICCION en INFO...
    if terminado(): break
```
- `terminado()`: todas las cosechadoras en `FIN`; todos los carros en `EN_BASE`, `carga == 0` y `not getattr(c, "servicios", ())`; ningún agente con mensajes pendientes; `entregado == grano_total`.
- El buzón queda `Buzon()` en este PR: el `Buzon` con retraso es de Emilio y todavía no existe. No se pierde nada: el único escenario con retraso (F) no puede correr hasta el paso 6 de todos modos. (Ver la vuelta 3 de la revisión: el borrador tenía aquí un «puente» con `inspect.signature`, innecesario.)

**Hasta aquí con los agentes de `development`:** A/B/C funcionan (1 + 1, la cosechadora vieja usa `camino_serpentina()`, que ahora delega en `camino()`). D/E/F **no** (la cosechadora vieja tiene `carro_1` y la serpentina completa). Eso se activa en el paso 6.

### 5.7 Escenarios D, E y F (tarea 7)

| | D (recurso escaso) | E (pasillo) | F (estrés) |
|---|---|---|---|
| Mapa | 10 × 8 | 9 × 8 | 12 × 9 |
| Agentes (carros, cosechadoras) | 1, 2 | 2, 2 | 2, 2 |
| `grano_por_celda` | 1 | 1 | 1 |
| Capacidades (cosechadora, carro) | 8, 16 | 8, 16 | 8, 12 |
| Tasas (transferencia, descarga) | 2, 4 | 2, 4 | 2, 4 |
| Obstáculos | — | `{"inicio":[0,3],"tamano":[4,1]}`, `{"inicio":[5,3],"tamano":[4,1]}` | `{"inicio":[3,3],"tamano":[2,2]}`, `{"inicio":[8,5],"tamano":[2,2]}` |
| `incertidumbre` | defecto | defecto | rendimiento 1–2; duración extra 2; retraso 0.2 / 2 |
| `combustible` | defecto | defecto | tanques 60 (cosechadora) y 40 (carro), `tasa_recarga` 10 |
| `max_ticks` | 5000 | 5000 | 5000 |

F se ajusta (tanques) **después** del paso 6, cuando corre de verdad, hasta que haya ≥ 1 `RECARGA` y ≥ 1 `RESTRICCION` `combustible_reserva` en la seed 0, y termine en las 20 seeds con las 4 estrategias. Cuenta rápida para empezar: la cosechadora gasta 2 L por celda; con una carga de ≈ 6 celdas (8 / 1.5) + regreso a la base (≈ 10 celdas) son ≈ 32 L + encendido, contra una reserva de 9 L de un tanque de 60: recarga más o menos cada carga.

En este PR, la prueba de D/E/F es solo `cargar_config` + `Mundo(config)` (franjas, obstáculos y `descripcion()` válidos), en `tests/test_mundo.py` (`test_franjas`, `test_no_hay_franja_con_obstaculo`).

### 5.8 Pruebas del mundo (en `tests/test_mundo.py`, de Ilan; mínimas para que el PR demuestre lo que hace)

`test_franjas` (D y E: cubren cada celda libre una vez y con los tamaños 40/30 y 28/27), `test_reservar_reemplaza_futuras`, `test_reservas_excepto`, `test_nuevo_tick_limpia`, `test_azar_reproducible_por_fuente` (mismo seed → misma secuencia; agregar otra fuente no cambia la primera), `test_rendimiento_fijo_no_usa_azar` y `_sorteado`, `test_duracion_sin_y_con_extra`, `test_combustible_consumo_y_recarga_solo_en_base`, `test_combustible_nunca_negativo`, `test_eventos_recarga_y_restriccion`.

### 5.9 Verificación del paso 5

- `pytest -q` verde (incluida la regresión del paso 4 y las 248 de Oswaldo, ahora contra el mundo real: sus dobles no cambian).
- `reg.py`: A/B/C con las mismas métricas de v0.1.
- Validador: los traces de A/B/C son 2.2 válidos (con `combustible` y `RECARGA`).
- Prueba de humo del carro real con el mundo real: en un script fuera del repo, A con `politica.asignacion = "subasta"` y la cosechadora vieja → **no** debe usarse como evidencia (la cosechadora vieja no manda `SOLICITUD_SERVICIO`, el carro nunca sale y llega a `max_ticks`): confirma que la subasta necesita el paso 6. Lo anoto como esperado, no como error.
- Docs: `docs/equipo/carlos/mundo.md` (nuevo) con la API final, la regla de franjas con los ejemplos de D y E, la decisión D-A y qué pruebas cubren qué. Entrada en `decisiones.md`.

🔒 push y PR «Mundo de la segunda entrega: config, franjas, obstáculos, reservas, azar y combustible (en nombre de Carlos)». 🔒 merge.

---

## Paso 6 — branch-emilio-aux: buzón y cosechadora administradora

```bash
git worktree add $S/wt_emilio -b branch-emilio-aux origin/development   # ya con carlos-aux
```

### 6.1 `mensajes.py` (tarea 1)

- `TipoMensaje` con los 7 tipos (los 5 nuevos con el comentario de su payload).
- `Mensaje` gana `entrega_en: int = 0` (lo pone el buzón).
- `Buzon(azar=None, probabilidad=0.0, maximo=0)`:
  - `enviar`: `entrega_en = t + 1`; **solo si** `azar is not None and probabilidad > 0 and maximo >= 1` se llama `azar.random()`, y si sale `< probabilidad`, `entrega_en += azar.randint(1, maximo)`. (El `maximo >= 1` evita `randint(1, 0)` si alguien pone probabilidad > 0 con máximo 0.)
  - El evento usa ese `entrega_en`, y el log de consola también.
  - `entregar(t)`: entrega los de `entrega_en == t` **ordenados por id**; los demás siguen en tránsito.
- `simulacion.py`: la línea del buzón pasa a `Buzon(mundo.azar("mensajes"), retraso["probabilidad"], retraso["maximo"])` con `retraso = config.incertidumbre["retraso_mensajes"]` (único cambio a un archivo de Carlos).

Pruebas (`tests/test_mensajes.py`): las actuales iguales; con `p = 1` y `maximo = 2`, `entrega_en ∈ [t+2, t+3]` y se entrega exactamente ese tick; con `p = 0` el generador no se llama (un doble que falla si lo llaman); orden por id en empate.

### 6.2 Cosechadora: franja, carro asignado y obstáculos (tarea 2)

- Lee `politica` igual que el carro: `{**POLITICA_POR_DEFECTO, **(config.politica or {})}`, importando `POLITICA_POR_DEFECTO` de `config.py` (una sola fuente de valores por defecto; el carro de Oswaldo conserva su copia defensiva).
- `self._camino = mundo.camino(id) if hasattr(mundo, "camino") else mundo.camino_serpentina()` (los dobles de `test_cosechadora.py` solo tienen `camino_serpentina`).
- Carro asignado en `directa`: `carro_((j − 1) mod n) + 1`, con `j` sacado del id y `n = config.num_carros` (con 1 + 1 → `carro_1`, igual que v0.1).
- **Modo con reservas** = no (`directa` y `n == 1` y `m == 1`). Es decir, A/B/C usan **exactamente** el código de v0.1 (BFS con ocupadas y `BLOQUEO` si la siguiente celda está ocupada).
- `COSECHANDO` con siguiente celda **no vecina** (hay un obstáculo entre las dos): pasa a `YENDO_A_CAMPO` con destino esa celda y la cosecha al llegar.
- Llena antes de tiempo: si `carga + mundo.rendimiento(siguiente) > capacidad`, se considera llena (con rendimiento fijo y capacidad múltiplo, esto equivale a `carga == capacidad`: v0.1 intacto).
- Movimiento con reservas (`YENDO_A_CAMPO`, `REGRESANDO_A_BASE`): igual que el carro (convención de Oswaldo): `plan = rutas.bfs_tiempo(pos, destino, t − 1, ancho, alto, bloqueadas_fijas, reservas_de_otros)`, donde `reservas_de_otros` = `mundo.reservas(excepto=id)` + las celdas ocupadas ahora en `t`. Da el primer paso del plan (o espera). Si no hay plan: espera; `BLOQUEO` solo si lleva más de `HORIZONTE` ticks seguidos sin plan (una vez por espera).
- `COSECHANDO` con reservas: si la siguiente celda está ocupada, espera y registra **una** `RESTRICCION` `R3_celda_ocupada` por espera (no `BLOQUEO`: es una espera decidida por la regla, spec §5.5); `BLOQUEO` solo tras `HORIZONTE` ticks.
- Reserva al final de su paso (solo modo con reservas):
  - quieta (`EN_BASE`, `LLENA_ESPERANDO`, `TRANSFIRIENDO`, `FIN`): `[(pos, t) … (pos, t + H + 1)]` (lo pide Oswaldo);
  - `COSECHANDO`: su celda en `t` y las siguientes celdas **vecinas consecutivas** del camino, una por tick, hasta `t + H` (se corta en el primer salto por obstáculo); como se re-reserva cada tick, si se detiene por llena las reservas viejas se reemplazan;
  - en viaje: `rutas.reservas_de_ruta(pos, plan, t)`.
- Restricciones de ruta: una por tramo, con `rutas.clasificar_desvio` (R3, R4, R10). **R9:** si la ruta sin la bodega sería más corta que con ella, `R9_bodega` (una vez por tramo).

### 6.3 Administrar la subasta (tarea 3)

Estado del servicio: `_n_servicio`, `_servicio` (id `"<id>#<n>"` o `None`), `_tick_llamada`, `_propuestas {carro: costo}`, `_respuestas` (set de carros que contestaron), `_contratado`, `_reintento_en`.

Dentro de `paso(t)`, en este orden:
1. **Leer buzón** (solo subasta), **antes** del `return` de `FIN`: `PROPUESTA`/`RECHAZO` del servicio actual se guardan; de otro servicio, `logger.warning` y se descartan (un mensaje retrasado de una subasta vieja). Leer también en `FIN` es obligatorio: un mensaje viejo sin leer dejaría `hay_pendientes` en verdadero para siempre y la simulación nunca terminaría (ver la vuelta 3).
2. **Decidir** si hay servicio sin contratado y `t ≥ _tick_llamada + espera_propuestas + 2 · retraso_maximo`: ganador = `min(propuestas, key=(costo, id))`; `ACEPTACION` al ganador, `RECHAZO_PROPUESTA` a los demás que **propusieron**. Sin propuestas: `_servicio = None` y `_reintento_en = t + reintento_subasta`.
   (`retraso_maximo` = `config.incertidumbre.retraso_mensajes.maximo` si `probabilidad > 0`, si no 0. **Decisión D-C:** `2 ·` porque se retrasan los dos mensajes, la llamada y la respuesta; con `espera_propuestas = 2` y sin retraso, la propuesta enviada en `t0+1` se lee en `t0+2`, justo a tiempo. La spec dice «+ retraso máximo»: se corrige el texto.)
3. **Reintento:** si no hay servicio, ya había pedido carro y `t ≥ _reintento_en`, vuelve a llamar. **Decisión D-B:** un reintento es un **servicio nuevo** (`#n+1`), así se cumple «un cfp por carro por servicio» (prueba de Ilan).
4. **Máquina de estados** de v0.1 con los cambios. La **llamada** se evalúa justo después de cosechar, en el mismo tick (como el `LLENA` de v0.1; si se evaluara al inicio del paso siguiente, la subasta saldría un tick tarde respecto de la base): si no hay servicio en curso y (`carga ≥ umbral · capacidad`, o última celda, o llena) → `_n_servicio += 1` y `SOLICITUD_SERVICIO` a **cada** carro con `servicio, x, y, carga, capacidad`. Después, si está llena o fue la última celda → `LLENA_ESPERANDO` (en `directa` envía `LLENA` al carro asignado, como v0.1); si no, sigue `COSECHANDO` aunque ya haya llamado (despacho anticipado).
5. `LLENA_ESPERANDO`: transfiere solo si `carro = contratado (subasta) o asignado (directa)` está vecino y en `ESPERANDO_TRANSFERENCIA`. Duración con `mundo.duracion(carga, tasa_transferencia)` (con extra 0 da lo mismo que v0.1) y `−1` por el tick de entrada, como hoy.
6. `TRANSFIRIENDO` al terminar: `mundo.transferir` devuelve lo transferido; `TRANSFERENCIA_TERMINADA` con `{"cantidad"}` en directa (payload de v0.1, exacto) o `{"servicio", "cantidad"}` en subasta; libera el servicio. Si quedó grano (el carro no tenía lugar para todo, posible con `encadenar_servicios` y rendimiento variable), sigue `LLENA_ESPERANDO` y en subasta llama otra vez.

### 6.4 Combustible de la cosechadora (tarea 4)

- Al terminar una transferencia (y antes de salir de la base): estima lo de la **siguiente carga**, no todo lo que falta del camino (si no, con tanques chicos nunca le alcanzaría y daría vueltas a la base para siempre): `celdas` = celdas del camino hasta llenarse (con `rendimiento` de cada una) + distancia BFS de esa celda a su base; `ticks_encendido` = `ceil(capacidad / tasa_transferencia)` + `espera_propuestas`. Con `mundo.combustible_para`.
- Si no alcanza (`combustible − litros < reserva · tanque`) y el tanque no está lleno: `RESTRICCION combustible_reserva` (una vez), `REGRESANDO_A_BASE` con `_recargando = True`; en la base pasa a `EN_BASE` (el mundo recarga); con el tanque lleno vuelve a `YENDO_A_CAMPO` hacia la siguiente celda de su camino. **No se agregan estados nuevos** (el validador, el visor y Unity solo conocen los 7 de la cosechadora).
- Con tanque lleno sale aunque la estimación diga que no (si no, se quedaría para siempre).
- `registro()` agrega `combustible` (2 decimales) si no es `None`.

### 6.5 Pruebas (tarea 5, en `tests/test_cosechadora.py` con dobles)

Llamada al umbral (0.7 con capacidad 10 → a las 7); gana el menor costo; empate por id; sin propuestas reintenta con servicio nuevo tras `reintento_subasta`; no transfiere con un carro no contratado aunque esté vecino y esperando; se traslada sin cosechar alrededor de un obstáculo; va a recargar y regresa a la celda siguiente; `directa`: mismos mensajes que v0.1 (las pruebas actuales sin cambios).

### 6.6 D/E/F de punta a punta (aquí se prueba de verdad todo junto)

Script fuera del repo (`$S/corridas.py`): D, E y F × 4 estrategias × seeds 0–19 (240 corridas), y para cada una: termina, `validar_trace` sin errores, `colisiones == 0`, sin intercambios, sin `BLOQUEO` en E, grano conservado, combustible ≥ 0. Además A/B/C con la regresión.

**Riesgos que espero encontrar aquí y qué hago con cada uno:**

| Riesgo | Síntoma | Qué se hace |
|---|---|---|
| Espera mutua cosechadora–carro en un pasillo (la cosechadora sigue su camino fijo y el carro está parado en él) | `BLOQUEO` o `max_ticks` en E | El carro ya evita la «siguiente celda del camino» (`mundo.camino`) y respeta las reservas de la cosechadora; si aun así pasa, la cosechadora espera y el carro cede paso (regla de Oswaldo «pedir y ceder el paso» extendida: la cosechadora en `COSECHANDO` cuenta como «en viaje»). Eso toca `carro.py`: iría en un commit aparte «en nombre de Oswaldo», con su prueba, y se le avisa |
| `TRANSFERENCIA_TERMINADA` retrasada (F) y el mismo carro gana el siguiente servicio | El carro recibe dos `TRANSFERENCIA_TERMINADA` | Oswaldo empareja por `servicio`; la cosechadora incluye `servicio` en subasta. Se verifica en F con la prueba `test_transferencia_solo_contratado` |
| La cosechadora_2 de D cruza la franja 1 para llegar a la suya (paridad global) | Restricciones R3 al inicio | Esperado y correcto (queda en el log); no es un error |
| F no termina en alguna seed (combustible) | `max_ticks` | Ajustar tanques/tasa en `escenario_f.json` (es configuración, no código), y documentar los valores finales |
| Una métrica de A/B/C cambia | Falla la regresión | Buscar la llamada al azar o el cambio de orden; nunca actualizar el fixture |

🔒 push y PR «Buzón con la subasta y cosechadora administradora (en nombre de Emilio)», con la tabla de las 240 corridas en la descripción. 🔒 merge.

---

## Paso 7 — ilan-aux, parte 2: integración, scripts y CI (si P1 = sí)

```bash
git -C wt_ilan merge origin/development
```
- `tests/test_integracion.py`: `ESCENARIOS = A..F`; `test_duracion_de_estados_en_el_log` se salta **solo** en F (tiene duración extra aleatoria) con la razón escrita; `test_conservacion_de_grano` usa `cantidad` de los eventos.
- Nuevas (spec §16 y guía de Ilan): `test_no_entra_a_obstaculo`, `test_pasillo_sin_colisiones_ni_bloqueos` (E × 4 estrategias × 20 seeds, marcada `lenta` solo si pasa de 30 s), `test_subasta_secuencia`, `test_transferencia_solo_contratado`, `test_semilla_reproducible` (F), `test_retraso_mensajes`, `test_combustible_nunca_negativo`, `test_recargas_solo_en_base`.
- `scripts/correr_todos.sh` con D/E/F y el experimento; `scripts/servidor.sh`.
- CI: ya instala `requirements.txt`, así que FastAPI/uvicorn/httpx entran solos con mi PR; solo verifico que el CI de GitHub corra verde.

🔒 push y PR «Pruebas de integración de la segunda entrega (en nombre de Ilan)». 🔒 merge.

## Paso 8 — Unity: mario-aux

```bash
cd $S/unity && git checkout -b mario-aux origin/mario_giovanni_branch
```
- `TraceLoader.cs:177`: `if (e["cantidad"] != null) Integer(e, "cantidad", 1);` (opcional, como la spec). Donde se acumula el grano, usar `cantidad` si existe, si no el `rendimiento` de la celda o `grano_por_celda`.
- (Mejora opcional, preguntar a Mario) el menú de estrategias se llena con `estrategias` de `/api/escenarios` y deja la lista fija solo como respaldo.
- Prueba EditMode nueva: un trace 2.2 **sin** `cantidad` carga.
- Verificación local (Unity está instalado):
```bash
~/Unity/Hub/Editor/6000.3.7f1/Editor/Unity -batchmode -nographics -projectPath $S/unity \
  -runTests -testPlatform EditMode -testResults $S/unity_editmode.xml
```
  y prueba manual: `uvicorn harvest_sim.servidor:app` con la simulación real, abrir la escena, elegir E/anticipada/seed 3 y ver que reproduce. Copio a `Assets/Data/Traces/` los traces exportados (`tools/exportar_traces_unity.py`, D/E/F × 4 estrategias, seed 0) para el respaldo local.

🔒 push y PR `mario-aux` → `dev` en `GioMax102/harvest-simu-visualization` (tenemos permiso de push). 🔒 merge.

## Paso 9 — Datos (Joel): resultados reales

Pasos 9–10 de `plan_datos_entrega2.md`, ahora con la simulación completa:
```bash
python tools/correr_experimento.py config/experimentos/estrategias.json --procesos 4   # resumen, comparacion.csv y ablacion.csv
python viz/plots.py runs/escenario_f/trace.json    # gráficas por trace (incluye 7_combustible.png)
```
Revisar que las diferencias contra la base tengan IC que no cruce 0 donde se afirme una mejora; ablación de J. Figuras y tablas al PDF (`tc2008b/entrega_pdf/`), secciones que cada persona redacta (guías: tarea 8 de Carlos, 6 de Emilio, 9 de Ilan). Va en una rama `branch-joel` nueva desde `development` (solo docs y `config/experimentos`), 🔒 PR.

## Paso 10 — Release

🔒 PR `development` → `main` «Segunda entrega» y 🔒 etiqueta `v0.2-entrega2`. Antes: `pytest -q` en limpio desde un clon nuevo con `pip install -r requirements.txt`, y `bash scripts/verificar_instalacion.sh`.

---

## R. Revisión del plan (dos vueltas)

### Vuelta 1 — incoherencias y errores encontrados y ya corregidos arriba

1. **Orden de merge.** El borrador seguía el orden pedido (Carlos → Emilio → Oswaldo → Mario) y dejaba `development` rojo: carlos-aux no podía probar contra el carro real, mi rama chocaba con la prueba de Mario, y el conflicto de `decisiones.md` se resolvía en la rama de Oswaldo. → Orden de la §2.
2. **D/E/F en carlos-aux.** El borrador pedía que D/E/F «terminen» en el paso 5 (como dice la guía de Carlos), imposible con la cosechadora vieja. → En el paso 5 solo cargan y validan; corren en el 6.
3. **Defaults de `rendimiento`.** La spec dice «1, 1 (= grano_por_celda)»: con `grano_por_celda = 2` serían cosas distintas. → El defecto es `grano_por_celda`, y la matriz va en la descripción si algún valor ≠ `grano_por_celda`.
4. **Campos obligatorios de `Config`.** `cargar_config` hoy calcula `faltantes` sobre **todos** los campos: con los 4 nuevos, los JSON de A/B/C fallarían por «falta politica». → `faltantes` solo sobre los obligatorios.
5. **Recarga con tanques por defecto.** La spec dice «nunca recargan», pero la regla del §9 recarga siempre que no esté lleno. → Decisión D-A y corrección del texto.
6. **Reintento de subasta.** Con el mismo id, un reintento rompería «un cfp por carro por servicio». → D-B: servicio nuevo.
7. **`randint(1, 0)`.** Con `probabilidad > 0` y `maximo = 0` el buzón fallaría. → Guarda `maximo >= 1`.
8. **Estimación de combustible de la cosechadora.** Con «todo lo que falta del camino», en F nunca alcanzaría. → Solo la siguiente carga + regreso, y con tanque lleno sale.
9. **Estados nuevos.** Una idea era un estado `RECARGANDO`: el validador, el visor y Unity lo rechazarían. → Se reutilizan `REGRESANDO_A_BASE`/`EN_BASE`.
10. **Prueba de Mario.** El borrador cambiaba el código de la CLI; el problema era la prueba. → Solo la prueba.

### Vuelta 2 — mejoras y huecos

1. **Red de seguridad primero:** la regresión se movió antes de carlos-aux (paso 4); en el borrador estaba al final con lo de Ilan.
2. **Puente del buzón (5.6):** dependencia temporal entre carlos-aux y emilio-aux; en esta vuelta se dejó como «puente» con `inspect.signature` (sustituido en la vuelta 3).
3. **Reservas en conflicto (5.3):** el borrador sobrescribía la reserva de otro. → Gana quien reservó primero, coherente con la prioridad del tick.
4. **Bloqueo de la cosechadora:** en modo con reservas, una espera por celda ocupada no es `BLOQUEO` (spec §5.5); si lo fuera, E fallaría la prueba de 0 bloqueos sin que haya un problema real. → `RESTRICCION R3` y `BLOQUEO` solo tras `HORIZONTE` ticks.
5. **Payload de `TRANSFERENCIA_TERMINADA`:** en directa se deja `{"cantidad"}` exacto para no tocar los traces de v0.1; en subasta se agrega `servicio` (el validador acepta claves extra).
6. **Duplicar valores por defecto:** `POLITICA_POR_DEFECTO` vive en `config.py`; la cosechadora la importa; los pesos de `costo` salen de `datos.metricas.PESOS_COSTO` (una sola fuente).
7. **R9 nunca aparecería:** la bodega casi nunca está en la ruta de una cosechadora. → Se registra cuando sí alarga la ruta; la prueba de `test_restriccion_registrada` usa un mapa a mano donde pasa.
8. **Pruebas de Ilan que se tocan en aux ajenas** (`test_config`, `test_mundo`): son cambios obligados por la spec y quedan anotados en la descripción de cada PR.

### Vuelta 3 — simulando los ticks a mano

1. **Simulación que nunca termina.** Siguiendo un mensaje retrasado en F: una `PROPUESTA` vieja llega a una cosechadora que ya está en `FIN`; el `FIN` de v0.1 hace `return` sin leer, el mensaje queda en su fila, `hay_pendientes` es verdadero para siempre y F llega a `max_ticks`. → La cosechadora lee (y descarta) su buzón **antes** del `return` de `FIN` (6.3, punto 1).
2. **Espera de la subasta.** Con retraso, la llamada **y** la respuesta pueden llegar tarde: con «+ retraso máximo» una propuesta válida podía llegar después de decidir y la cosechadora reintentaría sin necesidad. → D-C: `+ 2 · retraso_maximo`. (Sin retraso no cambia nada.)
3. **La llamada un tick tarde.** El borrador evaluaba la llamada al inicio del paso: con `umbral 1.0` la estrategia `subasta` saldría un tick tarde frente a la base, y la comparación quedaría sesgada en su contra. → Se evalúa justo después de cosechar (6.3, punto 4).
4. **Puente del buzón.** Era innecesario: F es el único escenario con retraso y no corre antes del paso 6. → carlos-aux usa `Buzon()` y emilio-aux cambia esa línea.
5. **`num_ciclos`.** En v0.1 contaba `LLENA`; con mi rama cuenta `TRANSFERENCIA_TERMINADA` (en subasta no hay `LLENA`). Con 1 + 1 en directa son iguales (1 `LLENA` → 1 transferencia), así que la regresión no cambia. Verificado en la definición de los dos.
6. **Un arreglo de ruta tocaría `carro.py`.** Si en E aparece una espera mutua cosechadora–carro, la solución está en el carro (de Oswaldo), no en la cosechadora. → Va en un commit propio «en nombre de Oswaldo» y se le avisa (6.6).
7. **Comando del experimento.** El borrador usaba `python -m harvest_sim.datos.experimentos`, que no tiene CLI; el real es `tools/correr_experimento.py` (paso 9).
8. **Textos de la spec a corregir** al implementar: D-A («nunca recargan») en carlos-aux y D-C («+ retraso máximo») en emilio-aux, cada uno con su entrada en `decisiones.md`. Docs nuevos: `docs/equipo/carlos/mundo.md` y `docs/equipo/emilio/cosechadora.md` (qué se hizo, API, decisiones y preguntas de defensa, igual que los de Oswaldo).

Después de esta vuelta, cada paso tiene: rama de origen, qué se cambia, qué pruebas se rompen y por qué, cómo se verifica y el PR que lo cierra; y cada interfaz entre partes está escrita con los nombres reales del código de Oswaldo y del mío. No encontré más incoherencias.

### Comprobación final (cosas que el plan asume y ya verifiqué en el código)

- Oswaldo: nombres y firmas de la API del mundo de la §2 del paso 2 (leídos de `carro.py`), `HORIZONTE = 10`, convención `bfs_tiempo(pos, destino, t − 1, …)`.
- Mi formato acepta claves extra en el payload y exige `servicio, x, y, carga, capacidad` en `SOLICITUD_SERVICIO`; `ESTADOS_COSECHADORA` son los 7 de v0.1.
- Mi servidor responde `{"escenarios": [{"nombre", "parametros"}], "estrategias"}`, que es lo que lee `TraceClient.cs`.
- CI instala `requirements.txt` (no hay que tocar el workflow).
- `v0.1-entrega1` existe como etiqueta (fuente del fixture de la regresión); su `runs/` está vacío, por eso las métricas se generan corriendo esa versión.
- Unity 6000.3.7f1 instalado (pruebas EditMode en batchmode posibles); push en el repo de Unity.

### Preguntas abiertas para Joel

- **P1.** ¿Hacemos también ilan-aux (pasos 4 y 7)? Recomendado: sí.
- **P2.** ¿Avisamos a Carlos, Emilio, Ilan y Mario antes de abrir las aux (para que no trabajen en paralelo sobre lo mismo)? Recomendado: sí, un mensaje corto en el grupo (lo mandas tú).
- **P3.** ¿Unity: lleno el menú de estrategias desde el servidor (mejora) o solo el arreglo de `cantidad`? Recomendado: solo el arreglo, y la mejora se le propone a Mario.
