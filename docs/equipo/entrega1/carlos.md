# Guía de Carlos — Mundo (configuración, mundo y simulación)

**Tu parte en una frase:** cargas y validas la configuración, construyes el mundo (casillas, serpentina, grano) y escribes el bucle de la simulación que junta a todos y produce el `trace.json`.

**Por qué importa:** sin `simulacion.ejecutar` no hay corridas reales, ni métricas, ni visor con datos reales. Eres el último eslabón de la integración. En la rúbrica, tu parte es el criterio 2 (modelado del entorno, 15 puntos) y la base del 3 (implementación).

**Fecha límite:** martes 17, antes de la clase. **Objetivo personal:** corrida completa de los tres escenarios el **lunes en la noche**.

**Archivos tuyos (nadie más los toca):** `src/harvest_sim/config.py`, `src/harvest_sim/mundo.py`, `src/harvest_sim/simulacion.py`, `config/escenario_a.json`, `config/escenario_b.json`, `config/escenario_c.json`.

**Lee antes:** [README del equipo](README.md) §3 y §4; especificación §2, §3, §4.1, §4.3 y §5.4.

---

## Tareas (en orden)

### 1. Configuración (`config.py`) — 45 min

1. Agrega a los tres JSON de `config/`, al final:
   ```json
   "obstaculos": {"celdas": [], "regiones": []}
   ```
2. Agrega el campo al `Config` (dataclass congelada), al final para no romper el orden:
   ```python
   from dataclasses import dataclass, field
   obstaculos: dict = field(default_factory=lambda: {"celdas": [], "regiones": []})
   ```
3. Implementa `cargar_config(ruta) -> Config`:
   - Lee el JSON (`json.loads(Path(ruta).read_text(encoding="utf-8"))`).
   - Si falta un campo o sobra uno desconocido: `ValueError("config: falta <campo>")`.
   - Validaciones del §3 de la especificación, cada una con `ValueError` y un mensaje que diga qué campo falló: `capacidad_carro >= capacidad_cosechadora`; `capacidad_cosechadora % grano_por_celda == 0`; `ancho >= 1 + num_carros + num_cosechadoras`; `alto >= 2`; enteros positivos (cuidado: `True` es `int` en Python, recházalo); `num_carros` y `num_cosechadoras` distintos de 1 → `ValueError("... aún no soportado")`.
   - Obstáculos: `celdas = expandir_obstaculos(datos.get("obstaculos"), ancho, alto)` (`from harvest_sim.datos.campo import expandir_obstaculos`). Esa función ya valida todo (dentro del mapa, fila 0, alcanzables) y lanza `ValueError` con mensaje claro. Si `celdas` no está vacía: `ValueError("obstáculos aún no soportados en esta entrega")`.
- **Listo cuando:** `pytest tests/test_config.py` pasa (Ilan quita el `skip` de `test_config_invalida` y agrega `obstaculos` a la lista de campos de `test_escenarios_tienen_todos_los_campos`; coordínalo con él) y `python -c "from harvest_sim.config import cargar_config; print(cargar_config('config/escenario_a.json'))"` imprime el `Config`.

### 2. Layout del mundo (`mundo.py`) — 1 h ⚡ (destraba a Emilio y Oswaldo: súbelo en cuanto pase)

- `Mundo.__init__(config)`: guarda `ancho`, `alto`, `bodega = (0, 0)`, `entregado = 0`; calcula las bases con `n = num_carros`, `m = num_cosechadoras` **genéricos**: `carro_i → (i, 0)`, `cosechadora_j → (n + j, 0)`. Guarda `self._obstaculos = expandir_obstaculos(config.obstaculos, ancho, alto)` y una lista vacía de eventos.
- `grano_total = grano_esperado(self.descripcion())` (`from harvest_sim.datos.campo import grano_esperado`). **No escribas la fórmula**: es la misma que usan las métricas.
- `registrar(agente)`: guarda la referencia y pone `agente.posicion = base_de(agente.agent_id)`.
- `base_de`, `posicion` (lee `agente.posicion`), `estado_de` (lee `agente.estado.value`), `ocupadas(excepto)` (celdas de los demás agentes), `bloqueadas_fijas(agent_id)` (`{bodega}` para cosechadoras, vacío para carros; R9).
- `vecinos` y `ruta_bfs` delegan en `rutas.vecinos` y `rutas.bfs` de Oswaldo (si aún no están, deja la llamada; tus pruebas de layout no las necesitan).
- `camino_serpentina()`: fila 1 de izquierda a derecha, fila 2 de derecha a izquierda, etc.; empieza en `(0, 1)`.
- `duracion_ticks(cantidad, tasa) = max(1, ceil(cantidad / tasa))`.
- **Listo cuando:** pasan `test_casillas_de_inicio`, `test_serpentina_cubre_todo_el_campo`, `test_serpentina_alterna_direccion` y `test_duracion_ticks` (las escribe Ilan; si aún no, pruébalo tú con un script).

