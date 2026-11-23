# Guía del equipo — segunda entrega (coordinación multiagente)

Punto de partida para todos. Cada quien tiene su guía paso a paso:

| Persona | Rol | Guía | Repositorio |
|---|---|---|---|
| Carlos | Mundo: configuración, mundo y simulación | [carlos/guia.md](carlos/guia.md) | harvest_sim |
| Oswaldo | Rutas y carro | [oswaldo/guia.md](oswaldo/guia.md) | harvest_sim |
| Emilio | Mensajes y cosechadora | [emilio/guia.md](emilio/guia.md) | harvest_sim |
| Mario Giovanni | Interfaz: Unity, visor, CLI y dashboard | [giovanni/guia.md](giovanni/guia.md) | harvest-simu-visualization y harvest_sim |
| Ilan | Calidad: pruebas, CI, scripts, autoevaluación y video | [ilan/guia.md](ilan/guia.md) | harvest_sim |
| Joel | Datos: log 2.2, métricas, costo J, experimentos, servidor FastAPI y reporte | [joel/guia.md](joel/guia.md) | harvest_sim |

**Lee en este orden:** este archivo, tu guía y las secciones de la [especificación de la segunda entrega](../especificacion_segunda_entrega.md) que tu guía cita. La primera entrega está archivada en [entrega1/](entrega1/README.md).

---

## 1. Qué construimos en esta entrega, en un minuto

La primera entrega fue la **línea base reactiva**: 1 cosechadora y 1 carro; el carro sale cuando la cosechadora ya está llena. Medimos que la cosechadora espera entre 37 % y 58 % del tiempo. Esta entrega agrega **coordinación** y la compara contra esa línea base:

- **Varios agentes** (N cosechadoras, M carros) en campos **con obstáculos**.
- **Subasta (Contract Net):** cuando una cosechadora necesita carro, los carros ofertan y gana el que llega antes.
- **Despacho anticipado:** la cosechadora pide el carro antes de llenarse y el carro la acompaña.
- **Rutas en el tiempo:** los carros reservan celdas por tick y no chocan ni se bloquean en pasillos.
- **Aleatoriedad con semilla, combustible, restricciones de seguridad registradas y costo J**, para experimentar con 20 repeticiones e intervalos de confianza.
- **Servidor FastAPI** que corre simulaciones y entrega traces a **Unity**.

**Regla de oro:** con la configuración por defecto, la simulación da **exactamente las mismas métricas que `v0.1-entrega1`**. Todo lo nuevo se activa con parámetros. Python sigue siendo la única fuente de verdad; Unity y el visor solo reproducen el log.

## 2. Orden de trabajo (quién destraba a quién)

```
Paso 1 (en paralelo, no esperan a nadie)
  Carlos:  configuración nueva + Mundo (franjas, obstáculos, reservas, azar, combustible, eventos) ⚡
  Oswaldo: rutas.bfs_tiempo + rutas.estimar_costo (funciones puras) ⚡
  Emilio:  Buzon con tipos nuevos, performativas y retraso aleatorio ⚡
  Joel:    formato 2.2 en TraceBuilder y validador ⚡ ; servidor FastAPI
  Giovanni: Unity acepta 2.2 y N agentes con traces de ejemplo; cliente HTTP
  Ilan:    CI con las dependencias nuevas; pruebas de configuración y regresión

Paso 2 (con los dobles de prueba de su guía, sin esperar)
  Emilio:  cosechadora (franja, umbral, administra la subasta, combustible)
  Oswaldo: carro (contratista, acompaña, fila de servicios, combustible)

Paso 3
  Carlos:  simulacion.ejecutar con N agentes ; escenarios D, E, F
  → corridas completas

Paso 4
  Joel:    experimentos (D, E, F × 4 estrategias × 20 seeds), costo J, reporte
  Giovanni: Unity con traces reales desde el servidor ; visor y dashboard
  Ilan:    pruebas de integración de D, E, F ; autoevaluación ; video
```

⚡ = destraba a otras personas: hazlo primero y súbelo en cuanto pase. Si te atoras más de 30 minutos, avisa en el chat.

## 3. Contrato compartido

### 3.1 Configuración

Secciones nuevas (opcionales, con valores por defecto que reproducen la línea base): `politica`, `incertidumbre`, `combustible` y `costo`. Ejemplo completo y validaciones: especificación §2. Las cuatro **estrategias** que se comparan:

| Estrategia | asignacion | umbral_aviso | atender_desde_bodega | encadenar_servicios |
|---|---|---|---|---|
| `base` | directa | 1.0 | false | false |
| `subasta` | subasta | 1.0 | false | false |
| `anticipada` | subasta | 0.7 | false | false |
| `anticipada_plus` | subasta | 0.7 | true | true |

### 3.2 API del Mundo (Carlos la implementa; Emilio y Oswaldo la usan)

