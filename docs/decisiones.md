# Registro de decisiones de diseño

Anota aquí cada decisión que no esté cubierta por [la especificación](especificacion_primera_entrega.md), o cada cambio al contrato de interfaces (§10 de la especificación).

Formato por entrada:

```
## AAAA-MM-DD — Título corto
- **Quién:** nombre (bloque)
- **Decisión:** qué se decidió
- **Alternativa considerada:** qué otra opción había
- **Por qué se descartó:** razón
- **Afecta a:** bloques o archivos
```

---

<!-- Agrega las entradas debajo, la más reciente al final -->

## 2026-11-15 — Formato del trace v2.0: log de cambios por tick (reemplaza la entrada provisional del 2026-11-14)
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. `trace.json` v2.0: primer nivel estático (`schema_version`, `meta`, `config`, `mundo`, `agentes`), más `ticks` y `metricas`.
  2. `ticks` es un **arreglo** ordenado por tick, solo con los ticks que tienen cambios (el 0 siempre aparece); `meta.total_ticks` da el último tick.
  3. Cada tick lleva una **lista cronológica de eventos tipados** (`AGENTE`, `CELDA_COSECHADA`, `DEPOSITO`, `BLOQUEO`, `MENSAJE_ENVIADO`, `MENSAJE_ENTREGADO`) con orden fijo por categoría.
  4. Los mensajes van **dentro de los ticks** como eventos (no en una lista aparte) y además se imprimen por consola con `logging` (§6.3 de la especificación).
  5. ~~`intencion.celdas` por tick~~ **REEMPLAZADA** por la entrada siguiente: el log no guarda rutas ni intenciones.
  6. **Checksum por tick** (sobre `{tick, cambios}` en JSON canónico).
  7. El log guarda **hechos con valores nuevos explícitos** y todo lo derivado ya calculado (orientación, totales). Colores, sprites y animación son decisión de la herramienta de visualización.
  8. Versión **2.0**: es incompatible con el esquema v1.0 de la propuesta (un registro por agente en cada tick); los campos `pose`, `estado` y `carga` de v1.0 se conservan dentro de `AGENTE.set`; `intencion` y `objetivo` salen (ver la entrada siguiente).
  9. El archivo se escribe con orden de inserción fijo (no `sort_keys`); el orden canónico se usa solo en el checksum.
- **Alternativas consideradas:** foto completa de agentes y mapa en cada tick (v1.0); agentes completos por tick y solo el mapa por cambios (primera versión del 2026-11-14); `ticks` como diccionario con claves de texto; diccionarios por entidad dentro de cada tick; lista de mensajes aparte; `intencion.celdas` como ruta completa fijada una sola vez; checksum por registro de agente.
- **Por qué se descartaron:** la foto por tick crece como ticks × celdas; el híbrido deja al visor deduciendo el estado del mapa; con `ticks` como diccionario las claves (texto) se ordenan mal al escribir con claves ordenadas (`"10"` antes que `"2"`) y Unity (`JsonUtility`) no lee diccionarios con claves dinámicas; los diccionarios por entidad no admiten dos cambios del mismo agente ni dos mensajes en un tick, y pierden el orden; una lista de mensajes aparte duplica la fuente de verdad; la ruta completa fijada una vez obliga al visor a derivar la ruta restante a partir de la pose (lógica en el visor); el checksum por agente repite huellas en cada registro.
- **Afecta a:** Carlos (`Mundo.descripcion`, `drenar_eventos`), Emilio (`Buzon.drenar_eventos`; `registro()` de la cosechadora), Oswaldo (`registro()` del carro), Joel (`TraceBuilder`, `reconstruir`, métricas), Giovanni (visor y CLI), Ilan (tests).

## 2026-11-15 — El log guarda solo cambios explícitos: se quitan `intencion` y `objetivo` y se agrega `BLOQUEO` (corrige la decisión 5 de la entrada anterior)
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. `AGENTE.set` solo lleva `pose`, `estado` y `carga`.
  2. Se quitan `intencion` (acción y celdas) y `objetivo`: el `estado` ya indica a dónde va el agente (`YENDO_A_BODEGA`, `REGRESANDO_A_BASE`…).
  3. Un bloqueo (el agente esperó por una celda ocupada) es un hecho y se registra como evento `BLOQUEO` (`mundo.registrar_bloqueo(agent_id)`); `ticks_bloqueados` cuenta esos eventos.
  4. Criterio general: al log entra solo lo que es un hecho explícito de lo que cambió; nunca algo que el visor tenga que interpretar según el algoritmo del agente.
- **Alternativa considerada:** guardar `intencion.celdas` (próximas celdas en cada tick, o la ruta completa una sola vez) y guardar `intencion.accion` y `objetivo`.
- **Por qué se descartó:** rutas e intenciones dependen del algoritmo (BFS hoy, otro mañana); si estuvieran en el log, el visor tendría que interpretarlas y habría que cambiarlo cada vez que cambie el agente, y la lógica quedaría repartida entre Python y el visor (la propuesta dice que el visor solo reproduce y no decide). Además, repetir en cada tick lo que falta por recorrer es ineficiente: el progreso se expresa con `CELDA_COSECHADA`, como máximo n × m eventos porque una celda no se cosecha dos veces. Una función en el visor sería más compacta, pero repartiría la lógica.
- **Afecta a:** Carlos (`Mundo.registrar_bloqueo`), Emilio y Oswaldo (`registro()` sin `intencion` ni `objetivo`; llamar a `registrar_bloqueo`), Joel (`TraceBuilder`, métricas), Giovanni (visor), Ilan (tests).

