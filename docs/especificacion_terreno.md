# Especificación: terreno realista (forma real del campo, caminos y relieve)

> Contrato entre la simulación (Python) y la visualización (Unity) para simular y ver el cultivo real de **El Pueblito, Teocaltiche, Jalisco**.
> Todo lo de aquí es **opcional y está desactivado por defecto**: los escenarios A–F no cambian (`tests/test_regresion.py`).

## 1. Por qué entra por Python

Python es la única fuente de verdad y Unity solo reproduce el trace (especificación de la segunda entrega §14). Si Unity calculara las pasadas desde el KML, habría dos versiones de la cosecha: la que simula Python y la que dibuja Unity. Por eso:

1. el KML (trazado en Google Earth, en `harvest-simu-visualization/docs/cultivo/`) se convierte en Python en un **mapa de celdas** para la simulación;
2. la simulación corre sobre ese mapa;
3. el trace **2.3** lleva el mapa, la geometría real y el relieve;
4. Unity dibuja con eso, sin calcular nada.

## 2. Archivos

| Archivo | Qué es |
|---|---|
| `config/mapas/el_pueblito.kml` | Copia del KML de `docs/cultivo/harvestisim.kml` (la fuente) |
| `config/mapas/el_pueblito.yaml` | Configuración del convertidor: tamaño de celda, tolerancias, ancho de camino y DEM |
| `config/mapas/el_pueblito.json` | Mapa generado (§5). **No se edita a mano** |
| `config/escenario_g.json` | Escenario G: agentes, capacidades y tasas, más `"mapa": "mapas/el_pueblito.json"` |
| `tools/kml_a_mapa.py` | Genera el mapa desde el KML (y desde el DEM, si se pide) |
| `src/harvest_sim/mapa/` | Lector del KML, proyección, soldadura de caminos, rasterizado y pasadas |

## 3. Convenciones del KML

Son las de `docs/cultivo/prompt_claude_code_cultivo.md` (Oswaldo). El nombre del *Placemark* se compara en minúsculas y sin acentos, y solo cuenta cómo empieza:

| Empieza con | Geometría | Significado |
|---|---|---|
| `cultivo`, `lote` | Polígono | Lote sembrado (se cosecha). `rumbo=45` en el nombre fija el rumbo de sus surcos |
| `camino`, `brecha` | Línea | Camino de terracería (transitable, no se cosecha) |
| `camino`, `brecha` | Polígono | Zona de camino |
| `obstaculo` | Polígono o punto | Obstáculo (arboleda, poste, construcción) |
| `surco`, `guia` | Línea | Guía del rumbo de los surcos del lote donde cae su punto medio |
| `bodega` | Punto | **Nuevo:** dónde se descarga el grano |
| `base` | Punto | **Nuevo:** dónde se estaciona una máquina (uno por punto) |
| otro nombre | | Polígono → obstáculo; línea → camino |

Si el KML no trae `bodega` ni `base`, el convertidor los pone en un **patio** junto al camino más cercano a la entrada del lote más grande (§4.5).

## 4. Conversión del KML al mapa

### 4.1 Proyección y orientación

- Las coordenadas geográficas pasan a **UTM 13N (EPSG:32613)** con `pyproj`, la misma proyección del DEM.
- La cuadrícula se gira con el **rumbo común de los surcos**: el promedio, ponderado por área, del rumbo de cada lote (guía `surco`, `rumbo=` en el nombre, o automático si no hay ninguno). El eje x de la cuadrícula sigue los surcos, así que **una fila de celdas es una pasada**.
- Las celdas son cuadradas, de `tamano_celda_m` (12 m por defecto: un cabezal maicero de 16 hileras a 76 cm).

### 4.2 Soldadura de caminos

Los caminos del KML se trazan a mano y en segmentos que no se tocan exactamente. Antes de rasterizar:

1. Un extremo de camino que queda a menos de `tolerancia_union_m` (5 m) de otro camino se une al punto más cercano de ese camino.
2. Un extremo que queda a esa distancia de un lote se une a su orilla: es una **entrada** del lote.
3. Cada unión se imprime y queda en el mapa (`soldaduras`): qué camino, con cuál y cuántos metros.
4. La red soldada debe ser **una sola pieza**. Si queda algo suelto, el convertidor falla y dice qué camino y a qué distancia: eso es un error de trazo y **se corrige en el KML**.

### 4.3 Tipos de celda

Cada celda es de un solo tipo, con esta prioridad:

