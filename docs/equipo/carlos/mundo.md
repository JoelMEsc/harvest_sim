# Mundo de la segunda entrega: qué se hizo y cómo se usa

> Hecho por Joel en nombre de Carlos para integrar la segunda entrega. La guía de tareas está en [guia.md](guia.md); las decisiones, en `docs/decisiones.md` (2026-11-24).

## API del mundo (`src/harvest_sim/mundo.py`)

| Método | Para qué | Quién lo usa |
|---|---|---|
| `obstaculos` | `frozenset` de celdas con obstáculo | carro, cosechadora |
| `bloqueadas_fijas(id)` | obstáculos para todos y la bodega para las cosechadoras (R9, R10) | carro, cosechadora |
| `ruta_bfs(origen, destino, bloqueadas)` | BFS que siempre rodea los obstáculos | agentes en modo v0.1 |
| `franjas()` y `camino(id)` | filas de cada franja y la serpentina de la franja de esa cosechadora | cosechadora; el carro, para no tapar la siguiente celda |
| `camino_serpentina()` | `camino("cosechadora_1")` (compatibilidad) | código de la primera entrega |
| `reservar(id, [(celda, t), ...])` y `reservas(excepto=id)` | tabla espacio-tiempo del §5 | carro, cosechadora |
| `nuevo_tick(t)` | olvida reservas pasadas (lo llama la simulación) | simulación |
| `azar(fuente)` | `random.Random(f"{seed}-{fuente}")`, uno por fuente | mundo, buzón |
| `rendimiento(celda)` | grano de esa celda (0 fuera del campo) | cosechadora |
| `duracion(cantidad, tasa)` | `ceil` más el extra aleatorio (sin llamar al azar si el extra es 0) | transferencia y descarga |
| `cosechar(id, celda)` | suma el rendimiento y agrega `cantidad` al evento | cosechadora |
| `combustible_para(id, celdas, ticks)` | litros estimados para la reserva | carro, cosechadora |
| `actualizar_combustible(agente, se_movio)` | consumo y recarga en la base (evento `RECARGA`); nunca negativo (R11) | simulación |
| `registrar_restriccion(id, regla, detalle)` | evento `RESTRICCION` (valida la regla) | agentes |

`registrar(agente)` también pone `agente.tanque` y `agente.combustible` con el tanque lleno.

## Configuración (`src/harvest_sim/config.py`)

- Los 12 campos de la primera entrega son obligatorios. `obstaculos`, `politica`, `incertidumbre`, `combustible` y `costo` son opcionales.
- Validaciones de cada sección con un mensaje que nombra el campo, por ejemplo `config: politica.umbral_aviso debe estar en (0, 1]`.

## Simulación (`src/harvest_sim/simulacion.py`)

Crea `cosechadora_1..m` y `carro_1..n`. Cada tick sigue este orden:
1. `nuevo_tick`;
2. entregar los mensajes;
3. cosechadoras por id;
4. carros por id;
5. combustible de cada agente;
6. registro;
7. término.

Término: todas las cosechadoras en `FIN`; todos los carros en `EN_BASE`, vacíos y sin servicios en cola; ningún mensaje pendiente; todo el grano entregado.

## Escenarios

| | D (recurso escaso) | E (pasillo) | F (estrés) |
|---|---|---|---|
| Mapa | 10 × 8 | 9 × 8, muro en y = 3 con hueco en x = 4 | 12 × 9, dos bloques de 2 × 2 |
| Carros + cosechadoras | 1 + 2 | 2 + 2 | 2 + 2 |
| Capacidades | 8 / 16 | 8 / 16 | 8 / 12 |
| Incertidumbre y combustible | por defecto | por defecto | rendimiento 1–2, duración extra 2, retraso 0.2 / 2; tanques de 60 y 40 L con recarga de 10 L/tick |

Las franjas de D son 40/30 y las de E 28/27. D, E y F corren completos cuando la cosechadora sabe trabajar en su franja y con varios carros (parte de mensajes y cosechadora).

## Preguntas que te pueden hacer

- **¿Por qué A, B y C ahora tienen `RECARGA` si su tanque es enorme?** La regla del §9 recarga siempre que el agente vuelve a su base con el motor apagado. Las métricas de v0.1 no cambian: lo comprueba `test_regresion`.
- **¿Por qué el rendimiento se sortea en orden (y, x)?** Un `set` no tiene un orden fijo entre ejecuciones; recorrer en orden hace que la misma seed dé el mismo campo.
- **¿Por qué no se llama al generador cuando el extra es 0?** Cada llamada avanza la secuencia: llamarlo cambiaría las corridas de la línea base.
