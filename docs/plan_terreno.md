# Plan: terreno realista (forma real del campo, caminos y relieve)

> Plan de trabajo para simular y ver el cultivo real de **El Pueblito, Teocaltiche, Jalisco** (KML en `harvest-simu-visualization/docs/cultivo/`).
> El contrato técnico (formato del mapa, trace 2.3, reglas R12 y R13, relieve) está en [`especificacion_terreno.md`](especificacion_terreno.md); las decisiones, en [`decisiones.md`](decisiones.md).

## Estado

| Paso | Qué | Estado |
|---|---|---|
| P0 | Especificación y decisión | Hecho (PR #20) |
| P1 | Formato 2.3 y trace de ejemplo | Hecho (PR #20) |
| P2 | Mapa de El Pueblito desde el KML | Hecho (PR #21) |
| P3 | Mundo con mapa, R12, R13 y escenario G | Hecho (PR #22) |
| P4 | Relieve (DEM Copernicus) y consumo por pendiente | Hecho (PR #24) |
| P5 | Agentes que respetan R13 y corridas de G | Hecho (PR #25) |
| P6 | Unity: trace 2.3, forma real y relieve | Hecho (harvest-simu-visualization PR #5, EditMode 55/55) |
| P7 | Pruebas, experimentos y documentación | Hecho (`docs/resultados_terreno.md`) |
| M1 | Q-learning y SARSA para el despacho | Hecho (`docs/resultados_mejoras.md`): SARSA −37 % de ocio en G; en Unity con placa y tarjeta por decisión (harvest-simu-visualization PR #6) |
| H0–H8 | **Hileras y rutas de la industria** (antes de M2): cabeceras, pasadas paralelas a las hileras, orden snake/boustrophedon, vueltas Dubins con radio de giro, A* con rumbo en lugar de BFS, descarga en marcha y Unity sobre la trayectoria (referencia: Fields2Cover y AgOpenGPS). Bandera `politica.movimiento` | En curso. H0 hecho (PR #34): línea base de G, 102 entradas de lado, 23 pasos sobre cultivo y 12 vueltas de 180° en un tick. H1–H3 hechos (PR #35): con `hileras`, 0 entradas de lado fuera de la cabecera y 0 pasos sobre cultivo. H4 hecho: A* con rumbo, 0 vueltas instantáneas. Siguen H5 (trace 2.4), H6 (descarga en marcha), H7 (Unity) y H8 (experimentos) |
| M2–M12 | Mejoras siguientes, en orden | Pendiente |

## Objetivo y criterios de aceptación

Simular y ver la cosecha del **cultivo real de El Pueblito** con su forma, sus caminos, sus obstáculos y su relieve, sin romper nada de lo anterior.

| # | Criterio | Cómo se comprueba |
|---|---|---|
| C1 | Los 3 lotes, la arboleda y los caminos del KML se simulan en una cuadrícula a escala (metros), orientada con los surcos | Escenario G: el área cosechable simulada coincide con el área del KML con un error menor al 5 % (efecto de borde de las celdas) |
| C2 | Ninguna máquina entra a celdas fuera de campo ni a obstáculos; las máquinas cruzan entre lotes solo por caminos o por campo | Pruebas de integración en G (R10 y la regla nueva R12) |
| C2b | Los caminos del KML quedan conectados aunque estén trazados en segmentos, y la red completa llega a la bodega y a cada lote | Prueba de P2: después de soldar, la red de caminos es una sola componente conexa; cada unión queda en el reporte |
| C2c | Los carros y el camión **nunca pisan cultivo en pie**: solo andan por caminos y por campo ya cosechado (rastrojo) | Prueba de integración en G (regla nueva R13): en ningún tick un carro o camión ocupa una celda de campo que todavía no aparece en `CELDA_COSECHADA` |
| C3 | El relieve real (DEM Copernicus GLO-30) está en el trace y en Unity | `mundo.altura_m` en el trace; terreno de Unity con la misma altura en cada celda (±0.5 m) |
| C4 | La pendiente afecta el consumo, documentado y desactivado por defecto | Con el factor en 0, A–F siguen dando las métricas de v0.1 (`test_regresion`); con el factor activo, G consume más subiendo que bajando |
| C5 | Unity dibuja la forma real con bordes suaves, desde el trace y sin calcular nada | Las mallas de lotes, caminos y arboleda salen de `mundo.geo`; los scripts que calculan pasadas no se usan para la lógica |
| C6 | Nada se rompe | 650 pruebas más las nuevas; A–F igual; Unity EditMode y PlayMode en verde |

## Pasos en orden

### P0. Acuerdo del contrato

1. `docs/especificacion_terreno.md`:
   - trace 2.3;
   - tipos de celda, R12 y R13 (la tabla de quién pisa qué);
   - convenciones del KML (las de `docs/cultivo/` más `bodega` y `base_*`) y la soldadura de caminos (tolerancia, ancho y qué pasa si algo sigue suelto);
   - el formato de `config/mapas/*.json`;
   - el relieve y el factor de pendiente.
2. Una entrada en `docs/decisiones.md`: por qué la forma entra por Python y no por Unity.

**Listo cuando:** el equipo está de acuerdo con el contrato. Desde ahí todos pueden trabajar en paralelo.

### P1. Formato 2.3

`formato.py` (versión 2.3, campos nuevos y regla `R13_cultivo_en_pie`), validador (tipos, rangos, que las celdas de `fuera_de_campo` y `caminos` estén en el mapa, matriz de alturas del tamaño del mapa) y `campo.py` (campo cosechable con la regla 2.3). Agrega un trace de ejemplo 2.3, escrito a mano con un campo en L y un camino, como fixture para Unity.

**Listo cuando:** 2.1, 2.2 y 2.3 validan. El ejemplo 2.3 queda publicado.

### P2. KML a mapa

1. Lector de KML que conserva la clasificación por nombre de `CultivoDesdeKML`.
2. UTM 13N, rumbo común, soldadura de caminos con su reporte, rasterizado por fracción de área (Shapely) y salida `config/mapas/el_pueblito.json`.
3. El algoritmo de pasadas de `PasadasCultivo.cs` en Python, para comparar con la serpentina.
4. Pruebas:
   - el área de las celdas de campo está dentro del ±5 % del área de los lotes;
   - la arboleda queda como obstáculo;
   - los caminos quedan transitables;
   - con el KML actual, la soldadura une los 8 segmentos en **una sola red** que toca los 3 lotes y la bodega;
   - un KML de prueba con un hueco de 20 m hace fallar al script con el nombre del camino y la distancia;
   - con una tolerancia de 0 m, el KML actual queda partido (la prueba demuestra que la soldadura sí hace algo);
   - el rumbo de cada guía coincide con el que calcula `PasadasCultivo.cs`.

**Listo cuando:** el mapa se genera solo desde el KML.

### P3. Mundo con mapa

Tipos de celda, bodega y bases desde el mapa, R12, `bloqueadas_para(agent_id)` con R13, validación de alcanzabilidad, `descripcion()` con los campos 2.3 y escenario G.

Pruebas: `bloqueadas_para` de un carro incluye el campo sin cosechar y deja de incluirlo cuando se cosecha; el de la cosechadora no lo incluye; con `respetar_cultivo: false` nada cambia.

**Listo cuando:** G carga y se puede crear el mundo; A–F siguen iguales.

### P4. Relieve

1. `dem_a_alturas.py`. Requiere el visto bueno para descargar la ventana del DEM, de unos cientos de KB.
2. `altura_m` en el mapa y en la descripción del mundo.
3. Factor de pendiente en `actualizar_combustible`.
4. Pruebas:
   - las alturas coinciden con el DEM en 3 puntos de control;
   - con factor 0 el consumo no cambia;
   - con factor > 0, subir cuesta más que bajar.

**Listo cuando:** C3 y C4 del lado de Python.

### P5. Agentes en el campo real

1. Correr G con las 4 estrategias y 20 seeds y revisar:
   - que termine;
   - 0 colisiones y 0 BLOQUEO;
   - que nadie entre a `fuera_de_campo`;
   - que **ningún carro ni camión pise cultivo en pie** (R13);
   - que cada franja empiece por la orilla del camino y que el carro pueda llegar a la primera pasada;
   - los saltos entre lotes por caminos.
2. Corregir lo que salga.

   Riesgo conocido de la segunda entrega: un agente que espera en un paso único puede bloquear a todos, y en G los caminos son pasos angostos. Con R13 hay todavía menos espacio libre al inicio, porque solo hay caminos. Si aparece, la regla es que **ninguna máquina espera sobre un camino de una sola celda**; se detiene antes.
3. Medir el tiempo de corrida. Si pasa de 2 min, se perfila `bfs_tiempo`.

**Listo cuando:** C1, C2 y C2c con las 4 estrategias.

### P6. Unity

1. Leer 2.3 con el ejemplo de P1 (puede empezar en cuanto exista).
2. Terrain desde el heightmap; celdas, maíz y máquinas sobre la altura.
3. Mallas de `geo.formas` con el código de `CultivoDesdeKML`.
4. Atribución de Copernicus en el HUD.
5. Traces reales de G en `Assets/Data/Traces/` (generados con `tools/exportar_traces_unity.py`).
6. Pruebas EditMode:
   - un trace 2.3 carga;
   - la altura de una celda en Unity es igual a `altura_m` (±0.5 m);
   - ninguna celda de `fuera_de_campo` tiene maíz.

**Listo cuando:** C3 y C5. Se ve El Pueblito con su relieve.

### P7. Pruebas, experimentos y documentación

1. Integración en G (C1, C2, C2b y C2c) y regresión A–F.
2. Experimento principal en G (4 estrategias × 20 seeds), un barrido del factor de pendiente y la comparación de G con R13 contra G sin R13: cuánto más tardan los carros por no pisar el cultivo y cuánto suelo se deja de compactar.
3. Agregar los resultados a `docs/resultados_entrega2.md` o a uno nuevo de la entrega final.
4. Actualizar el README y la autoevaluación.

**Listo cuando:** C6. Todo entra a `development` por PR y a `main` en la entrega.

```
P0 ──► P1 ──► P6 (Unity puede empezar con el ejemplo 2.3)
  ├──► P2 ──► P3 ──► P5 ──► P7 ──► M1 … M12 (mejoras, sección 4b)
  └──────────► P4 ──┘
```

## Mejoras (van DESPUÉS del terreno y los caminos)

> **Regla de orden:** ninguna mejora empieza antes de que P7 esté terminado. P0–P7 ya es la mejora «Terreno realista». Todas las demás usan el escenario G (El Pueblito) como caso principal, porque es el único con datos reales.

**Idea general:** pasar de un simulador académico a una herramienta que, con datos reales del campo, le diga al dueño cuánto tarda la cosecha, cuánto cuesta y qué conviene hacer. Al mismo tiempo cubre los temas del curso: agentes, aprendizaje, teoría de juegos y visualización.

**Reglas para todas las mejoras:**
- Python sigue siendo la única fuente de verdad: Unity y el dashboard solo leen el trace o la API.
- Todo dato externo lleva su fuente y su licencia.
- Cada mejora nueva queda **desactivada por defecto**, para que A–F sigan pasando `test_regresion`.
- Una rama y un PR por mejora, con sus pruebas.

Estas son las mejoras, en el orden en que se implementan:

### M1. Q-learning para el despacho

- **Qué:** un agente aprende cuándo pedir el carro, en lugar de usar el umbral fijo.
- **Diseño** (rúbrica del curso: cliff, estados, acciones, recompensas y creatividad):

  | Elemento | Definición |
  |---|---|
  | Estado | Nivel de la tolva (en tramos), carros libres, distancia del carro más cercano (en tramos) y si la otra cosechadora ya pidió carro |
  | Acciones | Pedir carro o seguir cosechando |
  | Recompensa | −1 por tick de ocio, −costo de cada solicitud |
  | Cliff (castigo grande) | La tolva se llena sin carro en camino |

- **Cómo:**
  - Q-learning tabular escrito por el equipo (es lo que pide la materia), con SARSA como comparación.
  - Se entrena con semillas 1000 y siguientes y se evalúa con las semillas 0 a 19, en D y G.
  - Entra como una estrategia nueva, `qlearning`, en `ESTRATEGIAS`.
- **Listo cuando:** comparación pareada con IC 95 % contra el umbral fijo y la subasta, con curva de aprendizaje y tabla aprendida. Responde la pregunta 3 de la retro.

### M2. Equilibrio de Nash (teoría de juegos)

- **Qué:** la competencia entre dos carros por un servicio modelada como un juego de «compartir contra acaparar».
- **Cómo:**
  - los pagos de la matriz salen de corridas de la simulación;
  - los equilibrios se calculan con `nashpy`;
  - se compara el equilibrio con el óptimo social (precio de la anarquía).
- **Listo cuando:** la matriz, los equilibrios y su explicación están en los resultados.

### M3. Fallas de comunicación visibles

- **Qué:** que se vean los mensajes retrasados, perdidos o rechazados.
- **Cómo:**
  - si la simulación pierde mensajes, debe agregarse un evento `MENSAJE_PERDIDO` en el trace (opcional en 2.3);
  - Unity dibuja la línea del mensaje en rojo o punteada y un ícono sobre el agente;
  - el HUD pone marcas en la línea de tiempo;
  - el dashboard cuenta las fallas por tipo.
- **Listo cuando:** en F y en G con incertidumbre se ve cada falla, con su prueba en EditMode.

### M4. Variables en tiempo real por WebSockets

- **Qué:** cambiar parámetros mientras corre la simulación (velocidad, umbral, número de fallas, pausa) y ver el efecto al momento.
- **Cómo:**
  - ruta WebSocket en el servidor FastAPI;
  - la simulación avanza por ticks y aplica los cambios al inicio de cada tick;
  - cada cambio queda en el trace como un evento `CAMBIO_PARAMETRO`, para que la corrida se pueda repetir.
- **Listo cuando:** Unity y el dashboard cambian un parámetro en vivo y el trace resultante valida.

### M5. Logs accesibles para análisis

- **Qué:** sacar los traces del formato interno.
- **Cómo:** exportarlos a CSV y Parquet con una tabla por tipo de evento (agentes, mensajes, depósitos, restricciones), más un notebook de ejemplo y una ruta de la API para filtrar por corrida, agente y rango de ticks.
- **Listo cuando:** cualquiera del equipo puede responder una pregunta (por ejemplo, el ocio de una cosechadora entre los ticks 100 y 200) sin leer el JSON.

### M6. Dashboard web por túnel

- **Qué:** abrir el dashboard y el servidor desde cualquier lugar, sin desplegar un servidor.
- **Cómo:** `scripts/tunel.sh` con Cloudflare Tunnel o ngrok, con acceso protegido por contraseña o token, y la URL que se comparte.
- **Listo cuando:** el dashboard y la simulación en vivo abren desde otra red. Antes de publicarlo hay que pedir permiso.

### M7. Clima

- **Qué:** usar el clima histórico de Teocaltiche para saber qué días se puede cosechar y cuánto se pierde por retraso.
- **Cómo:**
  - clima diario de Open-Meteo, guardado en caché;
  - un día deja de ser apto si llueve más de un umbral o el suelo sigue húmedo;
  - pérdidas por desgrane y por humedad, con un % por día de retraso y su fuente;
  - simulación de varios días: los días no aptos no se trabaja.
- **Listo cuando:** el resultado dice cuántos días reales toma la cosecha y cuánto se pierde, para varios años.

### M8. Análisis financiero integral

- **Qué:** cuánto cuesta y cuánto deja la cosecha, en pesos.
- **Costos que incluye:**
  - diésel;
  - horas de operador;
  - renta o depreciación de cada máquina;
  - mantenimiento;
  - fletes al acopio;
  - pérdidas de grano (por retraso, humedad o desgrane, de M7).
- **Ingresos:** toneladas por precio de garantía o de mercado, con su fuente.
- **Métricas:** costo por hectárea, costo por tonelada, ganancia, margen, punto de equilibrio y comparación entre comprar o rentar otro carro o camión.
- **Listo cuando:** cada estrategia y cada flota del experimento tiene su ganancia con IC 95 %, y cada precio tiene su fuente en un YAML.

### M9. Análisis desde imagen satelital

- **Qué:** estimar área, vigor y rendimiento del predio sin medirlo a mano.
- **Cómo:**
  - imágenes Sentinel-2 abiertas del predio de El Pueblito;
  - NDVI por zona para un mapa de vigor, que alimenta el rendimiento por celda (`mundo.rendimiento`);
  - con eso se proyectan tiempo, costo y ganancia, usando M8.
- **Listo cuando:** el escenario G puede usar el rendimiento estimado por satélite, con su fuente, y el reporte muestra el mapa.

### M10. Visión computacional

- **Qué:** detectar en las imágenes los límites del lote, los obstáculos (árboles, construcciones) y las zonas con poca planta.
- **Cómo:** segmentación sobre la imagen satelital con un modelo abierto preentrenado. No se entrena uno desde cero.
- **Para qué:** compararla con el trazo del KML y proponer correcciones.
- **Listo cuando:** se mide la coincidencia (IoU) entre lo detectado y el KML, y las diferencias quedan en una figura.

### M11. Reportes financieros con RAG

- **Qué:** preguntar en lenguaje natural («¿cuánto me ahorra un segundo carro?») y recibir respuestas que citan los resultados reales.
- **Cómo:** índice con los resultados de M8, las métricas de las corridas y la documentación; un modelo local (por ejemplo, con Ollama) que responde citando la fuente; si no encuentra el dato, lo dice.
- **Listo cuando:** contesta 10 preguntas de prueba con la cifra correcta y su cita.

### M12. Rust para eficiencia

- **Qué:** hacer más rápidas las partes más pesadas.
- **Cómo:**
  - primero se mide con un perfilador; lo esperado es que lo más pesado sea `bfs_tiempo` en G;
  - solo eso se pasa a Rust con PyO3 y maturin;
  - se conserva la versión en Python y una prueba exige que las dos den el mismo resultado.
- **Listo cuando:** G corre al menos 3 veces más rápido, con la medición antes y después en los resultados.

**Si falta tiempo**, el orden de prioridad es: M1 → M2 → M8 → M3 → M4 → M7 → M5 → M6 → M9 → M10 → M11 → M12. M1 y M2 son lo que más pide la materia.

## Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | La simulación se vuelve lenta en G (~75 × 58 celdas) | Medir en P5; perfilar `bfs_tiempo`; si hace falta, celdas de 15 m o reservas solo cerca del agente |
| R2 | Los caminos del KML no conectan los lotes, o tienen huecos por el trazo a mano | Los huecos chicos (hoy de hasta 3.9 m) los suelda el script, con reporte. Lo que sigue suelto después de soldar hace fallar al script y se corrige **en el KML** (Google Earth), como dice el flujo de actualización del KML |
| R2b | La soldadura une dos caminos que en la realidad no se tocan (por ejemplo, separados por una cerca) | La tolerancia es chica (5 m) y cada unión sale en el reporte para revisarla; si una está mal, se baja la tolerancia o se corrige el KML |
| R3 | Esperas mutuas en caminos de una celda | La regla de P5 y una prueba específica |
| R4 | El rumbo común no sirve si un lote difiere mucho | Hoy la diferencia es ≤ 5.1°. Si aparece un lote muy distinto, una cuadrícula por lote, como escenarios separados |
| R5 | Unity se rompe con 2.3 | 2.3 solo agrega campos y `TraceLoader` acepta las tres versiones; el fixture de P1 permite probar antes de la simulación |
| R6 | Trabajo repetido entre los scripts de C# de Oswaldo y el módulo de Python | Lo dice P0: la lógica va en Python y en C# solo la malla; se acuerda antes de empezar |
| R7 | El DEM de 30 m es grueso para celdas de 12 m | Se interpola bilinealmente y se documenta. La forma general del relieve es correcta, aunque no lo sean las zanjas chicas |
| R8 | Con R13, al inicio solo hay caminos: un carro puede no tener por dónde llegar a una cosechadora, o los carros se estorban en los caminos | Empezar cada franja por la orilla del camino; rechazo `sin_ruta` en la subasta; medir en P5 con 20 seeds. Si los caminos no alcanzan, la cosechadora abre primero las cabeceras |
| R9 | Recalcular lo transitable cada tick hace más lenta la simulación | Las celdas bloqueadas por R13 solo disminuyen (cada cosecha libera una), así que el mundo mantiene el conjunto de forma incremental y no lo recalcula desde cero |

## Preguntas para el equipo

1. **¿Ancho de celda de 12 m o de 9 m?** 12 m es lo que ya usa la vista y lo que rinde mejor; 9 m equivale a un cabezal de 12 hileras, más común en predios del tamaño de El Pueblito. Recomendación: 12 m ahora y 9 m como experimento si el tiempo de corrida lo permite.
2. **¿Dónde están la bodega y las bases en El Pueblito?** Recomendación: agregarlas como puntos al KML.
3. **¿El escenario G reemplaza a los inventados en la entrega final?** Recomendación: se agrega G y se conservan A–F (la regresión y las comparaciones dependen de ellos).
4. **¿Los scripts de `docs/cultivo/scripts` se integran en Unity?** Recomendación: solo el código de mallas (P6); la lógica de pasadas queda en Python.
