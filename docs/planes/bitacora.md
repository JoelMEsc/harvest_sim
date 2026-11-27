# Progreso: terreno realista (bitácora para no perder el hilo)

> **Bitácora del trabajo con Claude Code** (terreno, M1 e hileras), versionada el 27 de noviembre de 2026. Las menciones al «scratchpad» eran carpetas temporales de trabajo que ya no existen; todo lo necesario para continuar está en el repo (ver `docs/estado_y_pendientes.md`).

> Documento personal, fuera de los repos. El plan está en `tc2008b/plan_terreno_realista.md`. Este archivo dice **qué está hecho, qué sigue y cómo retomarlo**. Se actualiza al terminar cada paso.

## Cómo retomar (si se cortó la sesión)

1. Leer este archivo completo y el plan.
2. `cd tc2008b/harvest_sim && git status -sb && git log --oneline -5`: la rama de trabajo es `branch-joel`.
3. Unity: el clon está en `tc2008b/harvest-simu-visualization` y la rama de trabajo es `terreno-2.3` (sale de `origin/dev`).
4. Seguir con el primer paso que no tenga ✅ en la tabla de abajo.
5. Probar con:
   ```
   SDL_VIDEODRIVER=dummy MPLBACKEND=Agg .venv/bin/python -m pytest -q -p no:cacheprovider
   ```
   Correr también `tools/` si aplica.

## Ramas y reglas

- **harvest_sim:** todo va en `branch-joel` (sale de `origin/development`). Un commit por paso, con el mensaje en español y la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nunca un commit directo a `development` ni a `main`.
- **Unity:** la rama `terreno-2.3` en `GioMax102/harvest-simu-visualization`, con PR a `dev`.
- **Push, PR y merge:** según lo que Joel diga (ver «Permisos»).
- **Regresión:** A–F deben dar siempre las métricas de v0.1 (`tests/test_regresion.py`). Toda novedad queda desactivada por defecto.

## Permisos (respuesta de Joel)

- Descargar la ventana del DEM e instalar shapely, pyproj y rasterio: **autorizado** (2026-11-25).
- Push y PR: **todo a `branch-joel`**. Yo reviso el CI y **hago el merge de mis propios PR** (`branch-joel` → `development`) cuando está en verde, uno por fase. En Unity: `terreno-2.3` → `dev`, verificado con las pruebas locales de Unity (no hay CI ahí).

## Decisiones finas tomadas al implementar (no están en el plan)

1. **No hay camión en harvest_sim:** el carro lleva el grano a la bodega. Por eso R13 aplica a los carros.
2. **El trace es 2.3 solo si el mundo tiene mapa.** `TraceBuilder` escribe `"2.3"` cuando `mundo` trae algún campo de 2.3; si no, escribe `"2.2"` como hoy. Así A–F no cambian (ni sus bytes) y Unity sigue leyendo A–F mientras se adapta.
3. **Caminos en la cuadrícula:** se rasterizan con la línea central de cada camino, usando todas las celdas que toca la línea (supercover). Así la red queda conectada en vecindad 4 aunque el camino sea de 4 m y la celda de 12 m. Una celda de camino gana sobre campo solo si la línea pasa por ella; el área perdida se mide contra el ±5 % de C1.
4. **Patio de servicio:** la bodega y las bases van en celdas que no son campo ni camino, junto al camino y cerca del punto de la bodega. Si fueran sobre un camino de una celda, las máquinas estacionadas lo taparían. En el trace 2.3 las celdas del patio van en `caminos` (transitables).
5. **Zonas por lote:** cada cosechadora recibe lotes completos, repartidos por tamaño (el más grande primero, a la cosechadora con menos celdas). Si hay más cosechadoras que lotes, el lote más grande se parte en bandas de filas. Las filas de la cuadrícula siguen el rumbo de los surcos: **una fila es una pasada**.
6. **Orden de las pasadas en un lote:**
   - empieza en la fila de la orilla (la de mínima o la de máxima y) y en el extremo más cercano a una celda de camino (BFS desde la bodega por caminos);
   - cada fila siguiente empieza en el extremo más cercano al final de la anterior (boustrophedon).

   Solo aplica con mapa; en A–F sigue la serpentina de v0.1.
