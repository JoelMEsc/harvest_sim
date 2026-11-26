"""Lectura del KML del cultivo (Google Earth) con las convenciones de nombres de Oswaldo.  [Oswaldo / Joel]

Las convenciones vienen de `CultivoDesdeKML.cs` (harvest-simu-visualization/docs/cultivo/) y se
documentan en docs/especificacion_terreno.md §3. El nombre del Placemark se compara en minúsculas y sin
acentos, y solo cuenta cómo empieza:

    cultivo / lote   -> LOTE      (polígono; "rumbo=45" en el nombre fija el rumbo de sus surcos)
    camino / brecha  -> CAMINO    (línea o polígono)
    obstaculo        -> OBSTACULO
    surco / guia     -> GUIA      (línea: rumbo de los surcos del lote donde cae su punto medio)
    bodega           -> BODEGA    (punto; nuevo)
    base             -> BASE      (punto; nuevo)
    otro nombre      -> línea: CAMINO; polígono o punto: OBSTACULO

Solo se lee el contorno exterior de los polígonos (como en el script de C#).
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

LOTE, CAMINO, OBSTACULO, GUIA, BODEGA, BASE = "lote", "camino", "obstaculo", "guia", "bodega", "base"
POLIGONO, LINEA, PUNTO = "poligono", "linea", "punto"

_KML = "{http://www.opengis.net/kml/2.2}"
_RUMBO = re.compile(r"rumbo\s*[=:_ ]?\s*(-?\d+(?:[.,]\d+)?)")


@dataclass
class Elemento:
    """Un Placemark del KML: nombre, tipo, geometría y coordenadas (lon, lat)."""
    nombre: str
    tipo: str
    geometria: str
    coordenadas: list[tuple[float, float]]
    rumbo_manual: float | None = None
    extra: dict = field(default_factory=dict)


def normalizar(nombre: str) -> str:
    """Minúsculas y sin acentos (á→a, ñ se conserva)."""
    sin = "".join(c for c in unicodedata.normalize("NFD", nombre.lower()) if unicodedata.category(c) != "Mn"
                  or c == "̃")
    return unicodedata.normalize("NFC", sin).strip()


def clasificar(nombre: str, geometria: str) -> str:
    """Tipo del elemento según cómo empieza su nombre (tabla de arriba)."""
    n = normalizar(nombre)
    if n.startswith(("cultivo", "lote")):
        return LOTE
    if n.startswith(("camino", "brecha")):
        return CAMINO
    if n.startswith("obstaculo"):
        return OBSTACULO
    if n.startswith(("surco", "guia")):
        return GUIA
    if n.startswith("bodega"):
        return BODEGA
    if n.startswith("base"):
        return BASE
    return CAMINO if geometria == LINEA else OBSTACULO


def rumbo_del_nombre(nombre: str) -> float | None:
    """`rumbo=45` (o `rumbo:45`, `rumbo 45`) en el nombre, normalizado a 0–180; None si no hay."""
    m = _RUMBO.search(nombre.lower())
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) % 180.0


def _coordenadas(texto: str) -> list[tuple[float, float]]:
    puntos = []
    for tupla in texto.split():
        partes = tupla.split(",")
        if len(partes) >= 2:
            puntos.append((float(partes[0]), float(partes[1])))
    return puntos


def leer_kml(ruta: str | Path) -> list[Elemento]:
    """Lee todos los Placemark (en orden) con su tipo y sus coordenadas (lon, lat)."""
    raiz = ET.parse(ruta).getroot()
    elementos = []
    for pm in raiz.iter(f"{_KML}Placemark"):
        nodo_nombre = pm.find(f"{_KML}name")
        nombre = (nodo_nombre.text or "").strip() if nodo_nombre is not None else ""
        poligono = pm.find(f".//{_KML}Polygon/{_KML}outerBoundaryIs//{_KML}coordinates")
        linea = pm.find(f".//{_KML}LineString/{_KML}coordinates")
        punto = pm.find(f".//{_KML}Point/{_KML}coordinates")
        if poligono is not None:
            geometria, coords = POLIGONO, _coordenadas(poligono.text or "")
            if len(coords) > 1 and coords[0] == coords[-1]:
                coords = coords[:-1]  # el KML repite el primer punto al final
        elif linea is not None:
            geometria, coords = LINEA, _coordenadas(linea.text or "")
        elif punto is not None:
            geometria, coords = PUNTO, _coordenadas(punto.text or "")
        else:
            continue
        tipo = clasificar(nombre, geometria)
        rumbo = rumbo_del_nombre(nombre) if tipo == LOTE else None
        elementos.append(Elemento(nombre, tipo, geometria, coords, rumbo))
    return elementos