## 2026-11-15 — Métricas calculadas desde el log: una por cada variable en juego
- **Estado:** DECIDIDO (revisable cuando cambien las funciones de costo o se agregue el combustible).
- **Quién:** Joel (Datos)
- **Decisión:** todas las métricas se calculan solo desde el `trace.json` (reconstruyendo el estado de cada tick) y hay una por cada variable en juego, para ver el efecto de modificar las funciones de costo sin perder información. Se cuentan los ticks 0..`total_ticks` (ambos incluidos). Definiciones:
  - Tiempo: `tiempo_completacion` = `total_ticks`; `tick_fin_cosecha` = tick del último `TRANSFERENCIA_TERMINADA` enviado (`null` si no hay); `tiempo_ocioso_cosechadora` = ticks en `LLENA_ESPERANDO`; `tiempo_transfiriendo`; `porcentaje_ocioso` = ticks ociosos entre los ticks totales (%); `ticks_por_estado` = ticks de cada agente en cada estado; `espera_por_ciclo` = largo de cada racha consecutiva de `LLENA_ESPERANDO`.
  - Movimiento: `distancia_*` = ticks en que cambió la celda (x, y) del agente (girar sin cambiar de celda no cuenta); `colisiones` = ticks (no pares) con dos agentes en la misma celda o intercambiando posiciones; `ticks_bloqueados` = eventos `BLOQUEO` por agente.
  - Distancia cosechadora–carro: distancia Manhattan por tick; se resume con `_promedio`, `_minima` y `_maxima`.
  - Coordinación: `num_ciclos` = mensajes `LLENA` enviados; `mensajes_enviados` por tipo; `utilizacion_carro` = ticks con el carro fuera de `EN_BASE` entre el total (4 decimales).
  - Grano: `grano_cosechado_total`, `grano_total_entregado` (suma de los `DEPOSITO`), `grano_esperado_total` = `ancho × (alto − 1) × grano_por_celda` y `porcentaje_entregado` (entregado entre esperado, %).
  - Series por tick (`series_temporales`, para las gráficas, no se guardan en el trace): ocioso acumulado, distancia cosechadora–carro, cargas de ambos, grano cosechado acumulado, grano en la bodega y bloqueos acumulados.
  - Pendiente: combustible (todavía no está en el trace).
- **Alternativa considerada:** promedio del ocioso por ciclo o entre corridas; distancia solo por ciclo, en el momento del aviso `LLENA`; calcular las métricas dentro de la simulación; contar pares de colisión; contar solo los ticks que aparecen en el archivo.
- **Por qué se descartó:** se prefiere ver el ocioso acumulado en el tiempo (la curva muestra el total hasta cada tick) y la distancia por tick; las métricas deben poder recalcularse desde el log para ser verificables; los ticks omitidos también cuentan.
- **Afecta a:** Joel (`calcular_metricas`, `series_temporales`); el resto del equipo solo las lee del `trace.json` (clave `metricas`).

## 2026-11-16 — Formato del trace 2.1: obstáculos, clases de la ontología y performativa (solo agrega campos a la 2.0)
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. `mundo.obstaculos`: lista ordenada de celdas `[x, y]` con obstáculo, ya expandida (vacía en esta entrega). La genera `Mundo.descripcion()`.
  2. Clases de la ontología del curso ([docs/ontologia.md](ontologia.md)): `meta.clase = "AccountabilityRecord"`, `agentes[].clase = "AutonomousAgriculturalRobot"` (el `tipo` sigue siendo el rol) y `mundo.clase_celdas = "SemanticMapCell"`. Las pone `TraceBuilder`: nadie las escribe a mano.
  3. `MENSAJE_ENVIADO.performativa`: el acto comunicativo (KQML / FIPA-ACL). `LLENA` → `request`, `TRANSFERENCIA_TERMINADA` → `inform`. La pone el `Buzon` con `datos.formato.PERFORMATIVAS`.
  4. El archivo se escribe con el primer nivel indentado (coordenadas en una línea) y **cada tick en una sola línea**: pesa la mitad y sigue siendo reproducible byte a byte.
  5. El validador acepta cualquier `tipo` de agente (texto no vacío), recibe `retraso_maximo` (default 1) para la entrega de mensajes y devuelve avisos, aparte de los errores, para estados que no están en el vocabulario.
- **Alternativa considerada:** dejar la ontología solo en el reporte; deducir la performativa en Datos; mantener `indent=2` en todo el archivo.
- **Por qué se descartó:** la rúbrica del curso pide las clases «en el diseño y en los logs»; la performativa es una decisión de quien envía el mensaje, no algo que el log deba adivinar; con `indent=2` cada coordenada ocupa 4 líneas (1,46 MB contra 0,73 MB en un campo de 640 celdas).
- **Afecta a:** Carlos (`descripcion()` con `obstaculos`), Emilio (`performativa` en el `Buzon`), Giovanni (visor: dibujar obstáculos), Ilan (pruebas), Joel (formato, validador, generador).

## 2026-11-16 — Métricas para cualquier número de agentes: promedio por defecto y detalle por agente
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. Magnitudes de cada agente (tiempo ocioso, % ocioso, tiempo transfiriendo, distancia recorrida, utilización del carro): el nivel superior de `metricas` lleva el **promedio entre los agentes de ese tipo**; el detalle de cada agente va en `metricas["por_agente"][agent_id]` (incluye `ticks_por_estado` y `espera_por_ciclo`).
  2. Magnitudes del sistema (completación, fin de la cosecha, distancia total, bloqueos, colisiones, ciclos, mensajes, grano): un solo valor total. `ticks_bloqueados` pasa de diccionario por agente a total (el detalle está en `por_agente`).
  3. `espera_promedio_por_ciclo` reemplaza a la lista `espera_por_ciclo` del nivel superior (la lista queda por agente).
  4. Distancia cosechadora–carro: para cada cosechadora, en cada tick, la distancia Manhattan al **carro más cercano**; promedio, mínima y máxima sobre todas las cosechadoras y ticks.
  5. Un promedio que da entero se guarda como entero (`23`, no `23.0`); los demás, con 4 decimales.
  6. Series por tick: ocio acumulado y distancia al carro, promedio por cosechadora; grano cosechado, en tránsito (suma de cargas) y en la bodega; bloqueos; y `por_agente` con las series de cada uno.
  7. Rendimiento: métricas, series y gráficas leen de una sola pasada por el trace (`linea_de_tiempo`), sin copiar el estado en cada tick (de 2,34 s a 0,009 s en un campo de 640 celdas).
