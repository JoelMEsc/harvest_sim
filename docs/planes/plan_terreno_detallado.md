# Plan: terreno realista en harvest_sim (forma real del campo, caminos y relieve)

> **Copia versionada (27 de noviembre de 2026).** Versión completa del plan de terreno, con el estado inicial y las decisiones de diseño. La tabla de estado del equipo está en `docs/plan_terreno.md`. **Estado:** P0–P7 y M1 hechos; M2–M12 pendientes (ver `docs/estado_y_pendientes.md`).

> Documento personal de Joel, fuera de los repos. Sin fechas (las maneja el equipo).
> Repos:
> - `JoelMEsc/harvest_sim`: `main` = `development` = `v0.2-entrega2`; no ha cambiado desde la segunda entrega.
> - `GioMax102/harvest-simu-visualization`: `dev` en `41a75ce`.

## 1. Estado actual (revisado)

**harvest_sim (Python):**
- **Mundo:** una cuadrícula rectangular en unidades abstractas.
  - La fila 0 es de servicio: bodega en (0, 0) y bases.
  - Las filas 1 y siguientes son campo, repartido en franjas.
  - Hay obstáculos.
- **Rutas:** reservas en el tiempo.
- **Coordinación:** subasta y combustible.
- **Formato:** trace 2.2.
- **Escenarios:** A–F, inventados.
- **No tiene:**
  - escala en metros;
  - forma real del campo;
  - caminos;
  - relieve.

**Unity (`dev`):**
- **PR #4 «vista realista» (Oswaldo), ya integrado:**
  - mundo 3D a escala, con **1 celda = 12 m** (una pasada de cabezal maicero);
  - texturas CC0 de Poly Haven, maíz seco instanciado con corte progresivo, cielo HDRI, silos y gasolineras;
  - HUD completo.
  - `FieldGrid` **ya lee** `mundo.tamano_celda_m` y `mundo.fuera_de_campo`, «previstos para el trace 2.3, cuando llegue la forma real del campo».
  - El terreno es **plano**.
- **Commit `41a75ce` (Oswaldo):** `docs/cultivo/` con el KML del cultivo real de **El Pueblito, Teocaltiche, Jalisco**, sus convenciones de nombres y 3 scripts de C# (`CultivoDesdeKML`, `PasadasCultivo` y `ElementoCultivo`). Esos scripts **calculan las pasadas dentro de Unity** y nunca se han compilado.

**El KML (medido):**

| Elemento | Medida |
|---|---|
| Lote A | 5.35 ha |
| Lote B | 7.21 ha |
| Lote C | 14.39 ha |
| Total | ≈27 ha, en una zona de 853 × 647 m |
| Arboleda dentro del lote C | 0.64 ha |
| Otros obstáculos | 1 obstáculo chico |
| Caminos de terracería | 6 caminos y 2 líneas sin nombre, **segmentados**: entre los extremos quedan huecos de 0 a 3.9 m (el mayor, entre `camino_norte_este` y `camino_norte`), y los extremos quedan a 0.2–8 m de algún lote |
| Surcos | Una guía por lote, con rumbos de 57.5° (A), 55.5° (B) y 48.9° (C) |

Teocaltiche está en Los Altos de Jalisco: **el relieve sí importa**, a diferencia de una planicie de riego.

**El problema de fondo.** Si Unity calcula las pasadas a partir del KML, habría **dos fuentes de verdad**: la simulación en Python decide una cosa y Unity dibuja otra. Eso rompe el contrato del proyecto («Python es la única fuente de verdad; Unity solo reproduce el trace»), que el propio PR #4 respeta. La forma real tiene que entrar **por Python** y llegar a Unity **en el trace 2.3**.

## 2. Objetivo y criterios de aceptación

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

## 3. Decisiones de diseño

1. **El KML es la fuente y el formato de Oswaldo es el estándar.** Se respetan sus convenciones de nombres (`cultivo`/`lote`, `camino`/`brecha`, `obstaculo`, `surco`/`guia`, `rumbo=`). Se agregan dos convenciones nuevas para la logística:
   - un punto `bodega` (donde se descarga el grano);
   - puntos `base_*` (donde se estacionan las máquinas).

   Si faltan, se toma el punto de camino más cercano a la entrada del lote C.
