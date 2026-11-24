# Especificación técnica — Segunda entrega (coordinación multiagente)

**Proyecto:** Reto agrícola multiagente, Equipo 3 · **Formato del log:** trace 2.2 · **Base:** `v0.1-entrega1`

Este documento define **qué se agrega** sobre la primera entrega. Todo lo que no se menciona aquí sigue como en [`especificacion_primera_entrega.md`](especificacion_primera_entrega.md) (mundo, reglas R1–R9, estados, duraciones, log de consola). Cada persona tiene su guía paso a paso en [`docs/equipo/`](equipo/README.md); las decisiones y sus alternativas están en [`docs/decisiones.md`](decisiones.md).

**Regla de oro de esta entrega:** con la configuración por defecto, la simulación debe dar **exactamente las mismas métricas que `v0.1-entrega1`** en los escenarios A, B y C. Todo lo nuevo se activa con parámetros. Así la línea base sigue siendo comparable y cada mejora se mide contra ella.

---

## 1. Qué se agrega y por qué

| Tema | Qué se agrega | Para qué (rúbrica / propuesta) |
|---|---|---|
| Varios agentes | N cosechadoras y M carros | Semana 4 del curso: coordinación con recursos escasos |
| Obstáculos | La simulación los recorre y los rodea | Escenario de pasillo; criterio de modelado del entorno |
| Rutas sin colisiones | Reservas espacio-tiempo entre agentes | Propuesta: «2 carros en un pasillo, 0 colisiones y 0 bloqueos» |
| Despacho anticipado | La cosechadora pide el carro antes de llenarse; el carro la acompaña | Propuesta: «despacho anticipado contra la línea base reactiva» |
| Subasta (Contract Net) | Los carros ofertan por cada servicio | Asignación de carros con mensajes y performativas (tema de clase) |
| Aleatoriedad con semilla | Rendimiento por celda, duraciones y retraso de mensajes | 20 repeticiones con intervalos de confianza |
| Combustible | Tanque, consumo y recarga dentro de la simulación | Métrica de sostenibilidad (rúbrica del curso) |
| Seguridad registrada | Evento `RESTRICCION` cuando una regla impide una acción | Ética y seguridad, IEEE 7007 |
| Costo J | J descompuesto por términos, con pesos en la configuración | Sustituye al aprendizaje por refuerzo (rúbrica: «documented cost decomposition») |
| Servidor FastAPI | API que corre simulaciones y entrega traces | Comunicación con Unity (WebGL queda para la entrega final) |

**Fuera de esta entrega:** WebGL, aprendizaje por refuerzo (se justifica con el costo J, §11), OpenClaw/NemoClaw (§15), cosechadoras que descargan solas, terreno variable distinto del rendimiento.

---

## 2. Configuración

Todas las secciones nuevas son **opcionales**: si faltan, se usan los valores por defecto, que reproducen la primera entrega. `cargar_config` valida cada una y falla con un mensaje claro.

```json
{
  "nombre": "escenario_d", "seed": 0, "ancho": 10, "alto": 8,
  "num_carros": 1, "num_cosechadoras": 2, "grano_por_celda": 1,
  "capacidad_cosechadora": 8, "capacidad_carro": 16,
  "tasa_transferencia": 2, "tasa_descarga": 4, "max_ticks": 5000,
  "obstaculos": {"celdas": [], "regiones": []},
  "politica": {
    "asignacion": "directa",
    "umbral_aviso": 1.0,
    "atender_desde_bodega": false,
    "encadenar_servicios": false,
    "espera_propuestas": 2,
    "reintento_subasta": 3
  },
  "incertidumbre": {
    "rendimiento": {"minimo": 1, "maximo": 1},
    "duracion_extra_maxima": 0,
    "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}
  },
  "combustible": {
    "tanque_cosechadora": 100000, "tanque_carro": 100000,
    "consumo_por_celda_cosechadora": 2.0, "consumo_por_celda_carro": 1.0,
    "consumo_por_tick_encendido": 0.5, "reserva": 0.15, "tasa_recarga": 0
  },
  "costo": {
    "pesos": {"tiempo": 1.0, "distancia": 0.5, "colisiones": 1000.0, "ocio": 5.0, "combustible": 0.2, "restricciones": 10.0}
  }
}
```