### 3. Grano y eventos (`mundo.py`) — 1 h

Reemplaza el método `cambios()` del esqueleto por estos (el formato v2.0 ya no usa `cambios()` ni `tick_actual`):

```python
def cosechar(self, agent_id, celda) -> int:        # R8: si ya se cosechó, ValueError
    ...  # agente.carga += grano_por_celda
    self._eventos.append({"tipo": "CELDA_COSECHADA", "celda": [x, y], "agente": agent_id})

def transferir(self, de, a, cantidad) -> int:      # R5: ValueError si no son vecinos; R6: δ = min(...)
    ...  # no genera evento: el cambio de carga ya sale en el registro de cada agente

def depositar(self, agent_id) -> int:
    ...  # self.entregado += carga; carga = 0
    self._eventos.append({"tipo": "DEPOSITO", "agente": agent_id, "cantidad": n, "entregado_total": self.entregado})

def registrar_bloqueo(self, agent_id) -> None:     # lo llaman los agentes cuando no pudieron moverse
    self._eventos.append({"tipo": "BLOQUEO", "agente": agent_id})

def drenar_eventos(self) -> list[dict]:            # devuelve los eventos del tick y vacía la lista
    eventos, self._eventos = self._eventos, []
    return eventos

def descripcion(self) -> dict:
    return {"ancho": ..., "alto": ..., "bodega": [0, 0], "bases": {id: [x, y], ...},
            "grano_por_celda": ..., "obstaculos": self._obstaculos}
```

- Usa **listas** (`[x, y]`), no tuplas, en todo lo que vaya al trace.
- **Listo cuando:** pasan `test_transferencia_solo_entre_vecinos`, `test_transferencia_respeta_capacidad`, `test_celda_cosechada_una_vez`, `test_cosechadora_no_entra_a_bodega`, `test_deposito_actualiza_entregado`, `test_cosechar_registra_cambio` y `test_descripcion_del_mundo`.

### 4. Catálogo de agentes — 10 min

En `simulacion.py`, el catálogo estático (va en `trace["agentes"]`), en el mismo orden que los registros (cosechadora y luego carro, como el orden del tick):

```python
catalogo = [{"id": a.agent_id, "tipo": "cosechadora" | "carro", "capacidad": a.capacidad,
             "base": list(mundo.base_de(a.agent_id))} for a in agentes]
```

`TraceBuilder` le agrega la clase de la ontología; tú no.

### 5. `simulacion.ejecutar(config) -> dict` — 1 h 30 min

```python
import dataclasses, logging
from harvest_sim.datos import TraceBuilder, calcular_metricas

def ejecutar(config):
    mundo = Mundo(config); buzon = Buzon()
    cosechadora = Cosechadora("cosechadora_1", config.capacidad_cosechadora)
    carro = Carro("carro_1", config.capacidad_carro)
    agentes = [cosechadora, carro]
    for a in agentes:
        mundo.registrar(a)
    builder = TraceBuilder(dataclasses.asdict(config), mundo.descripcion(), catalogo)
    builder.agregar_tick(0, [a.registro(0) for a in agentes], [])        # tick 0 = estado inicial, ANTES del primer paso
    t = 0
    while not termino(...):                                               # §5.4
        t += 1
        if t > config.max_ticks: registrar error y salir del bucle
        buzon.entregar(t)
        antes = {a.agent_id: a.estado for a in agentes}
        cosechadora.paso(t, mundo, buzon)
        carro.paso(t, mundo, buzon)
        # log de consola: cambios de estado (comparar con `antes`) y depósitos (§6.3)
        builder.agregar_tick(t, [a.registro(t) for a in agentes], buzon.drenar_eventos() + mundo.drenar_eventos())
    trace = builder.construir()
    trace["metricas"] = calcular_metricas(trace)
    return trace
```