2. **Python convierte el KML en el mapa de la simulación** con `tools/kml_a_mapa.py`:
   - **Proyección:** UTM 13N (EPSG:32613) con `pyproj`, en lugar de la equirectangular local. Así coincide con el DEM.
   - **Rotación:** la cuadrícula se gira con el **rumbo común de los surcos**, que es el promedio ponderado por área de las tres guías (≈52.4°). Las celdas quedan alineadas con los surcos; el error de orientación por lote es ≤ 5.1° (lote A).
   - **Tipos de celda:** `campo` (cosechable), `camino` (transitable, no cosechable), `obstaculo` y `fuera_de_campo` (ni cosechable ni transitable). Una celda es campo si al menos el 50 % de su área cae en un lote y no toca un obstáculo con su margen.
   - **Salida:** `config/mapas/el_pueblito.json` (celdas por tipo, geometría y metadatos) y el escenario `config/escenario_g.json`, que lo referencia con `"mapa": "mapas/el_pueblito.json"`.
   - El algoritmo de rumbo y pasadas de `PasadasCultivo.cs` **se porta a Python** como referencia y validación, porque la serpentina por franjas de la simulación ya es el plan de pasadas. Las ideas de Oswaldo (guía, rumbo manual y automático, zonas) se conservan en el módulo y en sus pruebas.
   - **Caminos segmentados (no hace falta que estén conectados al milímetro en el KML).** Antes de pasarlos a celdas, el script los **suelda**:
     1. Un extremo de camino que queda a menos de `tolerancia_union_m` de otro camino se une al punto más cercano de ese camino. El valor es 5 m: un poco más que el ancho del camino (4 m) y cubre todos los huecos actuales, que son de hasta 3.9 m.
     2. Un extremo que queda a menos de esa tolerancia de un lote se une a la orilla del lote: es su entrada.
     3. El script **imprime cada unión** (qué camino, con cuál, cuántos metros) para revisarla.
     4. Después se pasan a celdas con su ancho (`ancho_camino_m`, 4 m por defecto). Con celdas de 12 m, los huecos chicos que quedaran desaparecen solos.
     5. Al final se valida que **la red de caminos sea una sola pieza** y que toque a la bodega y a cada lote. Si algo sigue suelto (un hueco de 20 m, por ejemplo), el script falla con el nombre del camino y la distancia: eso sí es un error de trazo y **se corrige en el KML**.

     Los dos valores van en `config/mapas/el_pueblito.yaml`, la configuración del convertidor; no están fijos en el código.
3. **Trace 2.3 (solo agrega a 2.2; todo es opcional):**

   | Campo | Qué es |
   |---|---|
   | `mundo.tamano_celda_m` | Metros por celda (12 por defecto en Unity) |
   | `mundo.fuera_de_campo` | Lista de `[x, y]` |
   | `mundo.caminos` | Lista de `[x, y]`, transitables y no cosechables |
   | `mundo.altura_m` | Matriz alto × ancho en metros (relieve) |
   | `mundo.geo` | `epsg`, `origen_utm` (esquina de la celda (0, 0)), `rumbo_grados`, `atribucion` y `formas` (`lotes`, `obstaculos` y `caminos` en metros locales de la cuadrícula). Unity dibuja los bordes reales con esto |

   - Con 2.3, el campo cosechable es todo **menos** obstáculos, `fuera_de_campo`, `caminos`, bodega y bases.
   - Sin esos campos (2.1 y 2.2), sigue la regla actual: y ≥ 1. Así A–F no cambian.
4. **Mundo con tipos de celda:**
   - la bodega y las bases dejan de estar fijas en la fila 0 cuando el mapa las da (`mapa.bodega`, `mapa.bases`);
   - `bloqueadas_fijas` incluye `fuera_de_campo` (regla **R12**, nueva: nadie sale del predio);
   - `franjas()` y `camino()` funcionan sobre el campo irregular, porque ya saltan obstáculos con `YENDO_A_CAMPO`;
   - validación al cargar: todo el campo es alcanzable desde la bodega por campo o camino.