| Parámetro | Valores | Por defecto (= línea base) | Validación |
|---|---|---|---|
| `num_carros`, `num_cosechadoras` | enteros ≥ 1 | 1, 1 | Ya no falla con > 1. `ancho ≥ 1 + n + m` sigue |
| `politica.asignacion` | `"directa"` o `"subasta"` | `"directa"` | Con `directa` y varios carros: cosechadora j → carro ((j−1) mod n) + 1 |
| `politica.umbral_aviso` | 0 < u ≤ 1 | 1.0 | Fracción de la capacidad a la que la cosechadora pide el carro |
| `politica.atender_desde_bodega` | bool | false | true: el carro atiende su siguiente servicio sin regresar a la base |
| `politica.encadenar_servicios` | bool | false | true: si le cabe, el carro atiende otro servicio antes de ir a la bodega |
| `politica.espera_propuestas` | entero ≥ 2 | 2 | Ticks que la cosechadora espera propuestas (más 2 × el retraso máximo de mensajes: ida y vuelta) |
| `politica.reintento_subasta` | entero ≥ 1 | 3 | Ticks antes de repetir una subasta sin propuestas |
| `incertidumbre.rendimiento` | 1 ≤ mínimo ≤ máximo | 1, 1 (= `grano_por_celda`) | Grano por celda, sorteado al crear el mundo |
| `incertidumbre.duracion_extra_maxima` | entero ≥ 0 | 0 | Ticks extra sorteados en cada transferencia y descarga |
| `incertidumbre.retraso_mensajes` | 0 ≤ p ≤ 1, máximo ≥ 0 | 0, 0 | Probabilidad de que un mensaje llegue tarde y cuántos ticks como máximo |
| `combustible.*` | números > 0; reserva en [0, 1) | tanques enormes (la reserva nunca se activa; sí hay `RECARGA` al volver a la base) | Consumo en litros; `tasa_recarga` 0 = recarga instantánea |
| `costo.pesos` | números ≥ 0 | los de arriba | Solo afectan al cálculo de J (§11) |

**Las cuatro estrategias que se comparan** (todas con los mismos escenarios y semillas):

| Nombre | asignacion | umbral_aviso | atender_desde_bodega | encadenar_servicios |
|---|---|---|---|---|
| `base` (línea base, = v0.1) | directa | 1.0 | false | false |
| `subasta` | subasta | 1.0 | false | false |
| `anticipada` | subasta | 0.7 | false | false |
| `anticipada_plus` | subasta | 0.7 | true | true |

Así cada mejora se mide por separado (ablación): la subasta sola, el despacho anticipado y el uso de la capacidad del carro.

---

## 3. Varios agentes

- **Ids y bases:** `carro_1 … carro_n` en `(1,0) … (n,0)`; `cosechadora_1 … cosechadora_m` en `(n+1,0) … (n+m,0)` (ya calculado así en `mundo.py`).
- **Reparto del campo en franjas:** las celdas libres del campo se dividen en m franjas de filas contiguas con el número de celdas más parejo posible (las primeras franjas se quedan con la fila sobrante). La cosechadora j recorre solo su franja, en serpentina.
- **Orden del tick:** (1) entrega de mensajes; (2) cosechadoras por id; (3) carros por id; (4) combustible y registro (§9); (5) término. El orden es fijo: define la prioridad en las reservas (§5).
- **Término:** todas las cosechadoras en `FIN`, todos los carros en `EN_BASE` y vacíos, sin mensajes pendientes, sin servicios en cola y `entregado == grano_total`.

## 4. Obstáculos en la simulación

- `cargar_config` ya **no** rechaza obstáculos: los expande y valida con `datos.campo.expandir_obstaculos` (dentro del mapa, nada en la fila 0, campo alcanzable).
- **Camino de cada cosechadora:** la serpentina de su franja **sin** las celdas con obstáculo. Si dos celdas consecutivas del camino no son vecinas (hay un obstáculo entre ellas), la cosechadora se traslada con BFS sin cosechar (estado `YENDO_A_CAMPO`) y retoma `COSECHANDO` al llegar.
- **Rutas:** todo BFS trata los obstáculos como bloqueados (`mundo.bloqueadas_fijas` los incluye para todos los agentes).
- **Regla nueva R10:** ningún agente entra a una celda con obstáculo. Prueba obligatoria.

