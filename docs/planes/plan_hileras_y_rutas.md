# Plan: hileras reales y rutas de la industria para cosechadoras y carros

> **Copia versionada (27 de noviembre de 2026). Estado: completo.** H0–H8 y H6 están hechos (harvest_sim #34–#40, Unity #7, #8 y #10). Resultados en `docs/resultados_hileras.md`. Las decisiones abiertas de la sección 8 se tomaron así:
> - Fields2Cover solo como referencia, sin compilarlo;
> - la cabecera se cosecha primero;
> - la descarga en marcha quedó dentro del plan (H6) con su propia bandera.

26 de noviembre de 2026. Prioridad: antes de M2. Bitácora: `progreso_terreno.md`.

## Qué se quiere

1. **Que las máquinas respeten las hileras.** Hoy se mueven como si el cultivo no tuviera dirección.
2. **Cambiar BFS por los algoritmos que usa la industria** para cubrir un campo:
   - cabeceras;
   - pasadas paralelas a las hileras;
   - orden de pasadas;
   - vueltas con radio de giro;
   - traslados con rumbo.

## 1. Lo que se investigó

### Software abierto de referencia

| Referencia | Qué es | Qué tomamos |
|---|---|---|
| [Fields2Cover](https://github.com/Fields2Cover/Fields2Cover) ([artículo](https://arxiv.org/abs/2210.07838), [docs](https://fields2cover.github.io), BSD-3, de Wageningen) | Librería abierta de *coverage path planning* para vehículos agrícolas, con paquete de ROS ([índice ROS](https://index.ros.org/p/fields2cover)) | Su cadena de cuatro módulos, que es el estándar de la literatura: **cabeceras → pasadas → orden de pasadas → trayectoria con vueltas** (ver la tabla siguiente) |
| [AgOpenGPS](https://github.com/AgOpenGPS-Official/AgOpenGPS) (GPL-3) | Software abierto de autoguiado que usan agricultores reales | Guía por **línea AB** (las pasadas son paralelas a una línea de referencia) y **vuelta automática en la cabecera** («UTurn») |
| John Deere AutoTrac Turn Automation ([ayuda del S7](https://displaysimulator.deere.com/onscreen_help/S7combine/current/en/autotrac_turn_automation/autotrac_turn_automation_map_controls.htm)) | Producto comercial de las cosechadoras S7 | Confirma el modelo: pasadas guiadas por líneas y vueltas automáticas en la cabecera |

Los cuatro módulos de Fields2Cover:

| Módulo | Cómo lo resuelve |
|---|---|
| Cabeceras | Franja de ancho constante alrededor del lote |
| Pasadas (*swaths*) | Paralelas a un ángulo dado |
| Orden de pasadas | Boustrophedon, **snake** o espiral, con optimización (OR-tools) |
| Trayectoria con vueltas | Curvas **Dubins** y **Reeds-Shepp**, con o sin curvatura continua |

### Cómo se cosecha y se descarga en la práctica

| Fuente | Dato |
|---|---|
| [Wageningen, vueltas en cabeceras](https://edepot.wur.nl/683852) · [Sabelhaus et al., citado en arXiv 2407.05979](https://arxiv.org/html/2407.05979v4) · [vueltas en cabeceras restringidas, arXiv 2308.01117](https://arxiv.org/pdf/2308.01117) | **Tipos de vuelta** según el radio mínimo R y la separación d entre pasadas: U (si d ≥ 2R), Ω y *fishtail* (si d < 2R). El ancho de la cabecera sale del tipo de vuelta, de R y del ancho del cabezal. |
| [Farm Progress](https://www.farmprogress.com/management/combine-corn-in-any-direction) · [U. de Arkansas](https://www.uaex.uada.edu/publications/pdf/mp437/chap8.pdf) · [Bayer](https://www.cropscience.bayer.us/articles/bayer/combine-settings-drought-stricken-corn-crop) | **Maíz e hileras:** un cabezal maicero convencional tiene que ir centrado sobre las hileras; salirse 10–13 cm sube las pérdidas. Solo los cabezales «independientes de hilera» cortan en cualquier dirección y se usan para abrir las cabeceras. |
| [John Deere Machine Sync](https://www.deere.com/en/technology-products/precision-ag-technology/guidance/machine-sync/) · [Case IH Raven Cart Automation](https://www.caseih.com/en-us/unitedstates/connect-with-us/farm-forum/improve-harvest-efficiency-with-raven-cart-automation) · [PTx Trimble OutRun](https://www.farms.com/ag-industry-news/automating-grain-cart-operations-with-outrun-794.aspx) | **Descarga en marcha:** el carro se sincroniza al lado de la cosechadora (líder y seguidor) y recibe el grano sin que ella se detenga. |
| [Ali, Verlinden y Van Oudheusden 2009](https://typeset.io/pdf/infield-logistics-planning-for-crop-harvesting-operations-dx96tx1j4o.pdf) · [Nørremark et al. 2022](https://doaj.org/article/46ffc3cf34c346a7bb0c8e65547c9e5d) · [Evans, UNL](https://digitalcommons.unl.edu/dissertations/AAI10977171) · [Bochtis, patrones B con colonias de hormigas](https://dialnet.unirioja.es/descarga/articulo/4373233.pdf) | **Logística en el campo:** el orden de pasadas y las rutas de los carros se optimizan como un problema de ruteo con restricciones de vuelta; optimizar la ruta del carro reduce su recorrido ~25 %. |

**Instalación de Fields2Cover:** en PyPI solo está el código fuente (`fields2cover-2.1.0.tar.gz`, 0.1 MB, 2026-09-03), sin wheel. Instalarlo es compilar C++ con GDAL, GEOS, Eigen, TBB, SWIG y OR-tools. No conviene como dependencia de la simulación ni del CI (ver decisiones).

## 2. Qué pasa hoy (medido)

**G con `anticipada_plus`, seed 0: los 2,172 movimientos de las cosechadoras.**

| Movimiento | Veces | ¿Realista? |
|---|---|---|
| A lo largo de la hilera, cosechando | 1,670 | Sí |
| **De lado hacia una hilera nueva, cosechándola** (entra perpendicular con el cabezal) | **102** | **No:** cada cambio de pasada corta la primera celda de lado |
| **De lado sobre cultivo en pie, sin cosechar** | **9** | **No:** lo pisa |
| A lo largo sobre cultivo en pie, sin cosechar | 14 | No |
| **Vuelta de 180° en un tick** (radio de giro 0) | **12** | **No:** una cosechadora necesita ~2R ≈ 15–18 m y una cabecera |
| De lado o a lo largo sobre rastrojo o camino | 377 | Sí, pero con giros instantáneos |

**Causas:**

- **El modelo no conoce las hileras.** Una celda es «campo», sin dirección.
- **Las rutas no tienen rumbo ni radio de giro.**
  - La cosechadora recorre su lote en serpentina por celdas, y el cambio de pasada es un paso de lado dentro del cultivo.
  - Los traslados son BFS en vecindad 4, con un respaldo que cruza el cultivo.
  - No hay cabeceras: las vueltas ocurren dentro del cultivo.
- **El carro y la cosechadora se detienen para transferir.** En la industria se descarga en marcha.

**En Unity:** las hileras de maíz ya van a lo largo del eje x de cada celda, en la misma dirección que las pasadas de G. Pero están a 1.2 m; el maíz se siembra a ~0.76 m (16 hileras en 12 m, un cabezal de 16 hileras).

## 3. Modelo nuevo

Se mantiene la cuadrícula lógica de 12 m, con su tick, sus reservas y las reglas R1–R13: es la base de todo lo demás (métricas, M1, Unity). Lo que cambia es **qué movimientos son válidos y cuánto cuestan**. La geometría fina de las vueltas va en metros.

### 3.1 Hileras y cabeceras

- **Dirección de las hileras.**
  - Con mapa (G): la que da el rumbo de los surcos; la cuadrícula ya está alineada, así que las hileras van a lo largo de x.
  - Sin mapa (A–F): a lo largo de x por convención, como ya hace la serpentina.
- **Cabecera de cada lote.**
  - Es una franja de `k` pasadas en los extremos del lote, donde terminan las hileras.
  - Se calcula como Fields2Cover (`HG_Const_gen`): un recorte de ancho constante con shapely.
  - `k` sale del radio de giro y del ancho del cabezal: `k = ceil(ancho_vuelta / 12 m)`. Con R ≈ 7.5 m y cabezal de 12 m, una vuelta Ω u omega cabe en ~2–3 celdas.
- **Regla nueva R14 (hileras):** dentro del cultivo en pie, la cosechadora solo avanza **paralela a las hileras** y cosechando. Nadie entra de lado a cultivo en pie.
  - Las vueltas y los cambios de pasada ocurren en la cabecera ya cosechada o en un camino.
  - Se registra como `RESTRICCION R14_hileras` cuando cambia una decisión.

### 3.2 Cobertura: la cadena de Fields2Cover

1. **Abrir el campo:** la cabecera se cosecha primero, dando vueltas al lote siguiendo el contorno, como con un cabezal independiente de hilera. Así todas las vueltas posteriores son sobre rastrojo. La alternativa es dejarla al final (decisión 2).
2. **Pasadas (*swaths*):** líneas paralelas a las hileras, separadas 12 m (una por fila de la cuadrícula) y recortadas al lote sin la cabecera. Ya existe un puerto parecido (`mapa/pasadas.py`, de `PasadasCultivo.cs`).
3. **Orden de pasadas:**
    - **snake** (salta pasadas para que la vuelta sea en U sin reversa cuando 2R > 12 m), contra boustrophedon (pasada vecina, con vuelta Ω);
    - se elige el de menor tiempo de vueltas;
    - con dos cosechadoras, cada una toma bloques (*lands*) contiguos del lote.
4. **Vueltas:** la trayectoria entre el fin de una pasada y el inicio de la siguiente es una curva **Dubins** (o Reeds-Shepp si no cabe), dentro de la cabecera y con radio R.
    - Su duración en ticks es `ceil(largo / (velocidad_vuelta · Δt))`.
    - La geometría en metros va al trace para Unity.

### 3.3 Traslados: A* con rumbo en lugar de BFS

- **Fuera de la cobertura** (de la base al lote, entre lotes, a recargar, el carro a la cosechadora y a la bodega), la búsqueda es **A\* sobre estados (celda, rumbo)**, el enfoque de *Hybrid A\** / *state lattice* que usan los vehículos con radio de giro. Se reemplaza `rutas.bfs` y se conservan las reservas en el tiempo (A* cooperativo).
- **Costos:** distancia, giro de 90° (equivale a ~1–2 celdas) y giro de 180° (solo en rastrojo o camino, con el costo de la vuelta Dubins). Prohibido: cultivo en pie (R13 y R14), obstáculos y fuera del predio.
- **Heurística:** distancia Manhattan; es admisible porque cada paso cuesta al menos 1.
- **En caminos:** A* sobre el grafo de caminos (la red ya está soldada). Más adelante, velocidad de traslado mayor en camino.

### 3.4 Carros: descarga en marcha (fase aparte, desactivable)

- **Como Machine Sync / Raven:** el carro se pone al lado de la cosechadora, sobre el rastrojo de la pasada anterior, y la sigue a su velocidad. La cosechadora sigue cosechando mientras transfiere.
- **Qué cambia:** cambia la métrica principal. El ocio solo existe si no llega carro a tiempo. Por eso va detrás de una bandera y se compara contra la transferencia detenida.
- **En el trace:** la transferencia en marcha agrega el estado del carro `ACOMPANANDO`, o se reutiliza `ESPERANDO_TRANSFERENCIA` con un flag (decisión de formato).

### 3.5 Tiempo y velocidades

Un tick es una celda a velocidad de cosecha: 12 m a ~6 km/h ≈ 7 s.

| Movimiento | Velocidad | Ticks |
|---|---|---|
| Cosechar | ~6 km/h | 1 por celda (como hoy) |
| Vuelta en cabecera | ~5 km/h | `ceil(largo_Dubins / 10 m)` (una vuelta U de R = 7.5 m mide ~24 m: 3 ticks) |
| Traslado en rastrojo | ~8 km/h | 1 por celda |
| Traslado en camino | ~15 km/h | 1 por celda (más rápido, más adelante) |

Todo va en `config` (`maquinas: {radio_giro_m, velocidad_cosecha, velocidad_vuelta, ancho_cabezal_m}`) y se documenta como supuesto.

## 4. Formato e implementación

- **Python:**
  - `mapa/cobertura.py` (nuevo): cabeceras, pasadas, orden (snake o boustrophedon) y curvas Dubins, todo con shapely y escrito por el equipo siguiendo el diseño de Fields2Cover;
  - el convertidor del KML guarda en el mapa `cabeceras`, `pasadas` y `hileras` (el rumbo);
  - `rutas.py`: `astar_rumbo` y su versión con reservas en el tiempo;
  - `mundo.py`: R14, celdas de cabecera, orden de cobertura y costo de vueltas;
  - `cosechadora.py` y `carro.py`: usan las rutas nuevas; el estado del carro para descarga en marcha (fase 6).
- **Trace 2.4** (solo con `politica.movimiento = "hileras"`; A–F siguen en 2.2 y G sin la bandera en 2.3):
  - `pose.rumbo_grados` (opcional);
  - evento `TRAYECTORIA` por vuelta o traslado: la polilínea en metros del marco de la cuadrícula, generada desde la Dubins;
  - en `mundo`: `cabeceras` y `pasadas`.
- **Unity:**
  - mueve las máquinas sobre la `TRAYECTORIA` con curvas paramétricas (Catmull-Rom o Bézier entre puntos de la Dubins), lo que cubre el tema del curso que faltaba;
  - el rumbo es continuo;
  - las cabeceras se dibujan;
  - el maíz va a 0.76 m entre hileras;
  - el cabezal se alinea con las hileras.
- **Fields2Cover como referencia de validación, no como dependencia:**
  - si se compila localmente (decisión 1), una prueba opcional compara nuestras cabeceras, pasadas y largos Dubins con las suyas en El Pueblito;
  - sin él, la prueba se salta y el CI no cambia.

## 5. Fases

| Fase | Qué | Listo cuando |
|---|---|---|
| H0 | Bandera `politica.movimiento` (`celdas` por defecto, `hileras`); medición actual de G como línea base (la tabla de la sección 2), automatizada en `tools/verificar_terreno.py` | La medición sale en el verificador |
| H1 | `mapa/cobertura.py`: cabeceras, pasadas y orden snake/boustrophedon; mapa regenerado | Pruebas: cobertura completa sin repetir celdas; la cabecera rodea cada lote; las pasadas son paralelas al rumbo; ancho de cabecera según R |
| H2 | Curvas Dubins (LSL, RSR, LSR, RSL, RLR, LRL) y tipo de vuelta (U, Ω, fishtail) según d contra 2R | Pruebas contra casos conocidos (largos analíticos; d ≥ 2R da U); prueba opcional contra Fields2Cover |
| H3 | Cosechadora con R14: abre la cabecera, recorre las pasadas en el orden elegido y da las vueltas en la cabecera con su costo en ticks | En G: 0 entradas de lado a cultivo, 0 vueltas de 180° en un tick, 0 celdas de cultivo pisadas; todo cosechado; sin colisiones |
| H4 | A* con rumbo y reservas en lugar de BFS para traslados y carros | Misma validez (R1–R14), sin atascos en G × 4 estrategias × 20 seeds; tiempo por corrida medido |
| H5 | Trace 2.4 (`rumbo_grados`, `TRAYECTORIA`, cabeceras) y validador | Traces 2.4 validan; A–F y G sin bandera, idénticos |
| H6 | Descarga en marcha (bandera aparte) | Comparación pareada: detenida contra en marcha |
| H7 | Unity: movimiento sobre la trayectoria (curvas paramétricas), rumbo continuo, cabeceras visibles, hileras a 0.76 m | EditMode en verde; captura de una vuelta en cabecera |
| H8 | Experimentos: G con las 4 estrategias y con M1 reentrenado, con y sin hileras; eficiencia de campo (tiempo cosechando / total), tiempo en vueltas y compactación; documentación | Resultados y documentos al día |

## 6. Pruebas y métricas nuevas

- **Métricas nuevas:**
  - `eficiencia_campo`: ticks cosechando / ticks activos;
  - `tiempo_en_vueltas`;
  - `entradas_de_lado`: debe ser 0 con hileras;
  - `celdas_pisadas_cosechadora`: debe ser 0;
  - `vueltas_instantaneas`: debe ser 0.
- **Regresión:** A–F y G sin bandera, byte a byte; `test_regresion` igual.
- **Verificador de terreno:** suma R14 a R10, R12 y R13 para G × 4 estrategias × 20 seeds.

## 7. Riesgos

- **Cabeceras de solo 2–3 celdas.** En lotes angostos del KML la cabecera puede no caber; la vuelta Ω o fishtail puede salir del lote. Mitigación: tipo de vuelta según el espacio y, si no cabe, vuelta sobre un camino o el rastrojo vecino, como hace Wageningen con espacio limitado.
- **Atascos con las reglas nuevas.** Más restricciones dan menos rutas posibles. El verificador de 80 corridas y la prueba de regresión del atasco de M1 se corren en cada fase.
- **Rendimiento.** A* con rumbo tiene 4 veces los estados de BFS. Se mide en H4; G tarda ~21 s por corrida.
- **M1 se invalida.** Las tablas Q se entrenaron con el movimiento viejo. Hay que reentrenarlas en H8, unos 20 min por algoritmo en G.
- **Resultados publicados.** Los de G cambian con la bandera. Se reportan aparte, sin reescribir los de P7 y M1.

## 8. Decisiones abiertas

1. **Fields2Cover:** compilarlo localmente solo para validar (hay que instalar paquetes del sistema: GDAL, OR-tools, SWIG…), o usarlo solo como referencia de diseño, sin compilar. Recomiendo compilarlo solo si queremos la comparación numérica; no es necesario para implementar.
2. **Cabecera:** cosecharla primero («abrir el campo», recomendado) o al final.
3. **Descarga en marcha (H6):** dentro de este plan, o como mejora aparte después.