- **Convención:** el tick 0 es el estado inicial; los pasos empiezan en el tick 1 (registrada en `docs/decisiones.md`, 2026-11-15). El estado `EN_BASE` de la cosechadora pasa a `YENDO_A_CAMPO` en su primer paso (tick 1).
- Llama `agregar_tick` en **todos** los ticks, aunque no haya cambios (el builder omite los vacíos).
- Término (§5.4): cosechadora en `FIN`, carro en `EN_BASE`, sin mensajes pendientes para el carro, carga del carro 0 y `mundo.entregado == mundo.grano_total`.
- Mientras Emilio y Oswaldo no terminan, pruébalo con **agentes falsos** de 10 líneas (por ejemplo, una cosechadora que pasa a `FIN` en el tick 3).
- **Listo cuando:** para los tres escenarios, `python tools/validar_trace.py` da `OK` sobre el trace (guárdalo con `escribir_trace(trace, "runs/escenario_a/trace.json")`) y los tests de integración de Ilan pasan.

### 6. Escenarios — 15 min

Revisa que los tres escenarios den resultados distintos y que todos tengan una carga parcial final (§8 de la especificación). Si C no provoca espera por carro ocupado, regístralo en `docs/decisiones.md`.

### 7. PDF: secciones 1 y 2 — 45 min (martes)

Secciones «Problema y arquitectura» (con Emilio) y «Entorno» (con Oswaldo). Mándaselas a Joel antes del martes a mediodía: él arma el documento final (ver [README del equipo](README.md) §5).

---

## Contrato con Datos

- `TraceBuilder(config_dict, mundo.descripcion(), catalogo)`, `agregar_tick(t, registros, eventos)` en cada tick, `construir()`, y `calcular_metricas(trace)`. Ejemplo completo de un trace válido: `tests/fixtures/trace_ejemplo.json`.
- Los eventos de `drenar_eventos()` tienen exactamente los campos del README del equipo §3.2 (el validador rechaza campos de más o de menos).

## Dependencias

- **Dependes de:** Oswaldo (`rutas.vecinos`, `rutas.bfs`), Emilio (`Buzon`, `Cosechadora`), Oswaldo (`Carro`). Mientras tanto, dobles de prueba.
- **Dependen de ti:** Emilio y Oswaldo (layout del mundo), Giovanni (CLI), Joel (corridas reales), Ilan (pruebas de mundo e integración).

## Cómo probar

```bash
pytest tests/test_config.py tests/test_mundo.py -q
python -c "from harvest_sim.config import cargar_config; from harvest_sim.simulacion import ejecutar; from harvest_sim.datos import escribir_trace; escribir_trace(ejecutar(cargar_config('config/escenario_a.json')), 'runs/escenario_a/trace.json')"
python tools/validar_trace.py runs/escenario_a/trace.json
```

## Definición de listo

- [ ] Los tres JSON tienen `obstaculos` vacío y cargan sin error; las configuraciones inválidas fallan con mensaje claro.
- [ ] Ningún número mágico: `(1, 0)`, `(2, 0)` y la fórmula del grano no aparecen escritos en tu código.
- [ ] `ejecutar` produce un trace que el validador acepta en los tres escenarios.
- [ ] Pruebas de config, mundo e integración sin `skip` y pasando.

## Errores comunes

- Tuplas en lugar de listas en el trace (`(0, 0)` vs `[0, 0]`): el validador las rechaza al leer el archivo como JSON.
- Olvidar el tick 0 o agregarlo después del primer paso.
- Generar el evento `DEPOSITO` sin `entregado_total`.
- Escribir `ancho * (alto - 1)`: usa `grano_esperado`.