## 5. Rutas sin colisiones: reservas espacio-tiempo

Con varios carros, «recalcular si la siguiente celda está ocupada» provoca esperas y bloqueos mutuos en pasillos. Se reemplaza por **reservas en el tiempo** (idea de A* cooperativo):

1. El mundo guarda una **tabla de reservas** `{(celda, tick): agent_id}` con horizonte `H = 10` ticks.
2. Cada agente, al actuar, planea su ruta con **BFS en espacio-tiempo** (`rutas.bfs_tiempo`): los nodos son `(celda, tick)`, las acciones son moverse a un vecino o **esperar** en la celda, y no puede usar `(celda, t)` reservada por otro ni **intercambiarse** con otro agente (si otro va de `c2` a `c1` entre `t` y `t+1`, no puede ir de `c1` a `c2`).
3. Reserva su ruta para los próximos `H` ticks y su celda final después del horizonte. Los agentes que actúan antes en el tick tienen prioridad (cosechadoras, luego carros, por id).
4. Una cosechadora en `COSECHANDO` no cambia su camino (es fijo), pero **sí reserva** sus próximas celdas: los carros la rodean.
5. **Espera planeada vs. bloqueo:** esperar porque lo decidió la ruta en el tiempo **no** es un bloqueo. `BLOQUEO` se registra solo cuando la ruta reservada se invalida y no hay alternativa (no debe pasar en los escenarios).
6. Con `asignacion: "directa"` y un solo carro, se conserva la regla de la primera entrega (para no cambiar la línea base).

## 6. Despacho anticipado y comportamiento del carro

- **Aviso:** la cosechadora pide el carro (subasta, §7) cuando `carga ≥ umbral_aviso × capacidad` o al cosechar su última celda. Con `umbral_aviso = 1.0` es el comportamiento reactivo.
- **Acompañar:** el carro ganador va hacia la posición **actual** de la cosechadora (la percibe con `mundo.posicion`), recalculando el objetivo en cada tick: una celda vecina libre que no sea la siguiente del camino de la cosechadora. Al estar vecino queda en `ESPERANDO_TRANSFERENCIA`; si la cosechadora se aleja, vuelve a `YENDO_A_COSECHADORA` y la sigue.
- **Transferencia:** ocurre cuando la cosechadora está en `LLENA_ESPERANDO`, y el carro **contratado** para ese servicio está vecino y en `ESPERANDO_TRANSFERENCIA`. Un carro que solo pasa no activa la transferencia (como antes).
- **`atender_desde_bodega`:** al terminar de descargar, si el carro tiene servicios en cola, va directo; si no, regresa a su base.
- **`encadenar_servicios`:** al terminar una transferencia, si el carro tiene otro servicio en cola y le cabe (`capacidad − carga ≥ carga anunciada`), lo atiende antes de ir a la bodega.
- **Fila de servicios del carro:** los servicios ganados se atienden en orden (FIFO).

## 7. Subasta (Contract Net)

La cosechadora es el **administrador** del servicio y los carros son los **contratistas**. Cada servicio tiene un id `"<cosechadora>#<número>"`.

| Paso | Mensaje (`tipo_mensaje`) | Performativa | De → a | Payload |
|---|---|---|---|---|
| 1. Llamada | `SOLICITUD_SERVICIO` | `cfp` | cosechadora → cada carro | `servicio`, `x`, `y`, `carga`, `capacidad` |
| 2a. Oferta | `PROPUESTA` | `propose` | carro → cosechadora | `servicio`, `costo` (ticks estimados hasta llegar) |
| 2b. Rechazo | `RECHAZO` | `refuse` | carro → cosechadora | `servicio`, `motivo` (`"sin_capacidad"`, `"combustible"`, `"sin_ruta"`) |
| 3a. Adjudicación | `ACEPTACION` | `accept-proposal` | cosechadora → ganador | `servicio` |
| 3b. Descarte | `RECHAZO_PROPUESTA` | `reject-proposal` | cosechadora → los demás | `servicio` |
| 4. Fin | `TRANSFERENCIA_TERMINADA` | `inform` | cosechadora → ganador | `servicio`, `cantidad` |