- **Alternativa considerada:** sumar entre agentes; tomar el primer agente de cada tipo (lo que hacía la versión anterior); distancia al primer carro.
- **Por qué se descartó:** la suma crece con el número de agentes y no permite comparar escenarios con distinta flota; el primer agente ignora a los demás; con varios carros, el relevante es el más cercano.
- **Afecta a:** Joel (métricas, gráficas, tabla); el resto lee `metricas` del trace.

## 2026-11-16 — Campo, obstáculos y grano esperado: una sola fórmula
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos), con Carlos (Mundo) como usuario
- **Decisión:**
  1. Fórmula única (`harvest_sim/datos/campo.py`): `celdas_de_campo(mundo)` = celdas con `0 ≤ x < ancho` y `1 ≤ y < alto`, menos los obstáculos; `grano_esperado(mundo)` = celdas de campo × `grano_por_celda`. La usan las métricas, las gráficas, el validador, `Mundo.grano_total` y las pruebas de integración.
  2. Sección nueva de la configuración: `"obstaculos": {"celdas": [[x, y], ...], "regiones": [{"inicio": [x, y], "tamano": [ancho, alto]}, ...]}`, vacía en los tres escenarios.
  3. `expandir_obstaculos(seccion, ancho, alto)` valida y expande: enteros; dentro del mapa (regiones completas); tamaño ≥ 1; nada en la fila 0 (servicio); todo el campo libre alcanzable desde la bodega. Devuelve la lista ordenada para `mundo.obstaculos`.
  4. En esta entrega la simulación **no** recorre obstáculos: `cargar_config` los valida y, si la lista no está vacía, falla con «obstáculos aún no soportados» (igual que `num_carros` ≠ 1). El generador de ejemplo también los rechaza.
- **Alternativa considerada:** que cada configuración declare su total esperado; escribir la fórmula en cada módulo; soportar obstáculos ya en la serpentina y en las rutas.
- **Por qué se descartó:** un total escrito a mano se desincroniza del mapa; la fórmula repetida estaba en dos lugares y no consideraba obstáculos; recorrerlos exige cambiar la serpentina y las rutas, que no cabe antes del martes (el §1 de la especificación los deja fuera).
- **Afecta a:** Carlos (`config.py`, `Mundo`, JSON de escenarios), Ilan (`test_config.py`), Joel.

## 2026-11-16 — Gráficas finales y experimentos
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. Por corrida, 6 gráficas, cada una responde una pregunta distinta: línea de tiempo de estados, ocio acumulado, distancia al carro más cercano, **flujo del grano** (en la bodega + en tránsito = cosechado, contra el esperado; reemplaza a «carga de la cosechadora» y a «grano cosechado y en la bodega», que repetían datos), mapa de calor de la espera y mapa de calor del tráfico. Con varios agentes muestran promedios; `--agente <id>` muestra una cosechadora.
  2. Comparación entre escenarios con 6 indicadores: completación, ocio por cosechadora, distancia total, distancia media cosechadora–carro, utilización del carro y bloqueos. Salen «fin de la cosecha» (casi igual a la completación), «% ocioso» (la misma cifra normalizada) y «% entregado» (siempre 100 en una corrida completa); los tres siguen en la tabla.
  3. Ejecutor de experimentos (`tools/correr_experimento.py`, JSON en `config/experimentos/`): escenarios × barrido de parámetros × repeticiones (seed + r), con resultados por corrida, resumen con media, desviación estándar e IC 95 % (t de Student) y gráfica de sensibilidad. Con la simulación determinista, el resumen indica «sin variación».
- **Alternativa considerada:** conservar las 5 gráficas y los 8 paneles anteriores; correr los experimentos a mano.
- **Por qué se descartó:** había pares de gráficas y paneles con la misma información; la rúbrica nueva pide variar parámetros, repetir corridas y recomienda mapas de calor.
- **Afecta a:** Joel; Giovanni (el dashboard usa estas imágenes); Ilan (`scripts/correr_todos.sh`).

## 2026-11-17 — Rutas: casos de borde no especificados
- **Estado:** DECIDIDO.
- **Quién:** Oswaldo (Rutas)
- **Decisión:**
  1. `bfs` devuelve `None` si el destino está en `bloqueadas` (por ejemplo, ocupado por otro agente): el agente espera en vez de intentar entrar.
  2. `elegir_celda_objetivo` mide las distancias con la celda de la cosechadora (`objetivo`) como bloqueada, y entiende «salvo que sea la única opción» como «la única **alcanzable**»: si ninguna vecina fuera de `evitar` tiene ruta, usa la mejor de `evitar`.
  3. `siguiente_paso` recalcula con BFS si la ruta viene vacía o si su primera celda ya no es vecina de `pos` (ruta vieja); si `pos == destino` devuelve `(None, [])`, que no es un bloqueo (el agente debe revisar si llegó antes de pedir el paso). Nunca modifica la lista `ruta` que recibe.
- **Alternativa considerada:** dejar que `bfs` entre a un destino bloqueado; excluir `evitar` aunque las demás vecinas sean inalcanzables; confiar en que la ruta siempre esté al día.
- **Por qué se descartó:** entrar a un destino ocupado rompería R3; excluir la única vecina alcanzable dejaría al carro sin objetivo; una ruta vieja haría que el agente «saltara» (R2).
- **Afecta a:** Carlos (`Mundo.ruta_bfs`), Emilio (cosechadora), Oswaldo (carro).