5. **Por dónde puede pasar cada máquina (regla R13: no se pisa el cultivo en pie).** En el campo real los carros no cruzan el maíz sin cosechar: lo tumban y compactan el suelo. Lo transitable depende del tipo de celda **y de si ya se cosechó**:

   | Celda | Cosechadora | Carro recolector y camión |
   |---|---|---|
   | Camino | Sí | Sí |
   | Campo ya cosechado (rastrojo) | Sí | Sí |
   | Campo sin cosechar | Solo cosechándolo, en el orden de su camino | **No** |
   | Obstáculo o fuera de campo | No | No |
   | Bodega y bases | Como hoy (la bodega sigue prohibida para la cosechadora, R9) | Sí |

   - **Cómo se implementa sin algoritmos nuevos.** El mundo ya sabe qué celdas están cosechadas. Se agrega `mundo.bloqueadas_para(agent_id)`, que devuelve las celdas fijas (R9, R10, R12) más, para carros y camiones, las de campo todavía sin cosechar. Las rutas que ya existen (`bfs`, `bfs_tiempo`, `estimar_costo`) reciben ese conjunto en lugar de `bloqueadas_fijas`. Como la cosecha avanza, el conjunto se recalcula cada tick: lo transitable crece conforme hay más rastrojo.
   - **Dónde se estaciona el carro para recibir el grano.** La celda vecina a la cosechadora tiene que ser camino o rastrojo. En la serpentina, la pasada anterior ya está cosechada, así que siempre hay una disponible, salvo en la primera pasada de una franja (ver el punto siguiente).
   - **La primera pasada de cada franja.** Al inicio no hay rastrojo. La franja empieza por la orilla que toca un camino (como se hace en el campo: se «abre» el lote por la cabecera de la entrada), y el carro espera en ese camino. Si una franja no toca ningún camino, la cosechadora primero cosecha la orilla que la conecta con el rastrojo o con el camino más cercano.
   - **La cosechadora en traslado** (ir a su franja, cambiar de lote o volver a la base) también usa caminos y rastrojo. Solo entra a cultivo en pie cuando lo va cosechando.
   - **Si no hay ruta:** el carro rechaza la llamada con el motivo `sin_ruta`, que ya existe. El costo de la oferta ya usa la distancia real por ruta, así que un carro que tendría que rodear el lote oferta más caro, que es lo correcto.
   - **Registro (IEEE 7007):** cuando un carro rodea el cultivo en pie, se registra una `RESTRICCION` con `regla: "R13_cultivo_en_pie"`, una por tramo, como las demás reglas.
   - **Indicador para el dueño:** metros recorridos por carros y camiones sobre rastrojo contra metros sobre camino (compactación del suelo). Sale del log, sin agregar campos.
   - **Solo aplica con mapa (2.3).** En A–F no hay caminos ni mapa, así que R13 está apagada y la regresión no cambia (`politica.respetar_cultivo`: `true` en G, `false` por defecto).
6. **Relieve:**
   - `tools/dem_a_alturas.py` lee el **Copernicus DEM GLO-30**, cuadro N21 W103. Lee solo la ventana de la zona del COG con `rasterio`, no el archivo entero.
   - Con eso calcula la altura del centro de cada celda (`altura_m`) y un heightmap RAW de 16 bits para el Terrain de Unity, alineado con `mundo.geo`.
   - **Consumo:** factor por pendiente `combustible.factor_pendiente`, con 0 por defecto. Al subir, el consumo por celda se multiplica por `1 + f · pendiente_%/100`; al bajar no se descuenta.

     La fuente de la idea es la norma ASABE D497 (resistencia por pendiente). El valor de f se documenta como supuesto. Con 0 no hay ningún cambio.
7. **Unity solo dibuja:**
   - `TraceLoader` acepta la versión 2.3;
   - `FieldGrid` usa `tamano_celda_m`, `fuera_de_campo`, `caminos` y la orientación de `geo`;
   - el **Terrain de Unity** se crea con el heightmap y las celdas y las máquinas se apoyan en esa altura;
   - **las mallas de lotes, caminos y arboleda se construyen con el código de mallas de `CultivoDesdeKML.cs`** (se reutiliza el trabajo de Oswaldo), pero alimentadas con `mundo.geo.formas` del trace y no con el KML;
   - `PasadasCultivo.cs` no se usa para mover nada; puede quedar como herramienta de editor para comparar sus pasadas con las de la simulación.
8. **Escala:** se mantiene **1 celda = 12 m** (cabezal de 16 hileras a 76 cm), que ya usa la vista.
   - Con 12 m, G tiene unas 1,900 celdas de campo en una cuadrícula de ~75 × 58. Es del tamaño del «60 × 40 que tarda ~1.5 min» que menciona el PR #4.
   - El script de Oswaldo usa un ancho de trabajo de 6 m. Con 6 m serían ~7,500 celdas, demasiadas para el planificador actual.
   - Queda como parámetro (`--celda`) para probar 9 m después (ver preguntas abiertas).

## 4. Pasos en orden

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

## 4b. Mejoras (van DESPUÉS del terreno y los caminos)

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

## 5. Riesgos

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

## 6. Preguntas para el equipo

1. **¿Ancho de celda de 12 m o de 9 m?** 12 m es lo que ya usa la vista y lo que rinde mejor; 9 m equivale a un cabezal de 12 hileras, más común en predios del tamaño de El Pueblito. Recomendación: 12 m ahora y 9 m como experimento si el tiempo de corrida lo permite.
2. **¿Dónde están la bodega y las bases en El Pueblito?** Recomendación: agregarlas como puntos al KML.
3. **¿El escenario G reemplaza a los inventados en la entrega final?** Recomendación: se agrega G y se conservan A–F (la regresión y las comparaciones dependen de ellos).
4. **¿Los scripts de `docs/cultivo/scripts` se integran en Unity?** Recomendación: solo el código de mallas (P6); la lógica de pasadas queda en Python.