```python
mundo.config                                   # Config (tasas, política, combustible…)
mundo.camino(agent_id) -> list[Celda]          # serpentina de la franja de esa cosechadora, sin obstáculos
mundo.obstaculos -> set[Celda]
mundo.bloqueadas_fijas(agent_id) -> set[Celda] # obstáculos para todos, más la bodega para cosechadoras
mundo.reservar(agent_id, ruta: list[tuple[Celda, int]])   # (celda, tick); reemplaza sus reservas futuras
mundo.reservas(excepto: str) -> dict[tuple[Celda, int], str]
mundo.azar(fuente: str) -> random.Random       # "rendimiento", "duracion", "mensajes"
mundo.rendimiento(celda) -> int                # grano de esa celda
mundo.duracion(cantidad: int, tasa: int) -> int   # ceil(cantidad/tasa) + extra aleatorio
mundo.cosechar(agent_id, celda) -> int         # devuelve la cantidad; evento CELDA_COSECHADA con cantidad
mundo.registrar_restriccion(agent_id, regla: str, detalle: str)   # evento RESTRICCION
mundo.combustible_para(agent_id, celdas: int, ticks_encendido: int) -> float   # litros que costaría
mundo.actualizar_combustible(agente, se_movio: bool)  # lo llama simulacion.py; recarga y evento RECARGA en la base
```

### 3.3 Mensajes (Emilio implementa el buzón; cosechadora y carro los usan)

| `tipo_mensaje` | Performativa | De → a | Payload |
|---|---|---|---|
| `SOLICITUD_SERVICIO` | `cfp` | cosechadora → cada carro | `servicio`, `x`, `y`, `carga`, `capacidad` |
| `PROPUESTA` | `propose` | carro → cosechadora | `servicio`, `costo` |
| `RECHAZO` | `refuse` | carro → cosechadora | `servicio`, `motivo` |
| `ACEPTACION` | `accept-proposal` | cosechadora → ganador | `servicio` |
| `RECHAZO_PROPUESTA` | `reject-proposal` | cosechadora → los demás | `servicio` |
| `LLENA` | `request` | cosechadora → carro (solo modo `directa`) | `x`, `y`, `carga` |
| `TRANSFERENCIA_TERMINADA` | `inform` | cosechadora → carro | `servicio`, `cantidad` |

El tipo y la performativa están en `harvest_sim/datos/formato.py` (`PERFORMATIVAS`): **impórtalos, no los escribas a mano**.

### 3.4 Registro de cada agente (en cada tick)

```python
{"tick": t, "agent_id": "carro_2", "tipo": "carro",
 "pose": {"x": 3, "y": 2, "orientacion": "S"}, "estado": "YENDO_A_COSECHADORA",
 "carga": {"actual": 0, "capacidad": 16}, "combustible": 87.5}
```

Lo único nuevo es `combustible` (número, 2 decimales). Sin rutas, intenciones ni objetivos.

### 3.5 Trace 2.2 (lo arma `TraceBuilder`)

Agrega a la 2.1: `AGENTE.set.combustible`, `CELDA_COSECHADA.cantidad`, `mundo.rendimiento` (opcional), eventos `RECARGA` y `RESTRICCION`, los tipos de mensaje de §3.3 y `entrega_en` que puede ser mayor que t + 1. Detalle: especificación §12.

## 4. Escenarios nuevos

| Escenario | Agentes | Qué muestra |
|---|---|---|
| D, recurso escaso (10 × 8) | 2 cosechadoras + 1 carro | Quién se queda con el carro |
| E, pasillo (9 × 8, muro con hueco) | 2 cosechadoras + 2 carros | 0 colisiones y 0 bloqueos con rutas en el tiempo |
| F, estrés (12 × 9, obstáculos) | 2 cosechadoras + 2 carros, tanques chicos, incertidumbre | Combustible, recargas, restricciones y variabilidad |

## 5. Lo que se entrega

1. Simulación con varios agentes, obstáculos, subasta, despacho anticipado, aleatoriedad y combustible, sin romper la línea base.
2. Demo de coordinación con dos escenarios de conflicto (D y E) y el de estrés (F).
3. Tabla de experimentos: D, E, F × 4 estrategias × 20 seeds, con media e IC 95 % de cada métrica y de J.
4. Contrato de interfaz: trace 2.2, mensajes y API del servidor (especificación §7, §12 y §14).
5. Unity reproduciendo traces pedidos al servidor FastAPI.
6. Autoevaluación actualizada contra las dos rúbricas, video y PDF (lo arma Joel).

## 6. Git

Igual que en la primera entrega ([plan de trabajo](../plan_de_trabajo.md) §7): tu rama personal → PR a `development`. Antes de empezar, trae lo último: `git switch branch-TU-NOMBRE && git fetch origin && git merge origin/development`. Solo tus archivos; si necesitas algo de otro archivo, pídelo a su dueño.