## 2026-11-17 — Carro: tiempos, tasa de descarga y mensajes apartados
- **Estado:** DECIDIDO.
- **Quién:** Oswaldo (Carro)
- **Decisión:**
  1. En los estados de viaje, el carro da su paso y, si con ese paso llegó, cambia de estado en el mismo tick (`ESPERANDO_TRANSFERENCIA`, `DESCARGANDO` o `EN_BASE`), igual que el simulador de referencia (`tools/generar_trace_ejemplo.py`). Las transiciones que salen de `EN_BASE`, `ESPERANDO_TRANSFERENCIA` y `DESCARGANDO` no incluyen movimiento.
  2. `Carro(agent_id, capacidad, tasa_descarga=None)`: si no se pasa la tasa, se lee de `mundo.config.tasa_descarga` al entrar a `DESCARGANDO` (la cosechadora lee `mundo.config.tasa_transferencia`). **Requiere** que `Mundo` guarde `self.config = config`, o que `simulacion` pase las tasas al crear los agentes.
  3. Si en `ESPERANDO_TRANSFERENCIA` sale un `LLENA` de la fila (el buzón no permite ver sin sacar), el carro lo aparta y lo atiende primero al volver a `EN_BASE`; nunca se descarta.
  4. `carro.duracion_descarga` usa la misma fórmula que `mundo.duracion_ticks` (§4.3), porque en `development` esa función aún es esqueleto; se puede sustituir cuando llegue `mundo.py`.
- **Alternativa considerada:** cambiar de estado un tick después de llegar; pasar la tasa solo por constructor; ignorar mensajes que no sean `TRANSFERENCIA_TERMINADA` mientras espera.
- **Por qué se descartó:** el tick extra no aporta nada y desalinea los traces con el simulador de referencia; `simulacion.py` ya crea el carro sin tasa; ignorar un `LLENA` rompería la regla del carro ocupado.
- **Afecta a:** Carlos (`Mundo.config` o constructor en `simulacion.py`), Emilio (misma convención de `mundo.config`), Joel (métricas de duración).

## 2026-11-17 — Integración de la entrega: el mundo expone su configuración y se activan todas las pruebas
- **Estado:** DECIDIDO.
- **Quién:** Joel (integración, con el acuerdo del equipo de integrar sin revisión de PR)
- **Decisión:**
  1. `Mundo` guarda la configuración en `mundo.config`. La cosechadora y el carro leen de ahí `tasa_transferencia` y `tasa_descarga`; sin esto la simulación fallaba en la primera transferencia. Queda en el contrato (§10 de la especificación).
  2. Se quitan todos los `skip`: las pruebas de mundo, configuración e integración corren contra la simulación real (230 pruebas).
  3. `scripts/correr_todos.sh` exporta los cuadros del visor antes de armar el dashboard, para que el panel del entorno tenga imágenes.
  4. El error de obstáculos fuera del mapa dice «fuera del mapa», como espera `test_config.py`.
  5. El README se reescribe como documento global del proyecto (antes, una rama lo regresaba al del esqueleto y otra lo ampliaba).
- **Alternativa considerada:** pasar las tasas a los constructores de los agentes desde `simulacion.py`.
- **Por qué se descartó:** los dos agentes ya estaban escritos y probados leyendo `mundo.config`; exponerla en el mundo es una línea y no cambia sus pruebas.
- **Afecta a:** Carlos (`mundo.py`), Emilio y Oswaldo (lectura de las tasas), Ilan (pruebas y script), Joel.

## 2026-11-23 — Plan de la segunda entrega: coordinación multiagente
- **Estado:** DECIDIDO (equipo, propuesta de Joel).
- **Quién:** Joel, con las respuestas del equipo
- **Decisión:**
  1. **Asignación por subasta (Contract Net):** la cosechadora es administradora y los carros contratistas (cfp → propose/refuse → accept/reject → inform). Se conserva el modo `directa` como línea base.
  2. **Despacho anticipado** por `umbral_aviso` (la cosechadora pide el carro antes de llenarse y el carro la acompaña), con dos variantes medibles por separado: `atender_desde_bodega` y `encadenar_servicios`. Cuatro estrategias: `base`, `subasta`, `anticipada`, `anticipada_plus`.
  3. **Rutas con reservas espacio-tiempo** (BFS en (celda, tick) con espera); una espera planeada no es `BLOQUEO`.
  4. **Obstáculos en la simulación** (franjas sin obstáculos, traslados con BFS); regla R10.
  5. **Aleatoriedad con semilla** en tres fuentes independientes: rendimiento por celda, duraciones y retraso de mensajes. Sin incertidumbre, idéntico a v0.1.
  6. **Combustible dentro de la simulación** (antes se calculaba desde el log y se retiró): consumo por celda y por tick encendido, recarga en la base, reserva de seguridad; campo `combustible` en el registro y evento `RECARGA`; regla R11.
  7. **Restricciones de seguridad registradas** con el evento `RESTRICCION` (IEEE 7007).
  8. **Costo J descompuesto con ablación** en lugar de aprendizaje por refuerzo.
  9. **Trace 2.2** (solo agrega campos); el validador acepta 2.1 y 2.2.
  10. **Unity sigue en su repositorio** (`harvest-simu-visualization`); se comunica con un **servidor FastAPI** en harvest_sim. WebGL, en la entrega final.
  11. **OpenClaw/NemoClaw** se evalúa en la entrega final (justificación en la especificación §15).
  12. Mismos roles; el reporte lo arma Joel. El plan no lleva fechas.
- **Alternativa considerada:** carro libre más cercano o fila global; seguir recalculando rutas ante celdas ocupadas; combustible solo desde el log; aprendizaje por refuerzo; traer Unity a este repositorio.
- **Por qué se descartó:** la subasta es un protocolo de comunicación entre agentes (tema del curso) y decide con información local de cada carro; recalcular provoca bloqueos mutuos en pasillos; el combustible debe influir en las decisiones para ser una restricción real; el aprendizaje por refuerzo no cabe con una línea base aún creciendo y la rúbrica acepta un costo descompuesto; Unity en otro repositorio mantiene ligero este y permite ciclos de trabajo separados.
- **Afecta a:** todos (ver `docs/especificacion_segunda_entrega.md` y `docs/equipo/`).