7. **R13:**
   - es estricta para los carros;
   - la cosechadora en traslado prefiere caminos y rastrojo; si no hay ruta, cruza su propio cultivo en pie (se cuenta y la prueba exige que pase poco o nada en G);
   - `mundo.bloqueadas_para(agent_id)` = fijas (R9, R10, R12) + cultivo en pie para los carros;
   - el conjunto en pie se mantiene de forma incremental (cada cosecha libera una celda).
8. **Unity dibuja en el marco de la cuadrícula** (sin rotar). `geo.formas` viene en metros de la cuadrícula y el heightmap se remuestrea en Python en ese mismo marco. `geo.rumbo_grados` solo sirve para el norte y el sol.
9. **El mapa en el trace:** `config.mapa` lleva el contenido cargado; en el trace, la sección `config` solo guarda `{"archivo", "sha256"}` para no duplicar el mapa (que ya va en `mundo`).
10. **Rutas relativas del mapa:** `cargar_config` busca `mapa` junto al JSON y, si no está, en `config/` del repo. Así funcionan los experimentos y el servidor, que escriben la configuración en un directorio temporal.

## Pasos (marcar ✅ y anotar el commit al terminar)

| Paso | Qué | Dónde | Estado | Commit |
|---|---|---|---|---|
| P0 | `docs/especificacion_terreno.md` y la decisión «la forma entra por Python» | harvest_sim | ✅ | e820308 (PR #20, merge) |
| P1 | Formato 2.3: `formato.py`, validador, `campo.py`, versión condicional en `trace.py`, ejemplo 2.3 (`tools/traces_ejemplo_23.py`, `tests/fixtures/trace_ejemplo_23.json`) y pruebas | harvest_sim | ✅ | 9a932d2 (PR #20, merge) |
| P2 | `src/harvest_sim/mapa/` (KML, proyección, soldadura, rasterizado, patio, pasadas portadas), `tools/kml_a_mapa.py`, `config/mapas/el_pueblito.{yaml,json}`, `config/escenario_g.json` y pruebas | harvest_sim | ✅ | 5a69a79 (PR #21, merge) |
| P3 | Config con `mapa`; mundo con tipos de celda, patio, R12, `bloqueadas_para` (R13), zonas por lote y orden de pasadas; alcanzabilidad; `descripcion()` 2.3 | harvest_sim | ✅ | PR #22 (merge) |
| P4 | `tools/dem_a_alturas.py`, `altura_m` en el mapa y en el mundo, factor de pendiente y pruebas | harvest_sim | ✅ | PR #24 (merge) |
| P5 | Carro y cosechadora con `bloqueadas_para` y R13; correr G con 4 estrategias × 20 seeds; corregir; medir tiempo | harvest_sim | ✅ | PR #25 (merge) |
| P6 | Unity: `TraceLoader` 2.3, `FieldGrid` (caminos y fuera), Terrain con alturas, mallas de `geo.formas` (código de `CultivoDesdeKML`), atribución, traces de G y pruebas | Unity | | |
| P7 | Integración G (C1, C2, C2b, C2c), métricas de compactación, experimentos (G, pendiente, con y sin R13), resultados, README y autoevaluación | harvest_sim | | |
| M1…M12 | Mejoras, en el orden del plan, solo después de P7 | ambos | | |

## Notas de avance

(Se agregan al terminar cada paso: qué salió, números medidos, problemas.)

- **P0+P1** (PR #20, en `development`): `SCHEMA_VERSION` sigue en `"2.2"` (lo usan `/api/salud` y Unity) y `SCHEMA_VERSION_MAPA = "2.3"`. El visor y el dashboard aceptan 2.3. Fixture: `tests/fixtures/trace_ejemplo_23.json`. 665 pruebas.
- **P2** (PR #21): mapa de 76 × 52 celdas de 12 m, rumbo común de 51.6° (UTM; las guías dan 56.7, 54.7 y 48.1 en UTM, y 57.5, 55.5 y 48.9 con la proyección de Oswaldo), 1762 de campo (A 353, B 487, C 922), −3.2 % de área, 14 soldaduras y 21 celdas de puente, bodega en [31, 50] y 8 bases. Reglas de celda afinadas: un obstáculo es una celda que lo toca; un camino gana al campo solo si su línea central pasa por el centro de la celda. La configuración del convertidor es `config/mapas/el_pueblito.convertidor.json` (JSON, no YAML). `construir_desde_config` ya llama a `mapa/relieve.py:agregar_alturas` si `dem` no es null (P4).
- **P3** (PR #22): `Config.mapa` (contenido + archivo + sha256), `politica.respetar_cultivo`, `mundo.bloqueadas_para`, `mundo.cultivo_en_pie()`, `mundo.zonas()` (C → cosechadora_1; A y B → cosechadora_2), `mundo.celdas_camino`, `mundo.fuera_de_campo`, `mundo.tamano_celda_m`. Escenario G: 2 + 2, capacidades 120/360, tasas 12/24. Humo: 1708 ticks, ~11 s, 0 colisiones. Caminos de las cosechadoras: 31 y 15 saltos no vecinos (bordes irregulares y arboleda): revisar en P5.

## ⏸ PAUSA (pedida por Joel): dónde quedé y cómo seguir

**Estado de los repos al pausar:**
- harvest_sim: `branch-joel` = `origin/development` = `eb65082` (merge del PR #22). Sin cambios sin commit. P0–P3 están en `development` (PR #20, #21 y #22, con merge y el CI en verde). 697 pruebas.
- Unity (`tc2008b/harvest-simu-visualization`, rama `terreno-2.3` = `origin/dev`): todavía sin cambios.

**Siguiente: P4 (relieve).** Todavía no hay nada escrito. El diseño ya está decidido:
1. Descargar (ya autorizado) solo la ventana de El Pueblito del COG:
   `/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N21_00_W103_00_DEM/Copernicus_DSM_COG_10_N21_00_W103_00_DEM.tif`
   con `rasterio` (ya instalado en `.venv`: 1.4.3; agregar `rasterio==1.4.3` a `requirements.txt`). Recortar a la zona y guardarlo en `config/mapas/el_pueblito_dem.tif` (caché chico, para regenerar sin red). Registrar la URL y la atribución de Copernicus.
2. Crear `src/harvest_sim/mapa/relieve.py` con `agregar_alturas(mapa, ruta_dem) -> list[str]` (líneas del reporte). `construir_desde_config` ya la llama si `"dem"` no es null.
   - Reproyecta con `rasterio.warp.reproject` (bilineal) a la cuadrícula girada, con `dst_crs = EPSG:32613` y una afín girada. Con θ = `geo.rumbo_grados`, s = celda y (E0, N0) = `geo.origen_utm`: `Affine(s·sinθ, −s·cosθ, E0, s·cosθ, s·sinθ, N0)`. Ojo: los centros de celda necesitan un desplazamiento de media celda, o se toma la esquina y se documenta.
   - Escribe `mapa["altura_m"]` (alto × ancho, 2 decimales) y agrega la atribución del DEM a `geo.atribucion`.
3. Poner `"dem": "el_pueblito_dem.tif"` en `config/mapas/el_pueblito.convertidor.json` y regenerar con `.venv/bin/python tools/kml_a_mapa.py --figura docs/figuras/terreno/el_pueblito_mapa.png`. La prueba `test_el_json_del_repo_esta_al_dia` exige que el JSON del repo sea el regenerado.
4. Consumo por pendiente:
   - en `config.py`, `COMBUSTIBLE_POR_DEFECTO["factor_pendiente"] = 0` (validar ≥ 0);
   - en `mundo.actualizar_combustible(agente, se_movio, desde=None)`, si hay `altura_m` y el agente subió: consumo × (1 + f · pendiente_% / 100), donde pendiente_% = Δh / tamano_celda_m · 100; al bajar, sin descuento;
   - en `simulacion.py`, pasar `desde=inicio[id]`.
5. Pruebas (`tests/test_relieve.py`):
   - las alturas coinciden con el DEM en 3 puntos de control;
   - con factor 0 el consumo no cambia (regresión A–F);
   - con factor > 0, subir cuesta más que bajar;
   - un trace de G con `altura_m` valida.
6. Actualizar la especificación §8: Unity interpola el terreno desde `altura_m`; no hace falta un RAW aparte.
7. Commit, PR «Terreno realista (4/5): relieve», CI y merge.

**Después:**
- **P5:** carro y cosechadora usan `bloqueadas_para` y R13 (el carro: `_bloqueadas(mundo)` en lugar de `bloqueadas_fijas` en ~10 lugares de `carro.py`, y `RESTRICCION R13_cultivo_en_pie` por tramo; la cosechadora prefiere camino y rastrojo en traslado, con respaldo a las fijas, y se cuenta cuántas veces cruza su cultivo). Correr G con 4 estrategias × 20 seeds usando el script de `scratchpad/corridas.py` (o rehacerlo) y medir colisiones, BLOQUEO, R12, R13 y tiempo.
- **P6:** Unity.
- **P7:** pruebas, experimentos y documentación.
- Después, M1–M12.

- **P4** (PR #24): DEM en `config/mapas/el_pueblito_dem.tif`; `mapa/relieve.py`; campo de 1705 a 1715 m (pendiente media de 1.5 %); `combustible.factor_pendiente`; `mundo.altura()` y `mundo.factor_pendiente()`. Con f = 2, G usa 1.6 % más combustible. `docs/plan_terreno.md` (del equipo) lleva el estado: actualizarlo en cada PR.
- **P5 en curso:** el carro usa `_bloqueadas(mundo)` y registra R13; la cosechadora, en traslado, evita el cultivo en pie (`cruces_cultivo` cuenta cuándo no puede). Sin commit todavía.
- **P5** (PR #25): 80 corridas de G (`tools/verificar_terreno.py`) con 0 colisiones, 0 BLOQUEO, 0 R12 y 0 carros sobre cultivo; el despacho anticipado baja el ocio 69 %. R13 no alarga rutas en las corridas (rodear en escalera mide igual en vecindad 4); hay una prueba con un caso construido.
- **Siguiente (antes de Unity): quitar el espejo.** En Unity, `FieldGrid` dibuja la celda (x, y) en (x·s, 0, −y·s), y la y de la cuadrícula hoy va a la IZQUIERDA de los surcos, así que El Pueblito saldría en espejo. Cambiar `convertir.Marco` para que la y vaya a la DERECHA (`y = dE·cosθ − dN·sinθ`; `E = E0 + x·sinθ + y·cosθ`, `N = N0 + x·cosθ − y·sinθ`), cambiar la afín de `relieve.py` a `Affine(s·sinθ, s·cosθ, E0, s·cosθ, −s·sinθ, N0)`, regenerar el mapa, actualizar los números de las pruebas y de la especificación (§5 y §13) y volver a correr `verificar_terreno`.
- **Espejo** (PR #26, merge): el eje y va a la DERECHA de los surcos. Mapa: 1772 de campo (A 364, B 489, C 919), −2.6 %, bodega [31, 1]. G: base 1692 ticks y 806 de ocio; anticipada 1481 y 390 (−52 %); 0 colisiones, 0 BLOQUEO, 0 R12, 0 carros sobre cultivo.
- **P6 en curso (Unity, rama `terreno-2.3`):** traces en `Assets/Data/Traces/terreno/` (ejemplo_23 y G base y anticipada_plus). Plan C#: TraceLoader acepta 2.3 y reglas con mapa; FieldGrid con caminos, fuera y alturas (`CellToWorld` suma la altura, `GroundHeight` bilineal); GroundBuilder con esquinas apoyadas en el relieve y sin cuadros de camino con mapa; CornField con la altura de cada planta; SceneryBuilder (cerca y árboles) con la altura; TerrainShapes nuevo (franjas de caminos de 4 m y contorno de lotes desde geo.formas); TraceClient acepta salud 2.2 o 2.3; atribución del DEM en el HUD; pruebas EditMode nuevas (TerrainTests.cs).
- **P6 (Unity), cambios escritos (sin commit):** TraceLoader (2.3, `desde22`, reglas con mapa), FieldGrid (`HasMap`, `HasRelief`, `BaseHeight` = mínima del campo, `GroundHeight` bilineal; `CellToWorld` suma la altura), GroundBuilder (esquinas apoyadas en el relieve, malla de pasto con relieve, sin cuadros de camino con mapa), CornField (y de cada planta), SceneryBuilder (sin cerca con mapa; árboles del margen sobre el relieve), TerrainShapes.cs nuevo (franjas de 4 m adaptadas de `Cinta` de Oswaldo y contorno de los lotes), WorldView (Shapes), TraceClient (salud 2.2 o 2.3), HUD (atribución de `geo.atribucion` en el panel del campo), pruebas en `Assets/Tests/EditMode/TerrainTests.cs`. Se corren con `~/Unity/Hub/Editor/6000.3.7f1/Editor/Unity -batchmode -projectPath harvest-simu-visualization -runTests -testPlatform EditMode -testResults <xml>` (sin `-nographics`).
- **P6** (GioMax102/harvest-simu-visualization PR #5, merge en `dev`; tabla del plan en harvest_sim PR #27): EditMode 55/55. Se revirtió `Placa_Agente.mat` (cambio automático de TextMeshPro).
- **P7** (harvest_sim PR #28): métrica `metricas.suelo_de_carros` (metros de carro sobre camino, rastrojo y cultivo; solo con mapa); `config/experimentos/terreno_g_{estrategias,pendiente,r13}.json` (340 corridas); `docs/resultados_terreno.md`; README, autoevaluación (sección nueva al final), especificación §13 y plan (P7 hecho). 711 pruebas.
  - G: anticipada_plus −55 % de ocio y −28 % de J; R13 cuesta de 1.4 % a 2.2 % de tiempo y evita 348 m (anticipada) y 864 m (anticipada_plus) sobre cultivo; base y subasta nunca pisarían cultivo. Pendiente: +0.8 % de combustible por unidad de f, sin cambio de tiempo.
  - Limitación: G es determinista (IC = 0).
- **Siguiente:** M1 (Q-learning para el despacho), en el orden de la sección 4b del plan, con G como caso principal, desactivada por defecto, una rama y un PR por mejora.
- **README** (PR #29, merge): correr_todos.sh con A–G (G sin comparación, `plots.py --sin-comparacion`), visor 2D con mapa 2.3, README revisado completo, mensaje de variación corregido.
- **M1** (PR #30, merge): `aprendizaje.py` (Q-learning y SARSA tabulares; una decisión por tramo de la tolva; γ = 0.999), `politica.aviso`/`qtabla`, `tools/entrenar_despacho.py`, tablas en `config/aprendizaje/`, `docs/especificacion_mejoras.md` y `docs/resultados_mejoras.md`.
  - G: SARSA −37 % de ocio contra anticipada; Q-learning no convergió en 60 episodios (+19 %).
  - D: −2 % a −3 % (el mejor umbral fijo solo gana 3 %).
  - Arreglos en el camino: decisión por tramo (no por celda), objetivo de Q-learning en el estado forzado, y el carro ya no encierra a la cosechadora en traslado (`mundo.paso_de`; A–G sin cambios).
- **Siguiente:** M2 (equilibrio de Nash), en el orden del plan.
- **Documento de temas del curso** (PR #31): `docs/temas_del_curso.md` (también en Claude Docs, privado).
- **M1 en Unity** (plan en `tc2008b/plan_m1_unity.md`):
  - Python (PR #32): evento `DECISION_DESPACHO` (estado, q, acción, origen), `config.aprendizaje` (tabla y sha256), métricas `decisiones_despacho`/`pedidos_tabla`/`pedidos_respaldo`/`cliffs_despacho`, validador, servidor con estrategias por escenario, exportación con qlearning/sarsa. 742 pruebas; A–G sin cambios; G SARSA sigue en 244 de ocio.
  - Unity (GioMax102/harvest-simu-visualization PR #6, merge en `dev`): cargador, `PlaybackState.Decisions`, `TickCues.Decisions`, placa «Q: pide carro», tarjeta con la última decisión, selector desde el servidor (y 6 opciones en la escena), métricas y leyenda; traces en `Assets/Data/Traces/mejoras/`; EditMode 69/69.
  - Las pruebas y la captura se corrieron en una copia (`scratchpad/unity_copia`) porque el editor estaba abierto. La primera corrida falló en 4 pruebas de la escena solo por la caché fría de la copia.
  - Documentos (PR #33): resultados con la captura, plan del equipo, temas del curso, autoevaluación y README.
- **Siguiente:** M2 (equilibrio de Nash).
- **Plan nuevo (prioridad sobre M2):** `tc2008b/plan_hileras_y_rutas.md`, sobre hileras reales y rutas de la industria.
  - Investigación: Fields2Cover (cabeceras → pasadas → orden snake/boustrophedon → Dubins), AgOpenGPS (líneas AB y vuelta en cabecera), tipos de vuelta (U/Ω/fishtail), descarga en marcha (Machine Sync, Raven, OutRun).
  - Fields2Cover 2.1.0 está en PyPI solo como código fuente (hay que compilar C++ con GDAL y OR-tools).
  - Medido en G: 102 entradas de lado a una hilera nueva cosechándola, 9 pasos de lado sobre cultivo, 12 vueltas de 180° en un tick.
  - Fases H0–H8. Decisiones abiertas: compilar o no Fields2Cover, cabecera primero o al final, y si la descarga en marcha entra en este plan.
- **Hileras y rutas** (plan en `tc2008b/plan_hileras_y_rutas.md`; Fields2Cover solo como referencia, cabecera primero):
  - H0 (#34): métrica `movimiento_cosechadoras`, bandera `politica.movimiento`.
  - H1–H3 (#35): `mapa/cobertura.py`, `mapa/dubins.py`, R14, `secuencia_alcanzable`, carro que espera.
  - H4 (#36): `rutas.astar_rumbo_tiempo`; costos de giro por máquina (`config.maquinas`).
  - H5 (#37): trace 2.4, evento `TRAYECTORIA`; visor y dashboard aceptan 2.4.
  - H7 (Unity #7, traces regenerados en #8): Catmull-Rom sobre la curva, orilla de la cabecera, maíz a 0.76 m. EditMode 75/75.
  - H8 (#38): `escenario_g_hileras`, experimento `hileras_g`, `docs/resultados_hileras.md`. Ticks +29–35 %, 0 entradas de lado, 0 pasos sobre cultivo, 0 vueltas instantáneas.
  - Atascos corregidos: el carro espera fuera de toda la ruta y sin plan; `progreso_de_giro`.
  - Falta: M1 reentrenado en `escenario_g_hileras` (corriendo, logs en `harvest_sim/runs/entrenar_gh_*.log`) y H6 (descarga en marcha).
- **2026-11-27:**
  - Revisé los cambios del equipo. Oswaldo hizo merge en Unity (#9: orillas de lote recortadas con LotShapes y tramos suaves por camino con RoadRoutes); respeta la prioridad de las vueltas 2.4, sin conflictos. Repos sincronizados (`dev` c799b65, `development` 5063142 → #39).
  - M1 con hileras (#39, CI de `development` en verde): tablas de `escenario_g_hileras`. Contra anticipada, SARSA −13.6 % de ocio y −6.4 % de tiempo; Q-learning −10.9 % y −2.0 %.
  - Sigue: H6, descarga en marcha.
- **H6, descarga en marcha** (harvest_sim #40, Unity #10). **Plan de hileras completo.**
  - `politica.descarga_en_marcha` (requiere hileras; actúa con subasta): cita en el lateral de la pasada actual o la siguiente, estado nuevo del carro `RECIBIENDO_EN_MARCHA`.
  - `escenario_g_en_marcha`; experimento `hileras_g_en_marcha`.
  - Con umbral fijo: ocio −19 % (anticipada) y −21 % (anticipada_plus, 1897 ticks y 340 de ocio, la mejor combinación). SARSA sin reentrenar con la bandera: ocio −9 %, pero tiempo +10 %.
  - En Unity, EditMode 84/84.
  - `Placa_Agente.mat` sigue modificado localmente (el cambio automático de TMP); no se subió ni se descartó.
  - Posible siguiente: reentrenar M1 con descarga en marcha. Después, M2 (equilibrio de Nash).
