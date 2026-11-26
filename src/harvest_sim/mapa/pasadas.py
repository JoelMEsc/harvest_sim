"""Rumbo de los surcos y pasadas rectas de un lote: puerto a Python de `PasadasCultivo.cs` (Oswaldo).  [Oswaldo]

Es el mismo algoritmo, con los mismos nombres y pasos, para que se pueda comparar con el script de C#.
La simulación no recorre estas pasadas (recorre su serpentina por celdas); se usan para:
- decidir el rumbo de cada lote (guía, `rumbo=` en el nombre o automático) y con eso orientar la cuadrícula;
- validar que la serpentina por celdas cubre lo mismo que las pasadas reales.

Convenciones (como en el C#): coordenadas en metros con x = este e y = norte; rumbo en grados desde el
norte, en sentido horario, normalizado a 0–180; dirección de avance = (sin θ, cos θ).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Punto = tuple[float, float]
Intervalo = tuple[float, float]


@dataclass
class Pasada:
    inicio: Punto
    fin: Punto
    zona: int

    @property
    def largo(self) -> float:
        return math.dist(self.inicio, self.fin)


def direccion(rumbo_grados: float) -> Punto:
    r = math.radians(rumbo_grados)
    return (math.sin(r), math.cos(r))


def rumbo_de_linea(linea: list[Punto]) -> float:
    """Rumbo (0–180) de una línea guía, usando sus extremos."""
    dx, dy = linea[-1][0] - linea[0][0], linea[-1][1] - linea[0][1]
    return math.degrees(math.atan2(dx, dy)) % 180.0


def punto_medio(linea: list[Punto]) -> Punto:
    return ((linea[0][0] + linea[-1][0]) / 2, (linea[0][1] + linea[-1][1]) / 2)


def area_firmada(p: list[Punto]) -> float:
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def dentro_de_poligono(p: Punto, poli: list[Punto]) -> bool:
    dentro = False
    j = len(poli) - 1
    for i in range(len(poli)):
        xi, yi = poli[i]
        xj, yj = poli[j]
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _punto(a: Punto, b: Punto) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _intervalos(poli: list[Punto], n: Punto, d: Punto, c: float) -> list[Intervalo]:
    """Tramos (en coordenada de avance) donde la recta lateral = c está dentro del polígono."""
    cortes = []
    j = len(poli) - 1
    for i in range(len(poli)):
        ai, aj = _punto(poli[i], n), _punto(poli[j], n)
        if (ai > c) != (aj > c):
            t = (c - ai) / (aj - ai)
            di, dj = _punto(poli[i], d), _punto(poli[j], d)
            cortes.append(di + (dj - di) * t)
        j = i
    cortes.sort()
    return [(cortes[k], cortes[k + 1]) for k in range(0, len(cortes) - 1, 2)]


def _cruce_segmento(a: Punto, b: Punto, n: Punto, d: Punto, c: float) -> float | None:
    aa, ab = _punto(a, n), _punto(b, n)
    if (aa > c) == (ab > c):
        return None
    da, db = _punto(a, d), _punto(b, d)
    return da + (db - da) * (c - aa) / (ab - aa)


def _interseccion(a: list[Intervalo], b: list[Intervalo]) -> list[Intervalo]:
    res, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            res.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return res


def _unir(lista: list[Intervalo]) -> list[Intervalo]:
    res: list[Intervalo] = []
    for v in sorted(lista):
        if res and v[0] <= res[-1][1]:
            res[-1] = (res[-1][0], max(res[-1][1], v[1]))
        else:
            res.append(v)
    return res


def _restar(a: list[Intervalo], b: list[Intervalo]) -> list[Intervalo]:
    res = []
    for lo, hi in a:
        ini = lo
        for blo, bhi in b:
            if bhi <= ini or blo >= hi:
                continue
            if blo > ini:
                res.append((ini, blo))
            ini = max(ini, bhi)
            if ini >= hi:
                break
        if ini < hi:
            res.append((ini, hi))
    return res


def _solapa(a: Intervalo, b: Intervalo) -> bool:
    return min(a[1], b[1]) - max(a[0], b[0]) > 0


def generar_pasadas(lote: list[Punto], rumbo_grados: float, obs_poligonos=(), obs_lineas=(), obs_puntos=(),
                    radio_poste: float = 0.5, ancho: float = 6.0, cabecera: float = 8.0, margen: float = 3.0,
                    largo_min: float = 5.0) -> list[Pasada]:
    """Pasadas rectas paralelas al rumbo, separadas `ancho`, recortadas al lote (dejando la cabecera) y a los
    obstáculos (con margen). Donde un obstáculo o una entrada parte las pasadas, el lote se divide en zonas;
    cada zona se recorre completa en ida y vuelta antes de pasar a la siguiente."""
    if len(lote) < 3 or ancho <= 0:
        return []
    d = direccion(rumbo_grados)
    n = (d[1], -d[0])
    proy = [_punto(p, n) for p in lote]
    min_n, max_n = min(proy), max(proy)
    mitad = ancho / 2
    lineas: list[tuple[float, list[Intervalo]]] = []
    c = min_n + mitad
    while c <= max_n - mitad + 1e-3:
        libre = _intervalos(lote, n, d, c)
        libre = _interseccion(libre, _intervalos(lote, n, d, c - mitad * 0.98))
        libre = _interseccion(libre, _intervalos(lote, n, d, c + mitad * 0.98))
        libre = [(lo + cabecera, hi - cabecera) for lo, hi in libre if hi - cabecera > lo + cabecera]
        bloqueado = []
        for o in obs_poligonos:
            for off in (-mitad, 0.0, mitad):
                bloqueado += [(lo - margen, hi + margen) for lo, hi in _intervalos(o, n, d, c + off)]
        for linea in obs_lineas:
            for k in range(len(linea) - 1):
                for off in (-mitad, 0.0, mitad):
                    t = _cruce_segmento(linea[k], linea[k + 1], n, d, c + off)
                    if t is not None:
                        bloqueado.append((t - margen, t + margen))
        for p in obs_puntos:
            lat = _punto(p, n) - c
            r = radio_poste + margen
            if abs(lat) <= mitad + r:
                a = _punto(p, d)
                bloqueado.append((a - r, a + r))
        libre = _restar(libre, _unir(bloqueado))
        tramos = [i for i in libre if i[1] - i[0] >= largo_min]
        if tramos:
            lineas.append((c, tramos))
        c += ancho

    zonas: list[list[tuple[float, Intervalo]]] = []
    zona_prev: list[int] = []
    prev: list[Intervalo] | None = None
    for c, tramos in lineas:
        zona_act = []
        for t in tramos:
            zona = -1
            if prev is not None:
                toca = [k for k in range(len(prev)) if _solapa(prev[k], t)]
                if len(toca) == 1 and sum(_solapa(prev[toca[0]], o) for o in tramos) == 1:
                    zona = zona_prev[toca[0]]
            if zona < 0:
                zona = len(zonas)
                zonas.append([])
            zonas[zona].append((c, t))
            zona_act.append(zona)
        prev, zona_prev = tramos, zona_act

    res = []
    for z, tramos in enumerate(zonas):
        ida = True
        for c, (lo, hi) in tramos:
            a = (n[0] * c + d[0] * lo, n[1] * c + d[1] * lo)
            b = (n[0] * c + d[0] * hi, n[1] * c + d[1] * hi)
            res.append(Pasada(a, b, z) if ida else Pasada(b, a, z))
            ida = not ida
    return res


def rumbo_optimo(lote: list[Punto], obs_poligonos=(), obs_lineas=(), obs_puntos=(), **parametros) -> float:
    """Prueba rumbos de 0 a 179.5° y se queda con el que da menos pasadas; en empate, el que cubre más."""
    mejor, mejor_n, mejor_largo = 0.0, math.inf, -1.0
    r = 0.0
    while r < 180.0:
        p = generar_pasadas(lote, r, obs_poligonos, obs_lineas, obs_puntos, **parametros)
        largo = sum(x.largo for x in p)
        if len(p) < mejor_n or (len(p) == mejor_n and largo > mejor_largo + 0.01):
            mejor, mejor_n, mejor_largo = r, len(p), largo
        r += 0.5
    return mejor


def rumbo_de_lote(lote: list[Punto], rumbo_manual: float | None, guias: list[list[Punto]],
                  obs_poligonos=(), **parametros) -> tuple[float, str]:
    """(rumbo, modo) del lote, con la prioridad del C#: manual, guía cuyo punto medio cae en el lote,
    automático."""
    if rumbo_manual is not None:
        return rumbo_manual % 180.0, "manual"
    for g in guias:
        if len(g) >= 2 and dentro_de_poligono(punto_medio(g), lote):
            return rumbo_de_linea(g), "guia"
    return rumbo_optimo(lote, obs_poligonos, **parametros), "automatico"