## 2026-11-23 — Rutas en el tiempo y carro contratista: casos no especificados
- **Estado:** DECIDIDO.
- **Quién:** Oswaldo (Rutas y carro)
- **Decisión:**
  1. **Convención de tiempo:** `(celda, t)` = dónde está el agente al final del tick `t`. En el paso del tick `t` se llama `rutas.bfs_tiempo(pos, destino, t − 1, ...)`; el primer elemento de la ruta es la celda del tick `t`. Cada agente reserva con `mundo.reservar` desde `(pos, t)`.
  2. **`bfs_tiempo` sin límite artificial:** después del horizonte los estados se colapsan a uno por celda (BFS normal), así que la búsqueda siempre termina y no corta rutas largas. Orden de expansión: esperar, N, E, S, O.
  3. **Llegada con permanencia:** solo se llega al destino si nadie más lo tiene reservado mientras el agente se queda (`permanencia`; `None` = todo el horizonte). En la bodega la permanencia es la descarga, y se reserva completa aunque pase del horizonte. Parámetro opcional de `bfs_tiempo` y `reservas_de_ruta`; la firma de la guía no cambia.
  4. **Reglas del carro para no esperarse para siempre:** primer paso nunca a una celda ocupada (R3 conservadora); compromiso con el plan vigente (solo lo cambia por uno que llegue antes); reserva hasta `tick + H + 1`; mientras descarga reserva también su salida; a los agentes quietos se les supone en su celda todo el horizonte; un carro encerrado le pide paso a un carro en viaje que esté en su camino (gana el id menor). Detalle en `docs/equipo/oswaldo/carro.md` §12.
  5. **Estimaciones deterministas:** el costo de la oferta y el combustible estimado usan `ceil(cantidad / tasa)`, no `mundo.duracion` (que sortea el extra aleatorio y cambiaría la secuencia del generador).
  6. **Encadenar con la capacidad, no con la carga anunciada:** con despacho anticipado la cosechadora sigue cosechando hasta llenarse.
  7. **Tipos de mensaje por texto:** el carro compara `tipo` por su valor (`"PROPUESTA"`, …) y crea los mensajes con `TipoMensaje(texto)`; no depende del orden en que se integren el buzón y el carro. Motivo extra de rechazo `"sin_ruta"` si la cosechadora es inalcanzable (no debería pasar).
  8. **`registro()`** agrega `combustible` solo cuando el mundo ya lo puso (`carro.combustible` no es `None`).
  9. **Limitación conocida:** con 3 carros o más, la bodega con una sola entrada (carro_1 estacionado en `(1, 0)`) puede dejar a dos carros esperándose; en la prueba de estrés pasó en 36 de 520 corridas con 3 carros y en 0 de 608 con 2. Los escenarios de la entrega usan como máximo 2 carros.
- **Alternativa considerada:** límite de `4 × (ancho + alto)` ticks; tratar la bodega como estacionamiento (quedarse todo el horizonte); replanear desde cero en cada tick; estimar con `mundo.duracion`; agregar los tipos de mensaje al enum desde la rama del carro.
- **Por qué se descartó:** el límite puede cortar rutas válidas; la bodega como estacionamiento y el replaneo sin compromiso producían esperas mutuas sin fin en la prueba de estrés (dos carros siguiéndose por un pasillo); `mundo.duracion` consume números aleatorios; el enum es de Emilio.
- **Afecta a:** Emilio (la cosechadora usa `bfs_tiempo` y `reservas_de_ruta` con la misma convención de tiempo, y debe reservar su celda cuando está quieta), Carlos (`mundo.reservar` debe reemplazar las reservas del agente desde el primer tick de la lista; `mundo.posicion` y `mundo.estado_de` para todos los ids del §3), Ilan (prueba del pasillo), Joel (`combustible` en el registro).

## 2026-11-24 — Datos de la segunda entrega: formato 2.2, métricas nuevas, comparación pareada y servidor
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos)
- **Decisión:**
  1. **Formato 2.2** en `datos/formato.py`: 7 tipos de mensaje con su performativa, claves obligatorias de cada payload (error si faltan), motivos de rechazo (`sin_capacidad`, `combustible`, `sin_ruta`) y reglas de `RESTRICCION`; un motivo o una regla desconocidos son **aviso**, no error. `combustible` en el registro es opcional (solo si la simulación lo modela). `CELDA_COSECHADA.cantidad` es opcional: si falta, se usa el rendimiento de la celda. El validador acepta 2.1 y 2.2 y toma el retraso máximo de mensajes de la configuración del trace.
  2. **Métricas nuevas** (al final, sin cambiar las de v0.1): `tiempo_ocioso_total`; combustible usado = inicial − final + recargado, comprado = inicial + recargado, recargas y mínimo (al final de cada tick); restricciones por regla y por agente; servicios, propuestas por servicio, rechazos por motivo y respuesta promedio (ticks desde la primera llamada de un servicio hasta que empieza su transferencia); servicios ganados por carro.
  3. **`num_ciclos`** pasa a contar transferencias terminadas: en la línea base es igual al número de `LLENA` y sigue siendo correcto con la subasta.
  4. **Costo J** = suma de peso · valor de cada término (tiempo, distancia, colisiones, ocio total, combustible usado, restricciones), con los pesos de `config.costo.pesos` o los por defecto; cada término se reporta por separado.
  5. **Comparación pareada por seed** contra `base`: diferencia estrategia − base seed por seed, IC 95 % con t de Student y veredicto (mejora, empeora, igual, no concluyente si el IC cruza el 0, informativa). **Ablación de J**: orden de las estrategias con cada término quitado.
  6. **Traces de ejemplo 2.2** escritos como guion (`tools/traces_ejemplo_22.py`), no extendiendo el generador.
  7. **Servidor FastAPI** con simulador inyectable y modo de ejemplo; dependencias fijas (fastapi 0.115.6, uvicorn 0.32.1, httpx 0.28.1).