| Prioridad | Tipo | Regla |
|---|---|---|
| 1 | `obstaculo` | Toca un obstáculo ampliado `margen_obstaculo_m` (3 m) |
| 2 | `camino` | La línea central de un camino pasa por la celda (todas las celdas que toca la línea, para que la red quede conectada en vecindad 4) |
| 3 | `campo` | Al menos el 50 % del área de la celda cae en un lote |
| 4 | `patio` | Bodega y bases (§4.5) |
| 5 | `fuera_de_campo` | Todo lo demás |

Cada celda de campo guarda su lote (A, B o C).

**Validaciones** (el convertidor falla si no se cumplen):
- el área cosechable difiere del área de los lotes en menos de 5 %;
- todo el campo es alcanzable desde la bodega por camino, patio o campo;
- cada lote toca al menos una celda de camino.

### 4.4 Rumbo por lote

Sigue el algoritmo de `PasadasCultivo.cs` (portado a `mapa/pasadas.py`):
1. `rumbo=` manual;
2. si no, la guía `surco` que cae en el lote;
3. si no, el rumbo de 0 a 180° (en pasos de 0.5°) que da menos pasadas.

El rumbo se normaliza a 0–180°.

### 4.5 Patio de servicio

La bodega y las bases van en celdas que no son campo ni camino, pegadas al camino y lo más cerca posible del punto de la bodega. No pueden ir sobre un camino: si el camino es de una celda de ancho, una máquina estacionada lo taparía. Las celdas del patio son transitables para todos (la bodega sigue prohibida para la cosechadora, R9). Se generan `n_bases` bases (8 por defecto); el mundo asigna las primeras a los carros y las siguientes a las cosechadoras.

## 5. Formato del mapa (`config/mapas/*.json`)

```json
{
  "nombre": "el_pueblito",
  "fuente": {"kml": "el_pueblito.kml", "sha256": "…"},
  "tamano_celda_m": 12.0,
  "ancho": 80, "alto": 64,
  "bodega": [x, y],
  "bases": [[x, y], …],
  "obstaculos": [[x, y], …],
  "caminos": [[x, y], …],
  "fuera_de_campo": [[x, y], …],
  "lotes": {"A": [[x, y], …], "B": …, "C": …},
  "altura_m": [[…], …],
  "geo": {
    "epsg": 32613,
    "origen_utm": [E, N],
    "rumbo_grados": 52.4,
    "atribucion": "…",
    "formas": {
      "lotes": {"A": [[x_m, y_m], …], …},
      "obstaculos": [[[x_m, y_m], …], …],
      "caminos": [[[x_m, y_m], …], …]
    }
  },
  "soldaduras": [{"camino": "…", "con": "…", "metros": 3.9}, …]
}
```

- `altura_m` es opcional (§8).
- `geo.formas` está en **metros del marco de la cuadrícula**: el origen es la esquina de la celda (0, 0), x a lo largo de los surcos y y perpendicular.
- `geo.origen_utm` = (E0, N0) y `geo.rumbo_grados` = θ (desde el norte, en sentido horario) permiten volver a UTM. El eje x de la cuadrícula es la dirección de los surcos, (sin θ, cos θ) en (E, N), y el eje y es ese mismo eje girado 90° a la izquierda, (−cos θ, sin θ):
  `E = E0 + x·sin θ − y·cos θ`, `N = N0 + x·cos θ + y·sin θ` (x e y en metros del marco de la cuadrícula).

## 6. Trace 2.3

Solo agrega campos a la versión 2.2. `TraceBuilder` escribe `"2.3"` **solo si el mundo tiene mapa**; A–F siguen escribiendo `"2.2"`, byte a byte igual que antes. El validador acepta 2.1, 2.2 y 2.3.

| Campo de `mundo` | Tipo | Qué es |
|---|---|---|
| `tamano_celda_m` | número > 0 | Metros por celda |
| `caminos` | lista de `[x, y]` | Celdas transitables que no se cosechan (caminos y patio) |
| `fuera_de_campo` | lista de `[x, y]` | Celdas que nadie pisa (fuera del predio) |
| `lotes` | `{nombre: [[x, y], …]}` | Celdas de campo de cada lote |
| `altura_m` | matriz alto × ancho | Altura de cada celda en metros (relieve) |
| `geo` | objeto | Como en el mapa (§5) |

- **Campo cosechable con 2.3:** todas las celdas menos obstáculos, `fuera_de_campo`, `caminos`, bodega y bases. Con 2.1 y 2.2 sigue la regla de siempre: filas y ≥ 1 sin obstáculos.
- En 2.3 los obstáculos pueden estar en cualquier fila; la fila 0 ya no es especial.
- La sección `config` del trace guarda `mapa` como `{"archivo", "sha256"}`, sin copiar el contenido (ya está en `mundo`).

