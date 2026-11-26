"""Del KML del cultivo al mapa de celdas de la simulación.  [Oswaldo / Joel]

Especificación: docs/especificacion_terreno.md §4 y §5. Pasos:

1. Lee el KML (convenciones de Oswaldo) y proyecta todo a UTM 13N (EPSG:32613).
2. Rumbo de cada lote (manual, guía o automático; `pasadas.py`) y rumbo común ponderado por área.
3. Suelda los caminos trazados en segmentos (tolerancia), con reporte, y exige una sola red.
4. Gira la cuadrícula con el rumbo común (x a lo largo de los surcos: una fila es una pasada) y clasifica
   cada celda: obstáculo > camino > campo (>= fracción de un lote) > fuera de campo.
5. Pone la bodega y las bases en un patio junto al camino (no sobre él).
6. Valida: área cosechable dentro del ±5 % de los lotes, todo el campo alcanzable desde la bodega y cada
   lote tocando un camino.

El resultado es un dict con el formato de §5; `tools/kml_a_mapa.py` lo escribe en `config/mapas/`.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from . import kml as K
from .pasadas import area_firmada, generar_pasadas, rumbo_de_lote

EPSG_UTM = 32613  # UTM 13N: Teocaltiche, Jalisco (-102.47°) cae en la zona 13
ATRIBUCION_KML = "Trazo del cultivo de El Pueblito (Teocaltiche, Jalisco) hecho por el equipo en Google Earth."

PARAMETROS_POR_DEFECTO = {
    "tamano_celda_m": 12.0,       # un cabezal maicero de 16 hileras a 76 cm
    "tolerancia_union_m": 5.0,    # soldadura de caminos: un poco más que el ancho de un camino
    "ancho_camino_m": 4.0,
    "margen_obstaculo_m": 3.0,
    "fraccion_campo": 0.5,        # una celda es campo si al menos esta fracción cae en un lote
    "n_bases": 8,
    "margen_celdas": 1,           # celdas de margen alrededor de todo
    "tolerancia_area": 0.05,      # ±5 % entre el área cosechable y la de los lotes (criterio C1)
    "radio_poste_m": 0.5,
}


class ErrorMapa(ValueError):
    """El KML no se puede convertir (camino suelto, lote sin entrada, área fuera de tolerancia...)."""


@dataclass
class Marco:
    """Marco de la cuadrícula: x a lo largo de los surcos (rumbo θ), y = x girado 90° a la izquierda."""
    e0: float
    n0: float
    rumbo: float

    def a_cuadricula(self, e: float, n: float) -> tuple[float, float]:
        t = math.radians(self.rumbo)
        de, dn = e - self.e0, n - self.n0
        return de * math.sin(t) + dn * math.cos(t), -de * math.cos(t) + dn * math.sin(t)

    def a_utm(self, x: float, y: float) -> tuple[float, float]:
        t = math.radians(self.rumbo)
        return self.e0 + x * math.sin(t) - y * math.cos(t), self.n0 + x * math.cos(t) + y * math.sin(t)


def _nombre_corto(nombre: str) -> str:
    """'cultivo_loteA' -> 'A'; 'lote norte' -> 'norte'; si no, el nombre completo."""
    n = K.normalizar(nombre).split(" rumbo")[0].strip()
    for prefijo in ("cultivo_lote", "cultivo lote", "cultivo_", "cultivo ", "lote_", "lote "):
        if n.startswith(prefijo) and len(n) > len(prefijo):
            return n[len(prefijo):].strip().upper() if len(n) - len(prefijo) <= 2 else n[len(prefijo):].strip()
    return n


def rumbo_comun(rumbos_y_areas: list[tuple[float, float]]) -> float:
    """Promedio ponderado de rumbos axiales (0–180): se promedian los ángulos dobles."""
    sx = sum(a * math.cos(math.radians(2 * r)) for r, a in rumbos_y_areas)
    sy = sum(a * math.sin(math.radians(2 * r)) for r, a in rumbos_y_areas)
    return (math.degrees(math.atan2(sy, sx)) / 2) % 180.0


def soldar_caminos(caminos: dict[str, LineString], lotes: dict[str, Polygon], tolerancia: float):
    """Une los extremos sueltos (§4.2). Devuelve (conectores, soldaduras, componentes).

    - conectores: {nombre: LineString} de cada unión (camino→camino o camino→orilla de un lote);
    - soldaduras: [{"camino", "con", "metros"}] para el reporte;
    - componentes: lista de conjuntos de nombres de camino conectados entre sí (debe ser 1)."""
    conectores, soldaduras = {}, []
    for nombre, linea in caminos.items():
        for extremo in (Point(linea.coords[0]), Point(linea.coords[-1])):
            otros = [(extremo.distance(g), o) for o, g in caminos.items() if o != nombre]
            if otros:
                dist, otro = min(otros)
                if 0 < dist <= tolerancia:
                    destino = nearest_points(extremo, caminos[otro])[1]
                    conectores[f"{nombre}→{otro}"] = LineString([extremo, destino])
                    soldaduras.append({"camino": nombre, "con": otro, "metros": round(dist, 2)})
                    continue
                if dist == 0:
                    continue
            cerca = [(extremo.distance(p.exterior), l) for l, p in lotes.items()]
            if cerca:
                dist, lote = min(cerca)
                if dist <= tolerancia:
                    destino = nearest_points(extremo, lotes[lote].exterior)[1]
                    if dist > 0:
                        conectores[f"{nombre}→lote {lote}"] = LineString([extremo, destino])
                    soldaduras.append({"camino": nombre, "con": f"lote {lote}", "metros": round(dist, 2)})
    # componentes conexas de la red (caminos + conectores)
    piezas = dict(caminos) | conectores
    nombres = list(piezas)
    vecinos = {n: set() for n in nombres}
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            if piezas[a].distance(piezas[b]) < 1e-6:
                vecinos[a].add(b)
                vecinos[b].add(a)
    componentes, vistos = [], set()
    for n in nombres:
        if n in vistos:
            continue
        comp, cola = set(), deque([n])
        while cola:
            x = cola.popleft()
            if x in comp:
                continue
            comp.add(x)
            cola.extend(vecinos[x] - comp)
        vistos |= comp
        componentes.append({c for c in comp if c in caminos})
    return conectores, soldaduras, componentes


def convertir(ruta_kml: str | Path, parametros: dict | None = None) -> tuple[dict, list[str]]:
    """Convierte el KML en el mapa (§5). Devuelve (mapa, reporte). Lanza ErrorMapa si no cumple §4."""
    p = {**PARAMETROS_POR_DEFECTO, **(parametros or {})}
    s = float(p["tamano_celda_m"])
    reporte: list[str] = []
    elementos = K.leer_kml(ruta_kml)
    utm = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG_UTM}", always_xy=True)

    def proyectar(coords):
        return [utm.transform(lon, lat) for lon, lat in coords]

    lotes_e = [e for e in elementos if e.tipo == K.LOTE and e.geometria == K.POLIGONO and len(e.coordenadas) >= 3]
    if not lotes_e:
        raise ErrorMapa("el KML no tiene lotes (polígonos cuyo nombre empieza con 'cultivo' o 'lote')")
    lotes_utm = {_nombre_corto(e.nombre): proyectar(e.coordenadas) for e in lotes_e}
    guias = [proyectar(e.coordenadas) for e in elementos if e.tipo == K.GUIA and e.geometria == K.LINEA]
    obs_poligonos = [proyectar(e.coordenadas) for e in elementos
                     if e.tipo == K.OBSTACULO and e.geometria == K.POLIGONO and len(e.coordenadas) >= 3]
    obs_lineas = [proyectar(e.coordenadas) for e in elementos if e.tipo == K.OBSTACULO and e.geometria == K.LINEA]
    obs_puntos = [proyectar(e.coordenadas)[0] for e in elementos if e.tipo == K.OBSTACULO and e.geometria == K.PUNTO]
    caminos_utm = {}
    for i, e in enumerate(x for x in elementos if x.tipo == K.CAMINO):
        nombre = e.nombre if e.nombre not in caminos_utm else f"{e.nombre} ({i + 1})"
        if e.geometria == K.LINEA and len(e.coordenadas) >= 2:
            caminos_utm[nombre] = LineString(proyectar(e.coordenadas))
        elif e.geometria == K.POLIGONO and len(e.coordenadas) >= 3:
            caminos_utm[nombre] = Polygon(proyectar(e.coordenadas)).exterior
    puntos = {t: [utm.transform(*e.coordenadas[0]) for e in elementos if e.tipo == t and e.geometria == K.PUNTO]
              for t in (K.BODEGA, K.BASE)}

    # --- 2. Rumbo de cada lote (algoritmo de PasadasCultivo.cs) y rumbo común -------------------
    pasadas_p = {"ancho": s / 2, "cabecera": 8.0, "margen": p["margen_obstaculo_m"], "largo_min": 5.0,
                 "radio_poste": p["radio_poste_m"]}
    info_lotes = {}
    manuales = {_nombre_corto(e.nombre): e.rumbo_manual for e in lotes_e}
    for nombre, poli in lotes_utm.items():
        rumbo, modo = rumbo_de_lote(poli, manuales[nombre], guias, obs_poligonos, **pasadas_p)
        area = abs(area_firmada(poli))
        pasadas = generar_pasadas(poli, rumbo, obs_poligonos, obs_lineas, obs_puntos, **pasadas_p)
        info_lotes[nombre] = {"rumbo_grados": round(rumbo, 2), "modo_rumbo": modo, "area_ha": round(area / 1e4, 3),
                              "pasadas_oswaldo": len(pasadas)}
        reporte.append(f"lote {nombre}: {area / 1e4:.2f} ha, rumbo {rumbo:.1f}° ({modo}), "
                       f"{len(pasadas)} pasadas de {s / 2:.0f} m (algoritmo de PasadasCultivo)")
    rumbo = rumbo_comun([(i["rumbo_grados"], i["area_ha"]) for i in info_lotes.values()])
    desvio = max(abs(((i["rumbo_grados"] - rumbo + 90) % 180) - 90) for i in info_lotes.values())
    reporte.append(f"rumbo común de los surcos: {rumbo:.2f}° (desvío máximo de un lote: {desvio:.1f}°)")

    # --- 3. Soldadura de caminos -------------------------------------------------------------------
    lotes_geo = {n: Polygon(c) for n, c in lotes_utm.items()}
    conectores, soldaduras, componentes = soldar_caminos(caminos_utm, lotes_geo, p["tolerancia_union_m"])
    for sd in soldaduras:
        reporte.append(f"soldadura: {sd['camino']} con {sd['con']} ({sd['metros']} m)")
    if len(componentes) != 1:
        principal = max(componentes, key=len)
        red = unary_union([caminos_utm[c] for c in principal])
        sueltos = sorted((round(caminos_utm[c].distance(red), 1), c) for comp in componentes if comp is not principal
                         for c in comp)
        detalle = "; ".join(f"{c} a {d} m de la red" for d, c in sueltos)
        raise ErrorMapa(f"la red de caminos queda partida en {len(componentes)} piezas después de soldar con "
                        f"{p['tolerancia_union_m']} m: {detalle}. Corrígelo en el KML.")

    # --- 4. Cuadrícula girada y tipos de celda --------------------------------------------------
    todo = list(lotes_utm.values()) + [list(g.coords) for g in caminos_utm.values()] + obs_poligonos + obs_lineas
    todo_pts = [pt for g in todo for pt in g] + obs_puntos + puntos[K.BODEGA] + puntos[K.BASE]
    ref = Marco(0.0, 0.0, rumbo)
    uv = [ref.a_cuadricula(e, n) for e, n in todo_pts]
    m = p["margen_celdas"] * s
    u0, v0 = min(u for u, _ in uv) - m, min(v for _, v in uv) - m
    ancho = math.ceil((max(u for u, _ in uv) + m - u0) / s)
    alto = math.ceil((max(v for _, v in uv) + m - v0) / s)
    marco = Marco(*ref.a_utm(u0, v0), rumbo)

    def a_marco(coords):
        return [marco.a_cuadricula(e, n) for e, n in coords]

    lotes_m = {n: Polygon(a_marco(c)) for n, c in lotes_utm.items()}
    obstaculos_m = [Polygon(a_marco(c)) for c in obs_poligonos] + \
                   [LineString(a_marco(c)).buffer(p["radio_poste_m"]) for c in obs_lineas] + \
                   [Point(marco.a_cuadricula(*c)).buffer(p["radio_poste_m"]) for c in obs_puntos]
    red_m = {n: LineString(a_marco(list(g.coords))) for n, g in (caminos_utm | conectores).items()}
    # Obstáculo: la celda toca el obstáculo. Con celdas de 12 m, media celda ya da más que el margen de 3 m
    # que deja la cosechadora; ampliarlo además volvería obstáculo a celdas que apenas lo rozan.
    obstaculo_amp = unary_union(obstaculos_m) if obstaculos_m else None
    camino_amp = unary_union([g.buffer(p["ancho_camino_m"] / 2) for g in red_m.values()])
    linea_central = unary_union(list(red_m.values()))
    nucleo = s / 4  # el centro de la celda: la mitad central en cada eje
    arbol_lotes = STRtree(list(lotes_m.values()))
    nombres_lotes = list(lotes_m)

    tipo: dict[tuple[int, int], str] = {}
    lote_de: dict[tuple[int, int], str] = {}
    for y in range(alto):
        for x in range(ancho):
            celda = box(x * s, y * s, (x + 1) * s, (y + 1) * s)
            if obstaculo_amp is not None and celda.intersects(obstaculo_amp):
                tipo[(x, y)] = "obstaculo"
                continue
            mejor, frac = None, 0.0
            for i in arbol_lotes.query(celda):
                f = celda.intersection(lotes_m[nombres_lotes[i]]).area / (s * s)
                if f > frac:
                    mejor, frac = nombres_lotes[i], f
            es_campo = mejor is not None and frac >= p["fraccion_campo"]
            # Un camino le gana al campo solo si su línea central pasa por el centro de la celda: un camino
            # que corre por la orilla del lote no se come las celdas de campo que apenas roza.
            centro = box(x * s + nucleo, y * s + nucleo, (x + 1) * s - nucleo, (y + 1) * s - nucleo)
            if celda.intersects(camino_amp) and (not es_campo or centro.intersects(linea_central)):
                tipo[(x, y)] = "camino"
            elif es_campo:
                tipo[(x, y)] = "campo"
                lote_de[(x, y)] = mejor
            else:
                tipo[(x, y)] = "fuera"

    def vecinos4(c):
        x, y = c
        return [v for v in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)) if v in tipo]

    # Reparación de la red en celdas: el camino de la orilla puede quedar cortado donde respeta el campo. Cada
    # pieza suelta se une a la principal por el puente más corto de celdas de campo (BFS), y solo esas celdas
    # pasan a camino. La red geométrica ya es una sola pieza (soldadura), así que los puentes son cortos.
    def componentes_camino():
        cam = {c for c, t in tipo.items() if t == "camino"}
        comps, vistos = [], set()
        for c in sorted(cam):
            if c in vistos:
                continue
            comp, cola = {c}, deque([c])
            while cola:
                a = cola.popleft()
                for v in vecinos4(a):
                    if v in cam and v not in comp:
                        comp.add(v)
                        cola.append(v)
            vistos |= comp
            comps.append(comp)
        return sorted(comps, key=len, reverse=True)

    puentes = 0
    comps = componentes_camino()
    while len(comps) > 1:
        principal, resto = comps[0], set().union(*comps[1:])
        origen = min(comps[1:], key=len)
        padre = {c: None for c in origen}
        cola, llegada = deque(origen), None
        while cola and llegada is None:
            a = cola.popleft()
            for v in vecinos4(a):
                if v in padre:
                    continue
                if v in principal or (v in resto and v not in origen):
                    padre[v], llegada = a, v
                    break
                if tipo[v] == "campo":
                    padre[v] = a
                    cola.append(v)
        if llegada is None:
            break  # no hay puente por campo: lo detecta la validación de abajo
        c = padre[llegada]
        while c is not None and c not in origen:
            tipo[c] = "camino"
            lote_de.pop(c, None)
            puentes += 1
            c = padre[c]
        comps = componentes_camino()
    if puentes:
        reporte.append(f"red de caminos en celdas: {puentes} celdas de campo pasan a camino para unir las piezas")
    if len(comps) > 1:
        raise ErrorMapa(f"los caminos en celdas quedan en {len(comps)} piezas y no se pueden unir por el campo")

    # --- 5. Patio: bodega y bases junto al camino ------------------------------------------------
    def celda_de(e, n):
        x, y = marco.a_cuadricula(e, n)
        return (min(max(int(x // s), 0), ancho - 1), min(max(int(y // s), 0), alto - 1))

    caminos_c = {c for c, t in tipo.items() if t == "camino"}
    junto_al_camino = sorted(c for c, t in tipo.items() if t == "fuera" and any(v in caminos_c for v in vecinos4(c)))
    if not junto_al_camino:
        raise ErrorMapa("no hay celdas fuera de campo junto a un camino para poner la bodega y las bases")
    if puntos[K.BODEGA]:
        ancla = celda_de(*puntos[K.BODEGA][0])
        reporte.append("bodega: del punto 'bodega' del KML")
    else:
        mayor = max(lotes_m, key=lambda n: lotes_m[n].area)
        celdas_mayor = [c for c, lt in lote_de.items() if lt == mayor]
        entradas = [c for c in caminos_c if any(lote_de.get(v) == mayor for v in vecinos4(c))]
        if not entradas:
            raise ErrorMapa(f"el lote {mayor} no toca ningún camino")
        ancla = min(entradas, key=lambda c: (min(abs(c[0] - d[0]) + abs(c[1] - d[1]) for d in celdas_mayor), c))
        reporte.append(f"bodega: sin punto 'bodega' en el KML; junto a la entrada del lote más grande ({mayor})")
    dist = {ancla: 0}
    cola = deque([ancla])
    while cola:  # distancia por camino desde el ancla
        c = cola.popleft()
        for v in vecinos4(c):
            if v not in dist and (v in caminos_c or v == ancla):
                dist[v] = dist[c] + 1
                cola.append(v)

    def cercania(c):
        por_camino = min((dist.get(v, 10 ** 6) for v in vecinos4(c) if v in caminos_c), default=10 ** 6)
        return (por_camino, abs(c[0] - ancla[0]) + abs(c[1] - ancla[1]), c)

    candidatos = sorted(junto_al_camino, key=cercania)
    bodega = candidatos[0]
    if puntos[K.BASE]:
        bases = []
        for e, n in puntos[K.BASE]:
            c = celda_de(e, n)
            libres = [d for d in candidatos if d != bodega and d not in bases]
            bases.append(c if c in libres else min(libres, key=lambda d: abs(d[0] - c[0]) + abs(d[1] - c[1])))
    else:
        bases = candidatos[1:1 + p["n_bases"]]
    if len(bases) < p["n_bases"] and not puntos[K.BASE]:
        raise ErrorMapa(f"solo caben {len(bases)} bases junto al camino; se pidieron {p['n_bases']}")
    for c in [bodega] + bases:
        tipo[c] = "patio"

    # --- 6. Validaciones -----------------------------------------------------------------------
    campo = {c for c, t in tipo.items() if t == "campo"}
    # Área real cosechable: los lotes menos los obstáculos que caen dentro (el KML no tiene huecos: la
    # arboleda del lote C está dentro de su polígono).
    area_lotes = unary_union(list(lotes_m.values())).difference(obstaculo_amp).area if obstaculo_amp is not None \
        else unary_union(list(lotes_m.values())).area
    area_celdas = len(campo) * s * s
    error_area = (area_celdas - area_lotes) / area_lotes
    reporte.append(f"área: lotes {area_lotes / 1e4:.2f} ha, celdas de campo {area_celdas / 1e4:.2f} ha "
                   f"({len(campo)} celdas, {100 * error_area:+.1f} %)")
    if abs(error_area) > p["tolerancia_area"]:
        raise ErrorMapa(f"el área cosechable difiere {100 * error_area:+.1f} % del área de los lotes "
                        f"(tolerancia ±{100 * p['tolerancia_area']:.0f} %)")
    transitables = campo | caminos_c | {bodega} | set(bases)
    alcanzadas, cola = {bodega}, deque([bodega])
    while cola:
        c = cola.popleft()
        for v in vecinos4(c):
            if v in transitables and v not in alcanzadas:
                alcanzadas.add(v)
                cola.append(v)
    if campo - alcanzadas:
        raise ErrorMapa(f"{len(campo - alcanzadas)} celdas de campo no se alcanzan desde la bodega, "
                        f"por ejemplo {sorted(campo - alcanzadas)[0]}")
    servicio = caminos_c | {bodega} | set(bases)
    red_celdas, cola = {bodega}, deque([bodega])
    while cola:
        c = cola.popleft()
        for v in vecinos4(c):
            if v in servicio and v not in red_celdas:
                red_celdas.add(v)
                cola.append(v)
    if servicio - red_celdas:
        reporte.append(f"aviso: {len(servicio - red_celdas)} celdas de camino no se conectan con la bodega por "
                       f"camino, por ejemplo {sorted(servicio - red_celdas)[0]} (se llega cruzando rastrojo)")
    for nombre in lotes_m:
        propias = {c for c, lt in lote_de.items() if lt == nombre}
        if not any(v in caminos_c for c in propias for v in vecinos4(c)):
            raise ErrorMapa(f"el lote {nombre} no toca ningún camino (no tiene entrada)")

    # --- Salida -----------------------------------------------------------------------------------
    def ordenadas(t):
        return [list(c) for c in sorted((c for c, tt in tipo.items() if tt == t), key=lambda c: (c[1], c[0]))]

    def redondear(coords):
        return [[round(x, 2), round(y, 2)] for x, y in coords]

    ruta = Path(ruta_kml)
    mapa = {
        "nombre": ruta.stem,
        "fuente": {"kml": ruta.name, "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()},
        "parametros": {k: p[k] for k in PARAMETROS_POR_DEFECTO},
        "tamano_celda_m": s,
        "ancho": ancho,
        "alto": alto,
        "bodega": list(bodega),
        "bases": [list(b) for b in bases],
        "obstaculos": ordenadas("obstaculo"),
        "caminos": ordenadas("camino") + [list(c) for c in sorted([bodega] + bases, key=lambda c: (c[1], c[0]))],
        "fuera_de_campo": ordenadas("fuera"),
        "lotes": {n: [list(c) for c in sorted((c for c, lt in lote_de.items() if lt == n), key=lambda c: (c[1], c[0]))]
                  for n in lotes_m},
        "resumen_lotes": info_lotes,
        "geo": {
            "epsg": EPSG_UTM,
            "origen_utm": [round(marco.e0, 3), round(marco.n0, 3)],
            "rumbo_grados": round(rumbo, 3),
            "atribucion": ATRIBUCION_KML,
            "formas": {
                "lotes": {n: redondear(list(pol.exterior.coords)[:-1]) for n, pol in lotes_m.items()},
                "obstaculos": [redondear(list(o.exterior.coords)[:-1]) for o in obstaculos_m],
                "caminos": [redondear(list(g.coords)) for g in red_m.values()],
            },
        },
        "soldaduras": soldaduras,
    }
    reporte.append(f"cuadrícula: {ancho} × {alto} celdas de {s:g} m; campo {len(campo)}, caminos {len(caminos_c)}, "
                   f"obstáculos {len(ordenadas('obstaculo'))}, fuera {len(ordenadas('fuera'))}, "
                   f"bodega {list(bodega)}, {len(bases)} bases")
    return mapa, reporte


def construir_desde_config(ruta_config: str | Path) -> tuple[dict, list[str], Path]:
    """Lee la configuración del convertidor (`config/mapas/*.convertidor.json`) y devuelve
    (mapa, reporte, ruta de salida). Las rutas del KML y de la salida son relativas a la configuración."""
    ruta = Path(ruta_config)
    conf = json.loads(ruta.read_text(encoding="utf-8"))
    mapa, reporte = convertir(ruta.parent / conf["kml"], conf.get("parametros"))
    if conf.get("dem"):
        from .relieve import agregar_alturas
        reporte += agregar_alturas(mapa, conf["dem"] if Path(conf["dem"]).is_absolute() else ruta.parent / conf["dem"])
    return mapa, reporte, ruta.parent / conf.get("salida", f"{ruta.stem.split('.')[0]}.json")