- **Costo de la oferta:** ticks estimados para que el carro llegue junto a la cosechadora = duración restante de su fila de servicios (traslados, transferencias y descargas, con las tasas) + distancia BFS desde donde quedará al terminar esa fila (la bodega si `atender_desde_bodega`, si no su base) hasta la cosechadora. Función `rutas.estimar_costo` (Oswaldo).
- **Rechazo:** si el carro no tendría combustible para ir, transferir, descargar y volver respetando la reserva, o si nunca le cabría la carga.
- **Decisión:** la cosechadora espera `espera_propuestas + 2 × retraso máximo de mensajes` ticks desde la llamada (se pueden retrasar la llamada y la respuesta), elige el **menor costo** (empate: menor id) y avisa a todos. Si no hubo propuestas, repite la llamada después de `reintento_subasta` ticks.
- **Lectura del buzón:** en modo subasta los carros leen su buzón **en cada tick**, en cualquier estado (en la línea base solo en `EN_BASE`).
- **Modo `directa` (línea base):** se conserva `LLENA` (`request`) al carro asignado, como en la primera entrega.

Todos los mensajes pasan por el `Buzon`, llevan `id`, performativa y `entrega_en`, y quedan en el log.

## 8. Aleatoriedad con semilla

- Un generador `random.Random` **por fuente**, todos derivados de `seed` (por ejemplo `Random(f"{seed}-rendimiento")`), para que agregar una fuente no cambie las demás. Los crea el `Mundo` (`mundo.azar(fuente)`).
- **Rendimiento por celda:** entero uniforme en `[mínimo, máximo]`, sorteado al crear el mundo. Si una celda no cabe en la tolva (`carga + rendimiento > capacidad`), la cosechadora se considera llena antes de cosecharla.
- **Duraciones:** cada transferencia y descarga dura `ceil(cantidad/tasa) + U{0..duracion_extra_maxima}`.
- **Retraso de mensajes:** con probabilidad p, `entrega_en = t + 1 + U{1..máximo}`; si no, `t + 1`. El buzón entrega por `entrega_en` y, en empate, por id.
- **Reproducibilidad:** misma configuración y misma seed → mismo `trace.json` byte a byte. Seeds distintas → corridas distintas (prueba obligatoria con incertidumbre activa).

## 9. Combustible (dentro de la simulación)

- Cada agente tiene `combustible` (litros, 2 decimales) que empieza con el tanque lleno.
- **Consumo** (lo aplica `simulacion.py` después del paso de cada agente, con `mundo.actualizar_combustible`): `consumo_por_celda_*` si cambió de celda; `consumo_por_tick_encendido` si no se movió y no está en `EN_BASE` ni `FIN` (motor encendido).
- **Recarga:** en su base y en `EN_BASE` o `FIN`, el tanque se llena (instantáneo si `tasa_recarga = 0`; si no, a esa tasa por tick). Se registra un evento `RECARGA`.
- **Reserva (regla de seguridad):** antes de aceptar o empezar un trabajo, el agente estima si le alcanza para terminarlo y volver a su base sin bajar de `reserva × tanque`. Si no, regresa a recargar (la cosechadora retoma su camino después). Si la reserva impidió una acción, se registra `RESTRICCION` con `regla: "combustible_reserva"`.
- **R11:** el combustible nunca es negativo. Prueba obligatoria.

## 10. Seguridad registrada (IEEE 7007)

Evento nuevo `RESTRICCION` (`agente`, `regla`, `detalle`) cada vez que una regla impide o cambia una acción:

| `regla` | Cuándo |
|---|---|
| `R3_celda_ocupada` | El agente no entró a una celda porque otro la ocupaba o reservaba |
| `R4_intercambio` | Se evitó un intercambio de posiciones |
| `R9_bodega` | Una cosechadora no entró a la bodega |
| `R10_obstaculo` | Una ruta rodeó un obstáculo que la cortaba |
| `combustible_reserva` | Un agente fue a recargar o rechazó un servicio por la reserva |