- **Alternativa considerada:** `cantidad` obligatoria en 2.2; comparar medias sin emparejar; extender el generador con la subasta; contar `num_ciclos` como mensajes `LLENA`.
- **Por qué se descartó:** `cantidad` obligatoria rompía las corridas mientras `mundo.cosechar` no la envíe; sin emparejar, la variación entre seeds ensancha los intervalos; el generador duplicaría la lógica de Emilio y Oswaldo; con la subasta no hay `LLENA` y la métrica valdría 0.
- **Afecta a:** Emilio y Oswaldo (importar tipos y performativas de `datos.formato`), Carlos (`cantidad` y `combustible` opcionales), Mario Giovanni (traces de ejemplo, servidor, `ESTRATEGIAS`), Ilan (dependencias del CI).

## 2026-11-24 — Mundo de la segunda entrega: franjas, reservas, rendimiento y combustible
- **Estado:** DECIDIDO.
- **Quién:** Joel, en nombre de Carlos (Mundo).
- **Decisión:**
  1. **Secciones opcionales:** `cargar_config` exige solo los campos de la primera entrega. `politica`, `incertidumbre`, `combustible` y `costo` se completan con sus valores por defecto (también los dicts anidados) y rechazan las claves desconocidas. Los defectos de `politica` viven en `config.POLITICA_POR_DEFECTO`, y los pesos de J en `datos.metricas.PESOS_COSTO`, que es la única fuente.
  2. **Rendimiento por defecto = `grano_por_celda`.** La regla del múltiplo de la capacidad se exige solo con rendimiento fijo. La matriz `rendimiento` va en la descripción solo si alguna celda da distinto de `grano_por_celda`.
  3. **Franjas:** cada corte va después de la fila cuyo acumulado de celdas libres queda más cerca de k·N/m; en empate, la franja de arriba se queda con la fila. Resultados: D da 40/30 y E da 28/27. La serpentina usa la paridad global (fila impar: x creciente), así que con una cosechadora es la de v0.1. Nueva validación: `alto − 1 ≥ num_cosechadoras`.
  4. **Reservas:** `reservar` reemplaza las del agente desde el primer tick de la lista. Si otro ya tiene esa `(celda, tick)`, gana quien reservó primero (el orden del tick). `nuevo_tick` olvida las pasadas.
  5. **Recarga con los tanques por defecto:** los agentes recargan al volver a su base aunque el tanque sea enorme (la regla del §9 no distingue). A, B y C tienen ahora eventos `RECARGA` y `combustible` en el log, pero **ninguna métrica de v0.1 cambia** (`test_regresion`). Se corrigió en la especificación el texto «nunca recargan».
  6. **Buzón:** en esta rama, `ejecutar` crea `Buzon()`; el buzón con retraso llega con la parte de mensajes.
- **Alternativa considerada:** no registrar combustible cuando la sección falta; sobrescribir la reserva de otro agente; franjas por número de filas.
- **Por qué se descartó:** dos comportamientos según si la sección existe confunden y complican las métricas; sobrescribir en silencio permite choques; contar filas ignora los obstáculos (en E, la fila del muro tiene una sola celda).
- **Afecta a:** Emilio (`camino`, `rendimiento`, `duracion`, `combustible_para`, `reservar`), Oswaldo (la API que su carro ya usa), Ilan (pruebas de `test_mundo` y `test_config`), Joel (combustible y `RECARGA` en el log).

## 2026-11-24 — Buzón con retraso y cosechadora administradora: casos no especificados
- **Estado:** DECIDIDO.
- **Quién:** Joel, en nombre de Emilio (mensajes y cosechadora).
- **Decisión:**
  1. **Reintento = servicio nuevo** (`#n + 1`). Así cada servicio tiene exactamente un cfp por carro.
  2. **Espera de propuestas:** `espera_propuestas + 2 × retraso máximo`, porque se pueden retrasar la llamada y la respuesta. Se corrigió el texto de la especificación.
  3. **La llamada se evalúa justo después de cosechar**, en el mismo tick (como el `LLENA` de v0.1). Si se evaluara al inicio del paso siguiente, la subasta saldría un tick tarde frente a la base.
  4. **En `FIN` la cosechadora sigue vaciando su buzón:** un mensaje viejo sin leer deja `hay_pendientes` en verdadero y la simulación nunca termina.
  5. **Sin estados nuevos:** ir a recargar usa `REGRESANDO_A_BASE` y `EN_BASE` (el validador, el visor y Unity solo conocen los 7 estados).
  6. **Combustible de la cosechadora:**
     - tras cada transferencia estima solo la siguiente carga; con todo lo que falta del camino, un tanque chico nunca alcanzaría;
     - la espera estimada es la mayor entre la teórica y la última que vivió, y el regreso lleva un margen del 25 %;
     - **regreso de emergencia:** si mientras cosecha o espera ya solo le alcanza para volver respetando la reserva, regresa (con el grano) y vuelve a su lugar después de recargar. No lo hace si ya tiene un carro en camino (contratado, o el asignado al que avisó con `LLENA`), porque ese carro la seguiría hasta su base y se estorbarían.
  7. **Rutas en el tiempo de la cosechadora:** usa las mismas reglas del carro (`docs/equipo/oswaldo/carro.md` §12): compromiso con el plan anterior, y los agentes quietos se suponen en su celda todo el horizonte. Una espera porque la siguiente celda está ocupada es `RESTRICCION R3` (una por espera) y solo es `BLOQUEO` si dura más que el horizonte. En la línea base (1 + 1, directa) se conserva el código de v0.1.
  8. **Carro (en nombre de Oswaldo):** con el tanque lleno ya no rechaza por combustible. En un mapa donde el viaje no alcanza ni con el tanque lleno, rechazar siempre dejaba a la cosechadora llamando para siempre (pasó en F).
  9. **Escenario F:** tanques de 100 L (cosechadora) y 60 L (carro). Con 60 y 40 L, una cosechadora en la esquina lejana no completaba ni una carga más el regreso. Las 80 corridas de F (4 estrategias × 20 seeds) terminan, y cada una tiene al menos 8 restricciones `combustible_reserva` y al menos 115 eventos `RECARGA`.