## 7. Reglas nuevas

**R12. Nadie sale del predio.** Las celdas `fuera_de_campo` son fijas para todos, como los obstáculos (R10). Se aplica con `bloqueadas_fijas`.

**R13. No se pisa el cultivo en pie.** Solo aplica con mapa y con `politica.respetar_cultivo: true` (activado en G, `false` por defecto):

| Celda | Cosechadora | Carro |
|---|---|---|
| Camino o patio | Sí | Sí |
| Campo ya cosechado (rastrojo) | Sí | Sí |
| Campo sin cosechar | Solo cosechándolo, en el orden de su camino | **No** |
| Obstáculo o fuera de campo | No | No |
| Bodega | No (R9) | Sí |

- `mundo.bloqueadas_para(agent_id)` devuelve las celdas fijas más, para los carros, el campo sin cosechar. El conjunto en pie se actualiza con cada cosecha.
- El carro se estaciona junto a la cosechadora en rastrojo o camino. La celda de atrás en la pasada siempre está cosechada.
- Cuando la ruta de un carro se alarga por rodear el cultivo, se registra `RESTRICCION` con `regla: "R13_cultivo_en_pie"`, una por tramo.
- En traslado, la cosechadora prefiere caminos y rastrojo. Si no hay ruta así (un borde irregular del lote), cruza su propio cultivo en pie; eso se cuenta y en G debe ser cero o casi.
- Si un carro no tiene ruta, rechaza la llamada con `sin_ruta`.

## 8. Relieve

- `tools/kml_a_mapa.py --dem <COG>` lee el **Copernicus DEM GLO-30** (cuadro N21 W103) y lo remuestrea en bilineal al centro de cada celda, en el marco de la cuadrícula. Solo lee la ventana de la zona del COG.
- `altura_m` va en el mapa y en `mundo`.
- **Consumo por pendiente:** `combustible.factor_pendiente` (0 por defecto, sin efecto). Al subir de una celda a otra, el consumo por celda se multiplica por `1 + f · pendiente_%/100`; al bajar no se descuenta. La idea sale de ASABE D497 (resistencia por pendiente), y el valor de f es un supuesto documentado.

## 9. Zonas y orden de las pasadas (solo con mapa)

- **Zonas:** cada cosechadora recibe lotes completos, repartidos por número de celdas (el más grande a la que lleva menos). Si hay más cosechadoras que lotes, el lote más grande se parte en bandas de filas.
- **Orden dentro de un lote** (boustrophedon):
  - empieza en la fila de una orilla (la de y mínima o la de y máxima) y en el extremo más cercano a una celda de camino;
  - cada fila siguiente empieza en el extremo más cercano al final de la anterior;
  - los lotes de una cosechadora se recorren del más cercano a la bodega al más lejano.
- Sin mapa (A–F) sigue la serpentina de v0.1.

## 10. Unity

- Acepta 2.1, 2.2 y 2.3.
- Dibuja **en el marco de la cuadrícula**: x a lo largo de los surcos, sin rotar el mundo. `geo.rumbo_grados` solo orienta el norte y el sol.
- El Terrain sale de `altura_m`; las celdas, el maíz y las máquinas se apoyan en esa altura.
- Las mallas de lotes, caminos y obstáculos salen de `geo.formas`, con el código de mallas de `CultivoDesdeKML.cs`.
- Las celdas `fuera_de_campo` no llevan maíz.
- La atribución del DEM va en el HUD.

## 11. Pruebas mínimas

| Prueba | Verifica |
|---|---|
| Regresión A–F | Las mismas métricas que v0.1 y versión 2.2 |
| `test_mapa_area` | Área cosechable dentro del ±5 % del KML |
| `test_soldadura` | El KML actual queda en una sola red; un hueco de 20 m falla con nombre y distancia; con tolerancia 0 queda partido |
| `test_rumbo` | El rumbo de cada guía coincide con `PasadasCultivo.cs` |
| `test_validador_23` | 2.1, 2.2 y 2.3 validan; un 2.3 con un `camino` fuera del mapa falla |
| `test_bloqueadas_para` | Para el carro incluye el cultivo en pie y lo libera al cosecharse; la cosechadora no lo incluye; con `respetar_cultivo: false` nada cambia |
| Integración G | Termina con 4 estrategias × 20 seeds, 0 colisiones, nadie en `fuera_de_campo` (R12) y ningún carro sobre cultivo en pie (R13) |
| Relieve | Las alturas coinciden con el DEM en puntos de control; con factor 0 el consumo es igual |
