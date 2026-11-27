# Estado del proyecto y pendientes para continuar

27 de noviembre de 2026. Este documento basta para retomar el trabajo **solo con lo que está en los repositorios**: nada de lo necesario vive fuera de git.

## 1. Dónde quedó todo

| Bloque | Estado | Dónde |
|---|---|---|
| Primera y segunda entrega (A–F, estrategias, subasta, combustible, costo J, servidor) | Hecho | `docs/resultados_entrega2.md`, `docs/especificacion_*_entrega.md` |
| Terreno real (P0–P7): El Pueblito desde el KML, relieve, R12, R13, trace 2.3, Unity | Hecho | `docs/plan_terreno.md`, `docs/especificacion_terreno.md`, `docs/resultados_terreno.md` |
| M1: despacho aprendido (Q-learning y SARSA), también en Unity | Hecho | `docs/especificacion_mejoras.md`, `docs/resultados_mejoras.md` |
| Hileras reales y rutas de la industria (H0–H8 y H6: cabecera, pasadas, Dubins, A* con rumbo, trace 2.4, descarga en marcha) | Hecho | `docs/planes/plan_hileras_y_rutas.md`, `docs/resultados_hileras.md`, `docs/especificacion_terreno.md` §14 |
| Temas del curso: dónde se usa cada uno y con qué resultado | Hecho | `docs/temas_del_curso.md` |
| M2–M12 | **Pendiente** | `docs/plan_terreno.md` §«Mejoras»; plan detallado en `docs/planes/plan_terreno_detallado.md` §4b |