- **Alternativa considerada:** reintentar con el mismo id; estimar todo el camino; un estado `RECARGANDO`; dejar que el carro rechace siempre que no alcance.
- **Por qué se descartó:** rompe «un cfp por servicio»; con tanques chicos la cosechadora nunca saldría; los consumidores del log lo rechazarían; ciclo infinito de subastas.
- **Limitación conocida:** en F todavía hay unos pocos ticks con un tanque en 0 L (9 en unos 40,000 ticks, al esperar mucho a un carro ya en camino). R11 se cumple (nunca negativo) y queda un aviso en el log de consola.
- **Afecta a:** Oswaldo (regla 8), Ilan (pruebas de integración de D, E y F), Joel (experimentos).

## 2026-11-25 — Terreno realista: la forma del campo entra por Python (trace 2.3)
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos), con base en el KML y las convenciones de Oswaldo (`harvest-simu-visualization/docs/cultivo/`).
- **Decisión:**
  1. El KML de El Pueblito se convierte **en Python** en un mapa de celdas (`config/mapas/el_pueblito.json`). La simulación corre sobre ese mapa y Unity lo recibe en el **trace 2.3** (`tamano_celda_m`, `caminos`, `fuera_de_campo`, `lotes`, `altura_m` y `geo`).
  2. Unity dibuja con `geo.formas` (y reutiliza el código de mallas de `CultivoDesdeKML.cs`), pero no calcula pasadas.
  3. La cuadrícula se gira con el rumbo común de los surcos, así que una fila es una pasada. Las celdas son de 12 m, como en la vista realista.
  4. Los caminos trazados en segmentos se **sueldan** con una tolerancia de 5 m, y cada unión queda en un reporte. Lo que siga suelto es un error del KML.
  5. Reglas nuevas: **R12** (nadie sale del predio) y **R13** (los carros no pisan el cultivo en pie). R13 solo aplica con mapa y `politica.respetar_cultivo`.
  6. La bodega y las bases van en un **patio** junto al camino, no sobre él.
  7. Con mapa, el campo se reparte por lotes completos entre las cosechadoras, y cada lote empieza por la orilla que toca un camino.
  8. El trace es 2.3 solo si hay mapa: A–F siguen siendo 2.2 y dan las mismas métricas.
- **Alternativa considerada:** que Unity calcule las pasadas con `PasadasCultivo.cs`; un rectángulo con el área del predio; caminos rasterizados por área; la bodega sobre el camino.
- **Por qué se descartó:** habría dos fuentes de verdad; se perdería la forma, que es justo lo que se quiere estudiar; un camino de 4 m nunca ocupa la mitad de una celda de 12 m y la red quedaría partida; una máquina estacionada sobre un camino de una celda lo tapa para siempre.
- **Afecta a:** todos. Detalle en `docs/especificacion_terreno.md`.

## 2026-11-26 — M1: despacho aprendido y carro que no encierra a la cosechadora en traslado
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos). La regla 2 toca el carro y la cosechadora (Oswaldo y Emilio): se avisa en el PR.
- **Decisión:**
  1. **M1 entra como `politica.aviso`** (`umbral` por defecto, `qlearning` o `sarsa`). Solo funciona con subasta, porque usa `SOLICITUD_SERVICIO`.
     - La tabla Q se entrena aparte (`tools/entrenar_despacho.py`, seeds 1000 y siguientes) y se versiona en `config/aprendizaje/`.
     - La simulación solo la lee: sin exploración y con el umbral como respaldo en los estados que no conoce.
     - Las estrategias `qlearning` y `sarsa` son `anticipada` con el aviso aprendido. Van en `ESTRATEGIAS_APRENDIDAS`, no en `ESTRATEGIAS`, porque necesitan tabla por escenario.
  2. **El carro no se estaciona en el paso de una cosechadora que se traslada** (`mundo.paso_de`: su destino y los dos siguientes pasos de la ruta que respeta R13).
     - Si no hay otra vecina libre, el carro se hace a un lado o espera donde está.
     - Explorando en G, un carro llegaba temprano mientras la cosechadora rodeaba la arboleda y se quedaba en la única salida sin cultivo. Ella no se llenaba y él solo se mueve después de la transferencia, así que la corrida llegaba a `max_ticks`.
     - Con las estrategias fijas no se había visto, pero el mismo atasco podía pasar con cualquier aviso temprano.
     - A–G dan exactamente las mismas métricas que antes (D, E, F y G comprobados).
  3. **`comparar_contra_base` acepta otra referencia** (`"referencia"` en el JSON del experimento). M1 se compara contra `anticipada`, que es la misma política salvo el aviso.
- **Alternativa considerada:** una tabla única para todos los escenarios; aprender durante las corridas de evaluación; que la cosechadora cruce el cultivo cuando el carro le estorba.
- **Por qué se descartó:**
  - La tabla única mezcla campos donde el aviso importa de forma muy distinta: en D casi nada, en G mucho.
  - Aprender durante la evaluación rompe la reproducibilidad: la seed dejaría de determinar el trace.
  - Cruzar el cultivo rompe el espíritu de R13 por una falla de coordinación.
- **Afecta a:** Oswaldo (`carro._acompanar`), Emilio (`cosechadora.celdas_de_paso`), Ilan (prueba de regresión en `test_terreno_integracion.py`). Detalle en `docs/especificacion_mejoras.md` §M1.