Se registran solo cuando la regla **cambió** la decisión (no en cada tick). Las métricas cuentan las restricciones por regla y por agente.

## 11. Costo J (en lugar del aprendizaje por refuerzo)

```
J = λT · tiempo_completacion + λD · distancia_total + λC · colisiones
  + λW · tiempo_ocioso_total + λF · combustible_usado_total + λR · restricciones
```

- Pesos en `costo.pesos`; las métricas reportan cada término `λ·x` por separado y J total.
- **Justificación de los pesos por defecto:** colisiones casi prohibidas (1000); el ocio es el objetivo del reto (5); tiempo, distancia y combustible como costos operativos (1, 0.5, 0.2); restricciones activadas como señal de riesgo (10).
- **Ablación:** se recalcula J quitando cada término (peso 0) y se revisa si cambia el orden de las estrategias. Con esto se cumple el criterio de «diseño de la recompensa» sin aprendizaje por refuerzo (decisión del 2026-11-23).

## 12. Trace 2.2

Solo agrega campos a la 2.1. El validador acepta 2.1 y 2.2.

| Cambio | Detalle |
|---|---|
| `schema_version` | `"2.2"` |
| `AGENTE.set.combustible` | Nuevo campo permitido (número ≥ 0) |
| `CELDA_COSECHADA.cantidad` | Grano obtenido en esa celda (entero ≥ 1). Opcional: si falta, vale el rendimiento de `mundo.rendimiento` o `grano_por_celda` |
| `mundo.rendimiento` | Opcional: matriz alto × ancho con el grano de cada celda (0 en servicio y obstáculos). Si falta, todas valen `grano_por_celda` |
| `RECARGA` | Evento nuevo: `agente`, `cantidad`, `nivel` (categoría 2) |
| `RESTRICCION` | Evento nuevo: `agente`, `regla`, `detalle` (categoría 2) |
| Mensajes | Tipos y performativas de §7; `entrega_en` puede ser > t + 1 |
| `agentes[]` | Sin cambios (N agentes) |

La fórmula del grano esperado sigue en `datos/campo.py`, ahora sumando `mundo.rendimiento` si existe.

## 13. Escenarios

| Escenario | Mapa | Agentes | Qué prueba |
|---|---|---|---|
| A, B, C | Los de la primera entrega | 1 + 1 | Regresión: mismas métricas que v0.1 con la configuración por defecto |
| D, recurso escaso | 10 × 8, sin obstáculos | 2 cosechadoras + 1 carro | Conflicto por el carro: la subasta y el despacho anticipado deciden a quién atiende |
| E, pasillo | 9 × 8, muro en y = 3 con un hueco en x = 4 | 2 cosechadoras + 2 carros | Conflicto espacial: rutas en el tiempo, 0 colisiones y 0 bloqueos |
| F, estrés | 12 × 9, dos obstáculos | 2 cosechadoras + 2 carros, tanques chicos, incertidumbre activa | Combustible, recargas, restricciones y variabilidad |

Obstáculos de E: `"regiones": [{"inicio": [0, 3], "tamano": [4, 1]}, {"inicio": [5, 3], "tamano": [4, 1]}]`.

**Experimento principal:** escenarios D, E y F × las cuatro estrategias del §2 × 20 seeds (0 a 19), con media, desviación estándar e IC 95 % de cada métrica y de J.

## 14. Servidor FastAPI y Unity

Python sigue siendo la única fuente de verdad: el servidor corre la simulación y entrega el trace; Unity solo lo reproduce.

| Método y ruta | Respuesta |
|---|---|
| `GET /api/salud` | `{"estado": "ok", "schema_version": "2.2"}` |
| `GET /api/escenarios` | Lista de escenarios de `config/` con sus parámetros |
| `GET /api/escenarios/{nombre}/trace?seed=0&estrategia=base` | Corre (o devuelve de caché) y entrega el trace validado |
| `POST /api/simulaciones` | Cuerpo: configuración completa o `{"escenario", "estrategia", "seed", "cambios"}`. Entrega el trace validado; 422 con los errores si la configuración o el trace no son válidos |

