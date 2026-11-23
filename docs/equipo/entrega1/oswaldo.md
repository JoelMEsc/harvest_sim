# Guía de Oswaldo — Rutas y carro

**Tu parte en una frase:** escribes el cálculo de rutas (BFS y resolución de conflictos, funciones puras) y el agente carro (su máquina de estados).

**Por qué importa:** las rutas las usan el mundo y los dos agentes; el carro es la mitad de la coordinación que se mide. En la rúbrica, criterios 1 (arquitectura del agente) y 2 (reglas del entorno).

**Fecha límite:** martes 17, antes de la clase. **Objetivo personal:** `rutas.py` el **lunes en la tarde** (destraba a todos) y `carro.py` el lunes en la noche.

**Archivos tuyos:** `src/harvest_sim/rutas.py`, `src/harvest_sim/carro.py`, `tests/test_rutas.py`, `tests/test_carro.py`.

**Lee antes:** [README del equipo](README.md) §3; especificación §2 (vecindad y reglas físicas), §4.2 (conflictos), §4.3 (duraciones), §5.2 (carro) y §5.3.

---

## Tareas (en orden)

### 1. `rutas.py` — 1 h 30 min ⚡ (súbelo en cuanto pase: Carlos y Emilio lo necesitan)

Las firmas y lo que debe hacer cada función ya están en los docstrings del archivo. Resumen:

| Función | Qué devuelve | Ejemplo (mapa 4 × 3) |
|---|---|---|
| `vecinos(celda, ancho, alto)` | Vecinos dentro del mapa en orden **N, E, S, O** | `vecinos((0, 0), 4, 3) == [(1, 0), (0, 1)]` |
| `bfs(origen, destino, ancho, alto, bloqueadas)` | Ruta **sin** el origen y **con** el destino; `[]` si son iguales; `None` si no hay ruta | `bfs((0, 0), (2, 0), 4, 3, set()) == [(1, 0), (2, 0)]` |
| `elegir_celda_objetivo(origen, objetivo, ancho, alto, bloqueadas, evitar)` | Celda vecina de `objetivo` donde se estaciona el carro (reglas 1–4 del docstring) | |
| `siguiente_paso(pos, ruta, destino, ancho, alto, ocupadas, bloqueadas_fijas)` | `(celda, ruta_restante)` o `(None, ruta)` si debe esperar | |

- BFS determinista: expande en orden N, E, S, O y usa `collections.deque`. Nunca entra a `bloqueadas`.
- Funciones **puras**: no importes `Mundo` ni agentes.
- Escribe los cuerpos de las pruebas de `tests/test_rutas.py` (cada una ya tiene su docstring con lo que debe verificar) y quita el `skip`.
- **Listo cuando:** `pytest tests/test_rutas.py` pasa los 9 tests sin `skip`.

### 2. Dobles de prueba — 20 min

En `tests/test_carro.py`, un `Mundo` falso (posiciones, `ocupadas`, `bloqueadas_fijas`, `ruta_bfs`, `depositar`, `registrar_bloqueo`, `vecinos`, `camino_serpentina`) y un `Buzon` falso (`leer`, `hay_pendientes`). Así no esperas a Carlos ni a Emilio.

### 3. `carro.py` — 2 h

- Implementa la tabla del §5.2 en `Carro.paso(tick, mundo, buzon)`. Atributos públicos: `agent_id`, `posicion` (tupla), `estado` (`EstadoCarro`), `carga`, `capacidad`.
- Solo revisa su fila (`buzon.leer`) estando en `EN_BASE` (regla del carro ocupado).
- Para moverse: `siguiente_paso(...)`. Si devuelve `None` porque la celda está ocupada, **llama `mundo.registrar_bloqueo(self.agent_id)`** y espera ese tick.
- Orientación: la dirección del último movimiento (`N`, `E`, `S`, `O`); inicial `N`.
- Descarga: `duracion_ticks(carga, tasa_descarga)`; al terminar, `mundo.depositar(self.agent_id)` (el mundo genera el evento `DEPOSITO`; tú no).
- Un estado de duración `N` aparece en exactamente `N` ticks del log (§4.3).
- **Listo cuando:** pasan los 6 tests de `tests/test_carro.py` (escribe sus cuerpos a partir de los docstrings) con los dobles.

### 4. `registro(tick)` — 15 min

```python
def registro(self, tick):
    return {"tick": tick, "agent_id": self.agent_id, "tipo": "carro",
            "pose": {"x": self.posicion[0], "y": self.posicion[1], "orientacion": self.orientacion},
            "estado": self.estado.value, "carga": {"actual": self.carga, "capacidad": self.capacidad}}
```

Nada más: sin `intencion`, sin `objetivo` (decisión del 2026-11-15). Cambia el nombre de `test_carro_registro_v1_0` a `test_carro_registro` y verifica exactamente estas claves.

### 5. Cambiar los dobles por los reales — 30 min (cuando `mundo.py` y `mensajes.py` lleguen a `development`)

### 6. PDF: sección 2 «Entorno» con Carlos — 30 min (martes)

Explica el grid, la vecindad, las reglas R1–R9, BFS y la resolución de conflictos.

---

## Contrato con Datos

- Tu `registro()` alimenta los eventos `AGENTE` del trace. Si un tick cambian `pose` o `carga`, el builder lo detecta solo.
- Cada `registrar_bloqueo` se vuelve un evento `BLOQUEO`; la métrica `ticks_bloqueados` los cuenta. No lo llames cuando el carro espera la transferencia (eso es `ESPERANDO_TRANSFERENCIA`, no un bloqueo).

## Dependencias

- **Dependes de:** nadie para `rutas.py`; del layout de Carlos y del `Buzon` de Emilio para el carro real (mientras, dobles).
- **Dependen de ti:** Carlos (`Mundo.vecinos` y `ruta_bfs` delegan en tu `rutas.py`), Emilio (la cosechadora usa `siguiente_paso`).

## Cómo probar

```bash
pytest tests/test_rutas.py tests/test_carro.py -q
```

## Definición de listo

- [ ] `rutas.py` sin `NotImplementedError`, 9 tests pasando, determinista.
- [ ] `carro.py` completo, 6 tests pasando.
- [ ] `registro()` con exactamente las 6 claves del contrato.
- [ ] `registrar_bloqueo` se llama solo cuando el carro no pudo moverse por una celda ocupada.

## Errores comunes

- BFS que devuelve la ruta con el origen incluido.
- Expandir vecinos en otro orden (rompe el determinismo y la reproducibilidad).
- Revisar la fila de mensajes fuera de `EN_BASE`.
- Devolver tuplas en `pose` o `estado` como `Enum` en lugar de `.value`.