**Repositorios (ramas al cierre):**
- **`JoelMEsc/harvest_sim`:** `development` tiene todo (último merge: #40 y el PR de este documento). `main` todavía está en la segunda entrega (#19), así que hay que pasar `development` a `main` para la entrega final.
- **`GioMax102/harvest-simu-visualization`:** `dev` tiene todo (último merge: #10). Unity 6000.3.7f1.

**Números de referencia (G, El Pueblito, seed 0; G no tiene incertidumbre, así que las 20 seeds dan lo mismo):**

| Configuración | Ticks | Ocio |
|---|---|---|
| Movimiento por celdas, `anticipada_plus` | 1463 | 360 |
| Hileras, `anticipada_plus` | 1966 | 433 |
| Hileras + descarga en marcha, `anticipada_plus` (la mejor) | 1897 | 340 |
| Hileras, SARSA | 1869 | 406 |

## 2. Forma de trabajo acordada

- **Ramas:** se trabaja en `branch-joel` (harvest_sim) y en ramas de tema que salen de `dev` (Unity). Nunca un push directo a `development`, `dev` ni `main`.
- **Cambios:** un PR por paso o mejora, con CI en verde antes de hacer merge; quien abre el PR revisa el CI y hace el merge. Antes de empezar, sincronizar con `origin/development` y `origin/dev`, y revisar las ramas del equipo para no pisar trabajo ajeno.
- **Python es la única fuente de verdad:** Unity, el visor y el dashboard solo leen el trace o la API.
- **Toda mejora nueva queda desactivada por defecto,** para que A–F den lo mismo (`tests/test_regresion.py`). Las mejoras de terreno usan G como caso principal.
- **Planes:** sin reparto de tareas por persona; solo la técnica, los pasos, las pruebas y los riesgos.
- **Decisiones:** cada una va a `docs/decisiones.md`, con su alternativa y su porqué.
- **Datos externos:** todo dato externo lleva su fuente y su licencia (`geo.atribucion`).
- **Commits y PRs:** los commits hechos con Claude Code terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; las descripciones de PR, con la línea de Claude Code.
- **Ruido de Unity:** `Assets/Art/Materials/Placa_Agente.mat` aparece modificado solo (TextMeshPro cambia `_ScaleRatioC`). No se sube; si molesta, se restaura con git después de revisarlo.

## 3. Cómo correr y regenerar todo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .     # incluye shapely, pyproj y rasterio (mapa y relieve)
pytest                                                   # 786 pruebas
bash scripts/correr_todos.sh                             # A–G, gráficas, experimentos y dashboard (~2.5 min con 24 núcleos)
```

| Para | Comando |
|---|---|
| Verificar reglas en G (4 estrategias × 20 seeds) | `python tools/verificar_terreno.py [--movimiento hileras] [--descarga-en-marcha]` |
| Cualquier experimento | `python tools/correr_experimento.py config/experimentos/<nombre>.json --procesos 16` (lista y propósito en el README) |
| Reentrenar M1 (~21 min por algoritmo en G) | `python tools/entrenar_despacho.py config/<escenario>.json --algoritmo {qlearning,sarsa} --episodios 60 --epsilon 0.2`; las tablas quedan en `config/aprendizaje/` y se versionan |
| Regenerar el mapa desde el KML y el DEM (sin red) | `python tools/kml_a_mapa.py --figura` |
| Traces para Unity | `python tools/exportar_traces_unity.py ../harvest-simu-visualization/Assets/Data/Traces/<carpeta> --escenarios ... --estrategias ... --seed 0`; se documentan en `Assets/Data/Traces/README.md` |
| Pruebas de Unity (con el editor cerrado; si está abierto, copiar el proyecto a otra carpeta y correr ahí) | `Unity -batchmode -projectPath harvest-simu-visualization -runTests -testPlatform EditMode -testResults <xml>`; hoy 84/84 |
| Capturas de Unity | `Unity -batchmode -projectPath ... -executeMethod HarvestSim.Editor.HarvestCapture.CaptureFromCommandLine -captureDir <carpeta> -captureTrace <Assets/...json> -captureTick N [-captureFraction 0.5] [-captureHud] -quit` |

**Escenarios con mapa:**
- `escenario_g` (celdas);
- `escenario_g_hileras` (hileras; tiene tablas de M1);
- `escenario_g_en_marcha` (hileras + descarga en marcha).

## 4. Pendientes, en orden

### 4.1 Cerrar lo que quedó a medias

1. **Reentrenar M1 con descarga en marcha.** Las tablas de `escenario_g_hileras` aprendieron con la transferencia detenida. Con la descarga en marcha, SARSA baja el ocio (−9 %) pero termina 10 % más tarde.
    - Entrenar en `escenario_g_en_marcha`: `entrenar_despacho.py config/escenario_g_en_marcha.json`, unos 25 min con los dos algoritmos en paralelo.
    - Repetir `hileras_g_en_marcha.json` con las tablas nuevas.
2. **G con incertidumbre:** rendimiento variable y retrasos de mensajes. Hoy las 20 seeds de G dan lo mismo y los IC son 0. Agregar un `escenario_g_incertidumbre` (como `estrategias_incertidumbre.json` hace con D) y correr los experimentos de G.
3. **Pasar `development` a `main`** para la entrega final, con el README y `docs/autoevaluacion.md` al día.
4. **Unity:**
    - correr las pruebas PlayMode, que solo se han corrido en EditMode;
    - revisar la panorámica negra de la captura en modo batch (también pasa con traces 2.2; es de la herramienta de captura, no de los datos).

### 4.2 Mejoras M2–M12 (en este orden; el detalle está en `docs/plan_terreno.md` §«Mejoras»)

| # | Mejora | Idea |
|---|---|---|
| M2 | Equilibrio de Nash | La competencia de dos carros por un servicio como un juego de «compartir contra acaparar»: pagos sacados de corridas, equilibrios con `nashpy` y precio de la anarquía. **Es el objetivo del curso que falta** (`docs/temas_del_curso.md` §8). |
| M3 | Fallas de comunicación visibles | Pérdida y retraso de mensajes, mostrados en Unity |
| M4 | Variables en tiempo real por WebSockets | |
| M5 | Logs accesibles para análisis | |
| M6 | Dashboard web por túnel | |
| M7 | Clima | |
| M8 | Análisis financiero integral | |
| M9 | Análisis desde imagen satelital | |
| M10 | Visión computacional | |
| M11 | Reportes financieros con RAG | |
| M12 | Rust para eficiencia | |

Reglas para todas: desactivadas por defecto, una rama y un PR por mejora, con pruebas, y G como caso principal.

### 4.3 Propuestas de la retro de la semana 3 (profesor), todavía sin hacer

Las 4 preguntas de la retro ya están respondidas: la 1, la 2 y la 4 en `docs/resultados_entrega2.md`; la 3 con M1. Además, la retro propuso para nuestro proyecto:

- **Ideas de aprendizaje automático:**
    1. tiempo de ciclo del carro (regresión);
    2. probabilidad de llenado en k ticks (clasificación);
    3. cuantiles de espera (p90);
    4. regímenes de operación (k-means);
    5. importancia de variables con random forest;
    6. frontera de parámetros con proceso gaussiano;
    7. anomalías en traces (isolation forest);
    8. predicción de bloqueos cerca de la bodega;
    9. mapa de rendimiento por celda;
    10. modelo sustituto del número de carros.
- **Ideas de Q-learning** (M1 ya cubre el «cuándo pedir»):
    1. atención de varias tolvas (cuál aviso atender);
    2. celda donde estacionar el carro;
    3. cuándo salir de la bodega;
    4. asignación carro–cosechadora;
    5. orden de cosecha dentro de la serpentina.
- **Advertencia de la retro:** el aprendizaje entrenado con el propio simulador aprende sus supuestos. Por eso siempre se compara contra una regla simple, como se hizo en M1.

### 4.4 Limitaciones conocidas (posibles mejoras)

- **Velocidad del carro:** el carro avanza una celda por tick, igual que la cosechadora, aunque en el campo va a ~10 km/h. Su velocidad solo cuenta en los giros (`docs/resultados_hileras.md`).
- **Supuestos sin calibrar:** el radio de giro (7.5 y 6 m) y las velocidades de `config.maquinas` son valores típicos. Medirlos con una máquina real daría números absolutos más confiables.
- **Fields2Cover:** se usó como referencia de diseño, sin compilarlo; en PyPI solo hay código fuente y exige GDAL y OR-tools. Compilarlo permitiría comparar numéricamente cabeceras, pasadas y largos de vuelta con los nuestros.
- **DEM:** es un modelo de superficie (DSM), así que en la orilla del predio sobreestima la pendiente.
- **Compactación:** cuenta metros, no peso, ni cuántas veces se pasa por la misma celda.
- **Recompensa de M1:** solo mira el ocio de la cosechadora que decide, no el combustible del carro.
- **Temas del curso sin usar** (`docs/temas_del_curso.md` §8): juegos repetidos y bayesianos, elección social, estigmergia, *blackboard*, *broadcast* y shaders.

## 5. Planes e historia

| Documento | Qué es |
|---|---|
| `docs/planes/plan_terreno_detallado.md` | Plan completo del terreno y de las mejoras M1–M12, con el estado inicial y las decisiones de diseño |
| `docs/planes/plan_hileras_y_rutas.md` | Investigación (Fields2Cover, AgOpenGPS, Dubins, descarga en marcha) y fases H0–H8 |
| `docs/planes/plan_m1_unity.md` | Cómo se llevó M1 a Unity |
| `docs/planes/plan_datos_entrega2.md`, `plan_integracion_entrega2.md` | Planes de la segunda entrega (históricos) |
| `docs/planes/bitacora.md` | Bitácora paso a paso de terreno, M1 e hileras: qué se hizo, qué falló y cómo se corrigió |
| `docs/decisiones.md` | Todas las decisiones de diseño |