- Se arranca con `uvicorn harvest_sim.servidor:app` (dependencias fijadas en `requirements.txt`).
- CORS abierto a `localhost` para el Editor de Unity (y después para WebGL).
- Unity pide la lista de escenarios, deja elegir escenario, estrategia y seed, y reproduce el trace recibido. Si el servidor no responde, carga un trace local.

## 15. Trabajo futuro (documentado, no se implementa ahora)

- **WebGL:** el visor de Unity embebido en el dashboard, en la entrega final.
- **OpenClaw / NemoClaw (bono):** se evaluará en la entrega final. Justificación para dejarlo después: (1) el bono exige comparar contra la línea base clásica, que primero debe estar estable con varios agentes; (2) el curso cubre estas herramientas en la penúltima semana; (3) su lugar natural es la capa de coordinación (por ejemplo, un agente que decide la estrategia o los pesos de J consultando métricas), que ya queda separada en la política y la subasta. Se documentará su seguridad, latencia y dependencias en una nota de una página.
- **Aprendizaje por refuerzo:** sustituido por el costo J descompuesto con ablación (§11).

## 16. Pruebas mínimas nuevas

| Prueba | Verifica |
|---|---|
| `test_regresion_linea_base` | A, B y C con la configuración por defecto dan las métricas de v0.1 |
| `test_config_secciones_nuevas` | Valores por defecto y errores claros de `politica`, `incertidumbre`, `combustible`, `costo` |
| `test_franjas` | Las franjas cubren cada celda libre del campo una sola vez, sin obstáculos |
| `test_no_entra_a_obstaculo` | R10 en cada tick |
| `test_pasillo_sin_colisiones_ni_bloqueos` | Escenario E: 0 colisiones, 0 `BLOQUEO`, termina |
| `test_bfs_tiempo_respeta_reservas` | Nunca usa una `(celda, tick)` reservada ni se intercambia |
| `test_subasta_secuencia` | cfp → propose/refuse → accept/reject, ids y performativas correctas |
| `test_subasta_menor_costo` | Gana la menor oferta; empate por id |
| `test_umbral_aviso` | La llamada sale al llegar al umbral |
| `test_transferencia_solo_contratado` | Un carro no contratado no activa la transferencia |
| `test_semilla_reproducible` | Misma seed → mismo trace; seeds distintas → traces distintos (con incertidumbre) |
| `test_retraso_mensajes` | `entrega_en` dentro de `[t+1, t+1+máximo]` y entrega en ese tick |
| `test_combustible_nunca_negativo` | R11 y recarga en la base |
| `test_restriccion_registrada` | Cada regla del §10 genera su evento cuando cambia una decisión |
| `test_costo_j` | Términos y total calculados a mano |
| `test_servidor` | Las cuatro rutas de §14 con `TestClient` |

## 17. Preguntas frecuentes

**¿Qué es el despacho anticipado?** En la línea base la cosechadora avisa cuando ya está llena, y desde ese momento espera todo el viaje del carro. Con el despacho anticipado avisa antes (por ejemplo al 70 % de carga): el carro sale mientras ella sigue cosechando y llega más o menos cuando se llena, así que la espera baja. El umbral se puede variar para encontrar el mejor.

**¿Por qué subasta y no «el carro más cercano»?** Porque la subasta es un protocolo de comunicación entre agentes (Contract Net, con performativas KQML/FIPA-ACL) y decide con información que solo tiene cada carro: cuánto trabajo pendiente tiene y cuánto combustible le queda. «El más cercano» lo decide alguien desde fuera con información global.

**¿Por qué reservas en el tiempo y no solo recalcular?** Porque en un pasillo dos carros que recalculan se bloquean mutuamente. Con reservas, el segundo planea esperar o rodear desde antes, y no hay colisiones ni bloqueos.

**¿Por qué la configuración por defecto debe dar lo mismo que v0.1?** Para que la línea base no cambie: cada mejora se compara contra los mismos números, en los mismos escenarios y semillas.
