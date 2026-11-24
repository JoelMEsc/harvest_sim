# Buzón y cosechadora de la segunda entrega: qué se hizo y cómo se defiende

> Hecho por Joel en nombre de Emilio para integrar la segunda entrega. La guía de tareas está en [guia.md](guia.md); las decisiones, en `docs/decisiones.md` (2026-11-24).

## Buzón (`src/harvest_sim/mensajes.py`)

- **Los 7 tipos de mensaje**, cada uno con su performativa FIPA, tomada de `datos.formato.PERFORMATIVAS`:

  | Tipo | Performativa |
  |---|---|
  | `LLENA` | request |
  | `TRANSFERENCIA_TERMINADA` | inform |
  | `SOLICITUD_SERVICIO` | cfp |
  | `PROPUESTA` | propose |
  | `RECHAZO` | refuse |
  | `ACEPTACION` | accept-proposal |
  | `RECHAZO_PROPUESTA` | reject-proposal |

- **Firma:** `Buzon(azar, probabilidad, maximo)`. Con probabilidad p, el mensaje llega `U{1..maximo}` ticks más tarde. Con p = 0 nunca se llama al generador, así que la línea base no cambia.
- **Entrega:** por `entrega_en` y, si dos llegan en el mismo tick, por id.

## Cosechadora (`src/harvest_sim/cosechadora.py`)

| Modo | Qué hace |
|---|---|
| `directa` (base) | Como en v0.1. Al llenarse manda `LLENA` a su carro asignado, `carro_((j−1) mod n)+1` |
| `subasta` | Administra un Contract Net por cada carga (ver la secuencia abajo) |

Secuencia de la subasta:

```
cosechadora                           carros
   │── SOLICITUD_SERVICIO (cfp) ──────►│   al llegar al umbral (y sigue cosechando)
   │◄── PROPUESTA (propose) / RECHAZO ─│
   │   espera espera_propuestas + 2·retraso
   │── ACEPTACION ────────────────────►│   menor costo; empate: menor id
   │── RECHAZO_PROPUESTA ─────────────►│   a los demás que propusieron
   │   ... LLENA_ESPERANDO: transfiere solo con el contratado ...
   │── TRANSFERENCIA_TERMINADA (inform)►│   servicio, cantidad
```

- **Franja:** recorre `mundo.camino(id)`. Si un obstáculo separa dos celdas del camino, se traslada sin cosechar (`YENDO_A_CAMPO`).
- **Rendimiento:** si la siguiente celda no le cabe, se considera llena.
- **Rutas:** con varios agentes o en subasta usa rutas en el tiempo (`rutas.bfs_tiempo`) y reserva sus celdas: su celda todo el horizonte cuando está quieta, y su camino cuando cosecha.
- **Combustible:** estima la siguiente carga tras cada transferencia, y tiene un regreso de emergencia. Ver la decisión 6.

## Resultados (240 corridas: D, E y F × 4 estrategias × 20 seeds)

Todas terminan y validan, con 0 colisiones y 0 `BLOQUEO`. Medias de tiempo de completación (ticks) y ocio total:

| | base | subasta | anticipada | anticipada_plus |
|---|---|---|---|---|
| D (1 carro, 2 cosechadoras) | 247 / 331 | 248 / 334 | 246 / 330 | **180 / 199** |
| E (pasillo) | 165 / 144 | 160 / 141 | 156 / 133 | **127 / 92** |
| F (estrés) | **415 / 242** | 502 / 360 | 482 / 339 | 486 / 337 |

**Lectura:**
- En D y E, lo que más ayuda es aprovechar la capacidad del carro (`anticipada_plus`: atender desde la bodega y encadenar servicios): baja el tiempo un 27 % en D y un 23 % en E.
- En F, con tanques chicos e incertidumbre, la subasta pierde contra la base. Los carros rechazan servicios por combustible, las cosechadoras esperan más con el motor encendido, y todo eso cuesta recargas.

## Preguntas que te pueden hacer

- **¿Por qué la cosechadora es la administradora?** Porque es quien sabe cuándo y dónde necesita el servicio. Los carros saben su propia carga, su fila de servicios y su combustible, así que son quienes pueden ofertar un costo.
- **¿Por qué esperar el doble del retraso?** Se pueden retrasar la llamada y la respuesta. Con un solo retraso, una oferta válida podía llegar después de decidir.
- **¿Qué pasa si nadie propone?** Se reintenta tras `reintento_subasta` ticks, con un servicio nuevo.
- **¿Por qué no hay un estado `RECARGANDO`?** Los consumidores del log (validador, visor, Unity) solo conocen los 7 estados. Recargar es `REGRESANDO_A_BASE` y luego `EN_BASE`.
