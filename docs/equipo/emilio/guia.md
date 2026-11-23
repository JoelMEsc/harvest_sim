# Guía de Emilio — Mensajes y cosechadora (segunda entrega)

**Tu parte en una frase:** el buzón con los mensajes de la subasta y retraso aleatorio, y la cosechadora como **administradora** del servicio: recorre su franja, pide carro al llegar al umbral, decide la subasta y transfiere solo con el carro contratado.

**Por qué importa:** es el mecanismo de comunicación entre agentes (Contract Net con performativas KQML/FIPA-ACL), el tema central de la rúbrica, y el despacho anticipado, la mejora que se compara contra la línea base.

**Archivos tuyos:** `src/harvest_sim/mensajes.py`, `src/harvest_sim/cosechadora.py`, `tests/test_mensajes.py`, `tests/test_cosechadora.py`.

**Lee antes:** [README del equipo](../README.md); especificación de la segunda entrega §3, §4, §6, §7, §8 y §9.

**Condición:** con `asignacion: "directa"` y `umbral_aviso: 1.0` la cosechadora se comporta **exactamente** como en v0.1.

---

## Tareas (en orden)

### 1. Buzón con tipos nuevos y retraso ⚡

- `TipoMensaje`: agrega `SOLICITUD_SERVICIO`, `PROPUESTA`, `RECHAZO`, `ACEPTACION`, `RECHAZO_PROPUESTA` (tabla del README del equipo §3.3).
- La performativa del evento sale de `datos.formato.PERFORMATIVAS[tipo]` (Joel agrega los tipos nuevos ahí).
- `Buzon(azar=None, probabilidad=0.0, maximo=0)`: al enviar, `entrega_en = t + 1`; si `azar` existe y `azar.random() < probabilidad`, `entrega_en += azar.randint(1, maximo)`. Con probabilidad 0 **no** llames al generador.
- `entregar(t)`: entrega los mensajes con `entrega_en == t`, ordenados por id.
- **Listo cuando:** con probabilidad 0 todo es igual que antes; con probabilidad 1 y máximo 2, `entrega_en` cae en [t+2, t+3] y se entrega exactamente ese tick (pruebas).

### 2. Cosechadora con varios agentes y obstáculos

- Usa `mundo.camino(self.agent_id)` (su franja) en lugar de `camino_serpentina()`.
- Ya no supongas `"carro_1"`: el carro con el que transfiere es el **contratado** (subasta) o el asignado (`directa`: carro ((j−1) mod n) + 1).
- Si la siguiente celda del camino no es vecina (hay obstáculo entre ellas), trasládate con `rutas.bfs_tiempo` en estado `YENDO_A_CAMPO` y vuelve a `COSECHANDO` al llegar.
- Reserva tus próximas celdas del camino con `mundo.reservar` (horizonte 10) para que los carros te rodeen.
- Cosecha con la cantidad que devuelve `mundo.cosechar`. Si la siguiente celda no cabe (`carga + mundo.rendimiento(celda) > capacidad`), te consideras llena.

### 3. Administrar la subasta

Estado interno del servicio actual: `servicio` (id `"<tu id>#<n>"`), `propuestas` recibidas, tick de la llamada y `carro_contratado`.

- **Llamada:** cuando `carga ≥ umbral_aviso × capacidad` (o en tu última celda) y no tienes servicio en curso, envía `SOLICITUD_SERVICIO` a **cada** carro con `servicio, x, y, carga, capacidad`. **Sigue cosechando** mientras haya lugar.
- **Recolección:** lee tu buzón cada tick; guarda `PROPUESTA` y `RECHAZO` de ese servicio.
- **Decisión:** al pasar `espera_propuestas + retraso máximo` ticks desde la llamada, elige el menor `costo` (empate: menor id), envía `ACEPTACION` al ganador y `RECHAZO_PROPUESTA` a los demás que propusieron. Sin propuestas: nueva llamada tras `reintento_subasta` ticks.
- **Transferencia:** solo si estás en `LLENA_ESPERANDO` y el **carro contratado** está vecino y en `ESPERANDO_TRANSFERENCIA`. Al terminar (`mundo.duracion` para la duración), `TRANSFERENCIA_TERMINADA` con `servicio` y `cantidad`.
- **Modo `directa`:** se conserva `LLENA` al llenarte, como en v0.1.

### 4. Combustible

Antes de seguir cosechando después de una transferencia, estima si te alcanza para lo que falta de tu camino y volver a tu base sin bajar de la reserva (`mundo.combustible_para`). Si no: `mundo.registrar_restriccion(id, "combustible_reserva", ...)`, ve a tu base, espera la recarga y regresa a la celda donde te quedaste. `registro()` agrega `"combustible"`.

### 5. Pruebas (con dobles de mundo y buzón)

- Llamada al llegar al umbral (0.7 con capacidad 10 → a las 7 unidades).
- Decide por menor costo; empate por id; sin propuestas, reintenta.
- No transfiere con un carro no contratado aunque esté vecino.
- Se traslada sin cosechar alrededor de un obstáculo.
- Va a recargar cuando no le alcanza.
- Modo `directa`: mismos mensajes que v0.1.

### 6. PDF: arquitectura del agente y protocolo de comunicación (para Joel)

Diagrama de la secuencia cfp → propose/refuse → accept/reject → inform, con las performativas y los estados de cada agente.

---

## Dependencias

- **Dependes de:** nadie para el buzón; del mundo de Carlos (franjas, reservas, combustible) y de `bfs_tiempo` de Oswaldo para la cosechadora real. Mientras, dobles.
- **Dependen de ti:** Oswaldo (el carro responde a tus llamadas), Carlos (simulación), Joel (performativas en el log).

## Cómo probar

```bash
pytest tests/test_mensajes.py tests/test_cosechadora.py -q
python -m harvest_sim.cli config/escenario_d.json --sin-plots && python tools/validar_trace.py runs/escenario_d/trace.json
```

## Definición de listo

- [ ] Buzón con los 7 tipos, performativas y retraso; probabilidad 0 = v0.1.
- [ ] Cosechadora: franja, obstáculos, umbral, subasta completa, combustible.
- [ ] D termina y la secuencia de mensajes de cada servicio es cfp → propose/refuse → accept/reject → inform.

## Errores comunes

- Mandar la `ACEPTACION` antes de que lleguen todas las propuestas (no esperar el retraso máximo).
- Dejar de cosechar al mandar la llamada (eso es reactivo, no anticipado).
- Escribir la performativa a mano en lugar de importarla.
