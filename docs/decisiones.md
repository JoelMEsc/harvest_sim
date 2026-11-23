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
