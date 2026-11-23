# Guía de Emilio — Mensajes y cosechadora

**Tu parte en una frase:** escribes el buzón por el que pasan todos los mensajes (con sus eventos para el log) y el agente cosechadora (su máquina de estados).

**Por qué importa:** el mensaje `LLENA` es la coordinación entre agentes y el tiempo ocioso de la cosechadora es la métrica principal. En la rúbrica, criterio 1 (arquitectura del agente y mecanismos de comunicación) y la sección de ontología: la `performativa` de cada mensaje es el acto comunicativo (KQML / FIPA-ACL) que se vio en clase.

**Fecha límite:** martes 17, antes de la clase. **Objetivo personal:** `Buzon` el **lunes en la tarde** (destraba a todos) y `cosechadora.py` el lunes en la noche.

**Archivos tuyos:** `src/harvest_sim/mensajes.py`, `src/harvest_sim/cosechadora.py`, `tests/test_mensajes.py`, `tests/test_cosechadora.py`.

**Lee antes:** [README del equipo](README.md) §3; especificación §4.1, §4.3, §4.4, §4.5, §5.1, §5.3 y §6.3; [docs/ontologia.md](../../ontologia.md).

---

## Tareas (en orden)

### 1. `Buzon` — 1 h 30 min ⚡ (súbelo en cuanto pase)

- Fila FIFO por agente (`collections.deque`), `id` entero creciente desde 1, entrega en `tick_envio + 1`.
- `enviar(mensaje) -> int`: asigna el id, lo guarda como pendiente, **agrega el evento** y lo imprime (§6.3):
  ```python
  from harvest_sim.datos.formato import PERFORMATIVAS
  self._eventos.append({"tipo": "MENSAJE_ENVIADO", "id": mensaje.id, "tipo_mensaje": mensaje.tipo.value,
                        "performativa": PERFORMATIVAS[mensaje.tipo.value], "de": mensaje.emisor,
                        "a": mensaje.receptor, "payload": dict(mensaje.payload), "entrega_en": mensaje.tick_envio + 1})
  ```
- `entregar(tick)`: pasa a las filas los mensajes con `entrega_en == tick`, en orden de id, y por cada uno agrega `{"tipo": "MENSAJE_ENTREGADO", "id": n, "a": receptor}` y lo imprime.
- `leer(agent_id)`, `hay_pendientes(agent_id)` (fila de entrada **o** mensajes en tránsito hacia ese agente).
- Reemplaza `registro()` por `drenar_eventos() -> list[dict]` (devuelve los eventos y vacía la lista). El formato v2.0 ya no usa `registro()`.
- Logging con `logging.getLogger("harvest_sim.mensajes")`, formato exacto del §6.3 (sin fecha ni hora).
- Escribe los cuerpos de los 5 tests de `tests/test_mensajes.py` (renombra `test_registro_de_mensajes_para_el_log` a `test_eventos_de_mensajes_para_el_log` y verifica los dos eventos con `performativa`).
- **Listo cuando:** pasan los 5 tests sin `skip`.

### 2. Dobles de prueba — 20 min

En `tests/test_cosechadora.py`, un `Mundo` falso mínimo (posiciones, `camino_serpentina`, `ocupadas`, `bloqueadas_fijas`, `ruta_bfs`, `cosechar`, `transferir`, `estado_de`, `vecinos`, `registrar_bloqueo`).

### 3. `cosechadora.py` — 2 h

- La tabla del §5.1 en `Cosechadora.paso(tick, mundo, buzon)`. Atributos públicos: `agent_id`, `posicion`, `estado` (`EstadoCosechadora`), `carga`, `capacidad`.
- Cosechar con `mundo.cosechar(...)` (el mundo genera `CELDA_COSECHADA`). Transferir con `mundo.transferir(...)`.
- Mensajes: `buzon.enviar(Mensaje(TipoMensaje.LLENA, self.agent_id, "carro_1", tick, {"x": x, "y": y, "carga": carga}))` al llenarse **o** en la última celda (carga parcial); `TRANSFERENCIA_TERMINADA` con `{"cantidad": δ}` al terminar.
- Si la siguiente celda de la serpentina está ocupada: **llama `mundo.registrar_bloqueo(self.agent_id)`** y espera ese tick (no es tiempo ocioso: el ocioso es solo `LLENA_ESPERANDO`).
- Duración de la transferencia: `duracion_ticks(carga, tasa_transferencia)`; el estado aparece en exactamente `N` ticks (§4.3).
- Orientación inicial `S`.
- **Listo cuando:** pasan los 8 tests de `tests/test_cosechadora.py` con los dobles.

### 4. `registro(tick)` — 15 min

Igual que el carro, con `"tipo": "cosechadora"`: `tick`, `agent_id`, `tipo`, `pose {x, y, orientacion}`, `estado` (`.value`), `carga {actual, capacidad}`. Nada más. Renombra `test_cosechadora_registro_v1_0` a `test_cosechadora_registro`.

### 5. Cambiar los dobles por los reales — 30 min

### 6. PDF: arquitectura del agente y comunicación, con Carlos — 45 min (martes)

Explica la máquina de estados de cada agente (reactivo con estado), el buzón y los dos mensajes con su performativa (`request` y `inform`), y por qué un mensaje enviado en `t` se lee en `t+1`. Apóyate en [docs/ontologia.md](../../ontologia.md).

---

## Contrato con Datos

- Eventos de mensajes: exactamente los campos de arriba. El validador rechaza un `MENSAJE_ENVIADO` sin `performativa`, con una performativa que no corresponde al tipo, o con `entrega_en` distinto de `tick + 1`.
- Ejemplo real: busca `MENSAJE_ENVIADO` en `tests/fixtures/trace_ejemplo.json`.

## Dependencias

- **Dependes de:** nadie para el `Buzon`; del layout de Carlos y de `siguiente_paso` de Oswaldo para la cosechadora (mientras, dobles).
- **Dependen de ti:** Oswaldo (el carro lee el buzón), Carlos (`simulacion` usa el buzón y la cosechadora).

## Cómo probar

```bash
pytest tests/test_mensajes.py tests/test_cosechadora.py -q
```

## Definición de listo

- [ ] `Buzon` con `drenar_eventos()` y logging del §6.3; 5 tests pasando.
- [ ] `cosechadora.py` completa; 8 tests pasando.
- [ ] `performativa` importada de `formato.PERFORMATIVAS`, no escrita a mano.

## Errores comunes

- Entregar un mensaje en el mismo tick en que se envía.
- Enviar `LLENA` dos veces cuando la cosechadora se llena justo en la última celda.
- Contar como bloqueo la espera del carro (`LLENA_ESPERANDO` no llama a `registrar_bloqueo`).
- Guardar el `Enum` en el evento (`TipoMensaje.LLENA`) en lugar del texto (`"LLENA"`).