## 2026-11-26 — M1 en Unity: cada decisión del despacho aprendido queda en el log
- **Estado:** DECIDIDO.
- **Quién:** Joel (Datos), con la vista de Unity (Mario Giovanni).
- **Decisión:**
  1. Evento nuevo `DECISION_DESPACHO` (estado, valores Q, acción y origen), solo con `politica.aviso` aprendido.
  2. `config.aprendizaje` guarda qué tabla decidió (ruta y sha256).
  3. Métricas `decisiones_despacho`, `pedidos_tabla`, `pedidos_respaldo` y `cliffs_despacho`.
  4. El servidor lista por escenario las estrategias que puede correr.
  5. Unity muestra la decisión en la placa y en la tarjeta del agente.
- **Alternativa considerada:** meter la decisión en el payload del `SOLICITUD_SERVICIO`; que Unity cargara la tabla y recalculara la decisión.
- **Por qué se descartó:**
  - El payload solo existe cuando se pide, y la mitad de lo que aprende el agente son las veces que decide seguir, además del cliff.
  - Recalcular en Unity rompe la regla de que Unity solo lee el trace (habría dos fuentes de verdad).
- **Afecta a:** Mario Giovanni (Unity: el cargador acepta el evento nuevo; un Unity anterior rechaza los traces de `qlearning` y `sarsa`) e Ilan (pruebas). Detalle en `docs/especificacion_mejoras.md` §M1.

## 2026-11-26 — Hileras: cabeceras, pasadas paralelas a las hileras y vueltas Dubins
- **Estado:** DECIDIDO (fases H0–H3 del plan de hileras y rutas).
- **Decisión:**
  1. **`politica.movimiento`:** `celdas` (por defecto, el de siempre) o `hileras` (requiere mapa). Parámetros nuevos en `config.maquinas`: radio de giro de 7.5 m, 6 km/h cosechando y 5 km/h en la vuelta.
  2. **Cobertura como Fields2Cover** (`mapa/cobertura.py`):
     - cabecera de `k = ceil(2R / s)` celdas en los extremos de las hileras y una celda en las orillas;
     - pasadas = tramos de fila del interior;
     - descomposición boustrophedon en bloques;
     - orden snake o boustrophedon, el de menor costo de vueltas.
     - No se usa la librería: en PyPI solo hay código fuente que exige compilar C++ con GDAL y OR-tools. Se implementan sus pasos sobre la cuadrícula.
  3. **Cabecera primero («abrir el campo»).** Una secuencia que nunca obliga a cruzar cultivo: solo se cosecha cabecera alcanzable por rastrojo o camino. Cada pasada se entra de frente desde una celda de cabecera ya cosechada; la cabecera alrededor de un obstáculo en medio del lote se cosecha cuando las pasadas llegan a ella.
  4. **R14 (`R14_hileras`):** a una pasada se entra de frente, nunca de lado.
  5. **Vueltas:** el cambio de pasada dura lo que la curva de Dubins (`mapa/dubins.py`, Shkel y Lumelsky): 4 ticks para una Ω de 12 m o una U de 24 m.
  6. **Carro con hileras:** no persigue a la cosechadora mientras se traslada. Libra su paso, avanzando por el pasillo si no hay lado libre, y espera. Sin la bandera el carro sigue igual.
- **Resultado en G** (`anticipada_plus`, seed 0):

| | Celdas | Hileras |
|---|---|---|
| Ticks | 1463 | 1803 |
| Ocio | 360 | 397 |
| Entradas de lado fuera de la cabecera | 102 | 0 |
| Pasos sobre cultivo | 23 | 0 |

  Las 4 estrategias terminan sin colisiones. El tiempo sube porque las vueltas y la cabecera ahora cuestan lo que cuestan.
- **Alternativa considerada:** compilar Fields2Cover y llamarlo desde Python; mantener el BFS y solo prohibir entrar de lado; cosechar la cabecera al final.
- **Por qué se descartó:**
  - Compilar Fields2Cover es una dependencia pesada para la simulación y el CI.
  - Prohibir solo la entrada de lado deja atascos y vueltas de radio 0.
  - Dejar la cabecera al final obliga a dar las vueltas sobre cultivo en pie.
- **H4, A\* con rumbo** (`rutas.astar_rumbo_tiempo`): con hileras, los traslados de la cosechadora y del carro dejan el BFS y usan A* sobre (celda, rumbo, tick), con las mismas reservas y el mismo horizonte.
  - Girar 90° cuesta el cuarto de circunferencia a su velocidad. La media vuelta es una vuelta en K de varios ticks: 4 la cosechadora; el carro (R = 6 m, 10 km/h), 0 y 2.
  - En G con `anticipada_plus` pasa de 29 vueltas de 180° en un tick a 0, y termina en 1999 ticks con 454 de ocio.
  - La métrica cuenta como instantánea solo la inversión sin al menos 2 ticks detenida.
- **H7 y H8, con dos arreglos:**
  - **Escenario nuevo `escenario_g_hileras`:** es G con `movimiento = "hileras"`, para el servidor y Unity.
  - **Atasco 1, el carro que espera:** al combinar hileras con despacho anticipado aparecieron atascos. El carro que espera a la cosechadora en traslado ahora se aparta de **toda** su ruta, no solo de los dos pasos siguientes, y suelta su plan viejo para no dejar reservas fantasma.
  - **Atasco 2, el giro en el sitio:** ahora acumula su avance (`rutas.progreso_de_giro`). Antes, al replanear cada tick, la máquina empezaba el giro desde cero y nunca salía.
  - **Sin la bandera nada cambia.** Resultados en `docs/resultados_hileras.md`.
- **H6, descarga en marcha** (`politica.descarga_en_marcha`, requiere hileras; solo actúa con subasta):
  - el carro hace una cita en el lateral de rastrojo de la pasada actual o de la siguiente;
  - con la cosechadora a su altura pasa a `RECIBIENDO_EN_MARCHA` y avanzan en paralelo mientras ella le pasa grano;
  - al vaciarse ella, o llenarse el carro, se envía `TRANSFERENCIA_TERMINADA` como siempre.
  - **Alternativa descartada:** carro detrás de la cosechadora en la misma fila. Así no está a su lado para recibir, y el sinfín de una cosechadora real descarga hacia un costado.

