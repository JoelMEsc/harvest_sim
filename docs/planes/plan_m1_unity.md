# Plan: M1 (despacho aprendido) completo en Unity

> **Copia versionada (27 de noviembre de 2026). Estado: completo** (harvest_sim #32 y #33; Unity #6).

26 de noviembre de 2026. Bitácora: `progreso_terreno.md`.

## Objetivo

Que en Unity se pueda correr y ver una corrida con `qlearning` o `sarsa`:
- elegir la estrategia;
- ver cuándo y por qué la cosechadora pidió el carro (estado, valores Q, acción y origen de la decisión);
- leer las métricas del aprendizaje al final.

Unity sigue sin decidir nada: solo lee el trace.

## Qué hay hoy y qué falta

| Pieza | Hoy | Falta |
|---|---|---|
| Estrategias en Python | `qlearning` y `sarsa` en `ESTRATEGIAS_APRENDIDAS`; tablas de D y G | Nada |
| Trace | Solo `config.politica.aviso`; la decisión no queda registrada | Un evento por decisión y la procedencia de la tabla |
| Servidor | `/api/escenarios` lista solo las 4 estrategias | Listar las aprendidas en los escenarios que tienen tabla |
| Exportar traces | `exportar_traces_unity.py` acepta solo las 4 | Aceptar las aprendidas |
| Unity | El selector tiene 4 opciones fijas; el cargador rechaza eventos que no conoce | Selector desde el servidor, el evento nuevo, la placa, las tarjetas, las métricas y la leyenda |

## Diseño

### Trace (Python, `harvest_sim`)

- **Evento nuevo `DECISION_DESPACHO`** (desde 2.2), solo cuando `politica.aviso` es `qlearning` o `sarsa`. Uno por decisión:
  - `agente`;
  - `estado`: `{tramo, carros_libres, distancia, otra_pidio}`;
  - `q`: `{seguir, pedir}` (null si la tabla no conoce el estado);
  - `accion`: `seguir` | `pedir`;
  - `origen`: `tabla` | `umbral` (respaldo) | `forzada` (cliff).
- **Por qué un evento y no el payload del cfp:** también hay que ver las decisiones de «seguir» (son la mitad de lo que aprende) y el cliff. Con ~5 decisiones por ciclo, el trace de G crece poco.
- **`config.aprendizaje`** cuando aplica: `{algoritmo, tabla, sha256, episodios, estados}`. Sirve para saber qué tabla produjo la corrida.
- **Métricas** (solo con aviso aprendido): `decisiones_despacho`, `pedidos_tabla`, `pedidos_respaldo`, `cliffs`.
- **El validador** acepta el evento y revisa sus campos.
- **A–G con las 4 estrategias no cambian:** el evento solo existe con aviso aprendido, así que la regresión sigue igual.

### Servidor y exportación

- `/api/escenarios` agrega `qlearning` y `sarsa` a `estrategias` y, por escenario, `estrategias` = las que puede correr (las aprendidas solo si existe su tabla).
- `exportar_traces_unity.py` acepta las 6 estrategias.

### Unity (`harvest-simu-visualization`, rama nueva desde `dev`)

1. **`TraceLoader`:** acepta `DECISION_DESPACHO` (requiere 2.2+) y valida agente, campos, acción y origen.
2. **`PlaybackState.Decisions`:** la última decisión de cada cosechadora. Se mantiene entre ticks y se reinicia al retroceder, igual que el resto del estado.
3. **`TickCues.Decisions`:** las decisiones de este tick, para la placa.
4. **Placa del agente:** en el tick en que decide «pedir», muestra «Q pide carro» (o «umbral» / «tolva llena» según el origen), igual que la oferta de la subasta.
5. **Tarjeta del agente:** una línea con la última decisión, por ejemplo «Q: tramo 2 · 1 libre · seguir −312 / pedir −298 → pide».
6. **Selector de estrategia:** se llena con la lista del servidor (`SetStrategies`). El editor que arma la escena (`HarvestHudBuilder`) agrega `qlearning` y `sarsa` a las opciones por defecto.
7. **Métricas y leyenda:** filas para las métricas nuevas y una sección «Despacho aprendido» en la leyenda.
8. **Traces de ejemplo** en `Assets/Data/Traces/mejoras/`: D y G con `anticipada`, `qlearning` y `sarsa` (seed 0).

## Pruebas

- **Python:**
  - el evento aparece solo con aviso aprendido;
  - una decisión por tramo y su origen;
  - el validador lo acepta y rechaza campos malos;
  - A–G sin cambios (`test_regresion`);
  - el servidor lista las estrategias por escenario;
  - la exportación acepta las aprendidas.
- **Unity, EditMode:**
  - el cargador acepta el trace de M1 y rechaza un evento mal formado;
  - la última decisión por cosechadora, también al retroceder;
  - las señales del tick (placa);
  - el texto de la tarjeta;
  - las métricas nuevas en el HUD;
  - las opciones del selector desde una respuesta del servidor;
  - las 55 pruebas actuales siguen en verde.
- **Captura en modo batch** de G con `sarsa` para revisar la placa y las tarjetas.

## Riesgos

- **La escena guarda las opciones del selector.** Si `HarvestHudBuilder` no se vuelve a correr, la escena se queda con 4 opciones. Mitigación: el selector se llena en tiempo de ejecución desde el servidor y, sin servidor, desde la lista por defecto del código.
- **Traces más grandes.** G con SARSA agrega ~300 eventos; se medirá.
- **Unity anterior.** Un Unity sin el cambio rechaza estos traces («tipo de evento no soportado»). Se documenta; solo afecta a las estrategias aprendidas.

## Orden y criterio de listo

1. Python: evento, config, métricas, validador, servidor y exportación, con pruebas. PR a `development`, CI y merge.
2. Exportar los traces de ejemplo a Unity.
3. Unity: cargador, estado, señales, placa, tarjeta, selector, métricas y leyenda, con pruebas EditMode y captura. PR a `dev` y merge.
4. Documentos: `docs/especificacion_mejoras.md` (evento y config), `docs/resultados_mejoras.md` (Unity), `docs/decisiones.md`, tabla del plan del equipo, README de los traces y bitácora.

**Listo cuando:** en Unity se elige `sarsa` para G, se reproduce la corrida, se ve en la placa cuándo pide y en la tarjeta por qué, y las métricas del aprendizaje aparecen al final; todo con pruebas en verde y registrado.
