"""Cobertura de un lote como en la industria: cabecera, pasadas paralelas a las hileras y orden de pasadas.  [Joel]

Plan de hileras y rutas (fase H1). Sigue la cadena de Fields2Cover (Mier et al., 2023; github.com/Fields2Cover):
generador de cabeceras → generador de pasadas → planificador de orden → planificador de trayectoria (las vueltas
Dubins están en `dubins.py`). Aquí todo vive en la cuadrícula de la simulación: una celda mide `s` metros, las
hileras van a lo largo del eje x (con mapa, la cuadrícula está girada con el rumbo de los surcos) y una pasada es
un tramo de una fila.

- **Cabecera** (`cabecera`): el anillo del lote donde se dan las vueltas. En los extremos de cada tramo de fila
  (donde terminan las hileras) tiene `k` celdas, suficientes para la vuelta con el radio de giro; en las orillas
  paralelas a las hileras (la primera y la última fila de cada columna) tiene una celda, para poder pasar de un
  extremo al otro. Se cosecha primero («abrir el campo»), así todas las vueltas de después son sobre rastrojo.
- **Pasadas** (`pasadas`): los tramos de fila que quedan dentro de la cabecera. Cada una se cosecha de punta a
  punta a lo largo de las hileras.
- **Bloques** (`bloques`): descomposición boustrophedon (Choset): filas consecutivas cuyas pasadas se traslapan
  en x y no se parten. Un obstáculo o una muesca del lote abre bloques nuevos.
- **Orden** (`ordenar`): dentro de un bloque, `boustrophedon` (pasada vecina, sentido alterno) o `snake` (salta
  una pasada y regresa por las que dejó: la vuelta cabe en U cuando 2R > ancho de pasada). Se elige el de menor
  costo de vueltas con la función que se le pase (Dubins en la simulación).

No usa la librería Fields2Cover (en PyPI solo hay código fuente que exige compilar C++ con GDAL y OR-tools): se
implementan sus mismos pasos sobre la cuadrícula, que es donde la simulación vive.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

Celda = tuple[int, int]
PATRONES = ("boustrophedon", "snake")


@dataclass(frozen=True)
class Pasada:
    """Un tramo de la fila `y`, de `x0` a `x1` inclusive (x0 <= x1)."""
    y: int
    x0: int
    x1: int

    def celdas(self, hacia_este: bool = True) -> list[Celda]:
        xs = range(self.x0, self.x1 + 1) if hacia_este else range(self.x1, self.x0 - 1, -1)
        return [(x, self.y) for x in xs]

    @property
    def largo(self) -> int:
        return self.x1 - self.x0 + 1


@dataclass
class Cobertura:
    """Resultado para una unidad (lote o parte de lote): qué es cabecera, las pasadas y en qué orden."""
    cabecera: set[Celda]
    pasadas: list[Pasada]
    bloques: list[list[Pasada]]
    orden: list[tuple[Pasada, bool]] = field(default_factory=list)  # (pasada, hacia_este)
    patron: dict[int, str] = field(default_factory=dict)  # bloque -> patrón elegido


def tramos(celdas: Iterable[Celda]) -> list[Pasada]:
    """Tramos continuos de cada fila (ordenados por fila y luego por x)."""
    por_fila: dict[int, list[int]] = {}
    for x, y in celdas:
        por_fila.setdefault(y, []).append(x)
    res = []
    for y in sorted(por_fila):
        xs = sorted(por_fila[y])
        inicio = xs[0]
        for a, b in zip(xs, xs[1:] + [None]):
            if b is None or b != a + 1:
                res.append(Pasada(y, inicio, a))
                if b is not None:
                    inicio = b
    return res


def celdas_de_cabecera(radio_giro_m: float, tamano_celda_m: float) -> int:
    """Celdas de cabecera en los extremos de las hileras: lo que ocupa una vuelta en U con radio R (2R) más la
    celda donde la máquina termina de salir de la hilera. Mínimo 2."""
    return max(2, math.ceil(2 * radio_giro_m / tamano_celda_m))


def cabecera(celdas: set[Celda], k: int) -> set[Celda]:
    """Anillo de cabecera: las `k` primeras y últimas celdas de cada tramo de fila (donde terminan las hileras) y
    la primera y la última celda de cada columna (las orillas paralelas a las hileras). Un tramo de 2k celdas o
    menos es todo cabecera."""
    anillo: set[Celda] = set()
    for p in tramos(celdas):
        if p.largo <= 2 * k:
            anillo.update(p.celdas())
        else:
            anillo.update((x, p.y) for x in range(p.x0, p.x0 + k))
            anillo.update((x, p.y) for x in range(p.x1 - k + 1, p.x1 + 1))
    por_columna: dict[int, list[int]] = {}
    for x, y in celdas:
        por_columna.setdefault(x, []).append(y)
    for x, ys in por_columna.items():
        ys.sort()
        anillo.update({(x, ys[0]), (x, ys[-1])})
        for a, b in zip(ys, ys[1:]):  # una muesca o un obstáculo parten la columna: también es orilla
            if b != a + 1:
                anillo.update({(x, a), (x, b)})
    return anillo & set(celdas)


def bloques(pasadas: list[Pasada]) -> list[list[Pasada]]:
    """Descomposición boustrophedon: cada bloque es una serie de pasadas en filas consecutivas que se traslapan
    en x, sin bifurcaciones (si una pasada toca dos en la fila siguiente, o dos tocan una, empieza bloque nuevo)."""
    por_fila: dict[int, list[Pasada]] = {}
    for p in pasadas:
        por_fila.setdefault(p.y, []).append(p)

    def traslapan(a: Pasada, b: Pasada) -> bool:
        return a.x0 <= b.x1 and b.x0 <= a.x1

    abiertos: list[list[Pasada]] = []
    cerrados: list[list[Pasada]] = []
    for y in sorted(por_fila):
        nuevos: list[list[Pasada]] = []
        actuales = por_fila[y]
        usados: set[int] = set()
        for bloque in abiertos:
            ultima = bloque[-1]
            if ultima.y != y - 1:
                cerrados.append(bloque)
                continue
            hijos = [i for i, p in enumerate(actuales) if traslapan(ultima, p)]
            if len(hijos) == 1:
                padres = [b for b in abiertos if b[-1].y == y - 1 and traslapan(b[-1], actuales[hijos[0]])]
                if len(padres) == 1 and hijos[0] not in usados:
                    bloque.append(actuales[hijos[0]])
                    usados.add(hijos[0])
                    nuevos.append(bloque)
                    continue
            cerrados.append(bloque)
        for i, p in enumerate(actuales):
            if i not in usados:
                nuevos.append([p])
        abiertos = nuevos
    return cerrados + abiertos


def secuencia(n: int, patron: str) -> list[int]:
    """Índices de las pasadas de un bloque en el orden del patrón. snake: 0, 2, 4, … y de regreso por las
    impares, como el `RP_Snake` de Fields2Cover; boustrophedon: 0, 1, 2, …"""
    if patron == "boustrophedon" or n <= 2:
        return list(range(n))
    if patron == "snake":
        pares = list(range(0, n, 2))
        impares = list(range(1, n, 2))
        return pares + impares[::-1]
    raise ValueError(f"patrón desconocido: {patron}")


def ordenar(bloque: list[Pasada], patron: str, desde: Celda | None) -> list[tuple[Pasada, bool]]:
    """Orden y sentido de las pasadas de un bloque. Empieza por la punta (fila de arriba o de abajo, extremo
    oeste o este) más cercana a `desde`; el sentido se alterna para que cada pasada empiece donde terminó la
    vuelta."""
    mejores = []
    for invertir in (False, True):
        filas = bloque[::-1] if invertir else bloque
        indices = secuencia(len(filas), patron)
        for este in (True, False):
            orden = []
            sentido = este
            for i in indices:
                orden.append((filas[i], sentido))
                sentido = not sentido
            inicio = orden[0][0].celdas(orden[0][1])[0]
            d = 0 if desde is None else abs(inicio[0] - desde[0]) + abs(inicio[1] - desde[1])
            mejores.append((d, invertir, not este, orden))
    return min(mejores, key=lambda m: m[:3])[3]


Vuelta = Callable[[Celda, str, Celda, str], float]


def _manhattan(fin: Celda, _rf: str, inicio: Celda, _ri: str) -> float:
    return abs(fin[0] - inicio[0]) + abs(fin[1] - inicio[1])


def costo_vueltas(orden: list[tuple[Pasada, bool]], vuelta: Vuelta) -> float:
    """Suma de las vueltas entre pasadas consecutivas: `vuelta(fin, rumbo, inicio, rumbo)` del fin de una
    pasada (con su rumbo, E u O) al inicio de la siguiente."""
    total = 0.0
    for (a, ea), (b, eb) in zip(orden, orden[1:]):
        total += vuelta(a.celdas(ea)[-1], "E" if ea else "O", b.celdas(eb)[0], "E" if eb else "O")
    return total


def cobertura(celdas: set[Celda], k: int, desde: Celda | None = None,
              vuelta: Vuelta | None = None,
              patrones: tuple[str, ...] = PATRONES) -> Cobertura:
    """Cabecera, pasadas, bloques y orden de una unidad. `vuelta(fin, rumbo, inicio, rumbo)` = costo de dar la
    vuelta (en la simulación, ticks de la curva Dubins); sin ella se usa la distancia Manhattan. Para cada bloque
    se prueba cada patrón y se queda el de menor costo de vueltas (empate: boustrophedon)."""
    vuelta = vuelta or _manhattan
    cab = cabecera(celdas, k)
    interiores = tramos(set(celdas) - cab)
    bls = bloques(interiores)
    resultado = Cobertura(cab, interiores, bls)
    pendientes = list(range(len(bls)))
    posicion = desde
    while pendientes:
        # el bloque cuya punta más cercana queda más cerca de donde va la máquina
        def distancia(i):
            puntas = [p.celdas(e)[0] for p, e in ordenar(bls[i], "boustrophedon", posicion)[:1]]
            return min(abs(c[0] - posicion[0]) + abs(c[1] - posicion[1]) for c in puntas) if posicion else 0
        i = min(pendientes, key=lambda j: (distancia(j), j))
        pendientes.remove(i)
        opciones = [(costo_vueltas(o, vuelta), patron != "boustrophedon", patron, o)
                    for patron in patrones for o in [ordenar(bls[i], patron, posicion)]]
        _, _, patron, orden = min(opciones, key=lambda o: o[:2])
        resultado.orden += orden
        resultado.patron[i] = patron
        ultima, sentido = orden[-1]
        posicion = ultima.celdas(sentido)[-1]
    return resultado


def recorrido_cabecera(cab: set[Celda], desde: Celda | None) -> list[Celda]:
    """Orden para cosechar la cabecera («abrir el campo»): un paseo que siempre va a la celda de cabecera sin
    cosechar más cercana, prefiriendo seguir derecho. Los saltos entre celdas no vecinas los resuelve el
    planificador de traslados por rastrojo."""
    pendientes = set(cab)
    if not pendientes:
        return []
    actual = min(pendientes, key=lambda c: ((abs(c[0] - desde[0]) + abs(c[1] - desde[1])) if desde else 0, c))
    orden = [actual]
    pendientes.discard(actual)
    rumbo = (0, 0)
    while pendientes:
        def clave(c):
            d = abs(c[0] - actual[0]) + abs(c[1] - actual[1])
            derecho = (c[0] - actual[0], c[1] - actual[1]) == rumbo
            return (d, not derecho, c[1], c[0])
        siguiente = min(pendientes, key=clave)
        rumbo = (siguiente[0] - actual[0], siguiente[1] - actual[1]) if clave(siguiente)[0] == 1 else (0, 0)
        orden.append(siguiente)
        pendientes.discard(siguiente)
        actual = siguiente
    return orden


def _alcance(desde: Celda, libres: set[Celda]) -> dict[Celda, int]:
    """Distancias en vecindad 4 desde `desde` andando solo por `libres` (rastrojo y caminos)."""
    dist = {desde: 0}
    frente = [desde]
    while frente:
        siguiente = []
        for x, y in frente:
            for v in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if v in libres and v not in dist:
                    dist[v] = dist[(x, y)] + 1
                    siguiente.append(v)
        frente = siguiente
    return dist


def secuencia_alcanzable(r: Cobertura, inicio: Celda, transitables: set[Celda]
                         ) -> tuple[list[Celda], dict[Celda, tuple[Celda, str]], int]:
    """Orden de cosecha que nunca obliga a cruzar cultivo en pie, como se hace en el campo:

    1. «abrir el campo»: cosecha la cabecera que puede alcanzar por rastrojo o camino, siempre la celda alcanzable
       más cercana (prefiriendo seguir derecho);
    2. recorre las pasadas en el orden planeado; cada una se entra de frente desde una celda de cabecera ya
       cosechada (si la entrada planeada sigue en pie, la pasada se hace en sentido contrario; si ninguna punta
       está lista, se pospone);
    3. después de cada pasada cosecha la cabecera que quedó alcanzable (por ejemplo, la que rodea un obstáculo
       en medio del lote, que solo se alcanza cuando las pasadas llegan a ella).

    Devuelve (celdas en orden, {inicio de pasada: (celda de entrada, rumbo)}, celdas que no se pudieron alcanzar
    sin cruzar cultivo; esas van al final y el planificador de traslados las resuelve)."""
    hecho: set[Celda] = set()
    pendientes = set(r.cabecera)
    orden: list[Celda] = []
    entradas: dict[Celda, tuple[Celda, str]] = {}
    pos = inicio
    rumbo = (0, 0)

    def abrir():
        nonlocal pos, rumbo
        while pendientes:
            dist = _alcance(pos, transitables | hecho | {pos})
            mejor = None
            for c in pendientes:
                x, y = c
                for v in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if v in dist:
                        derecho = (c[0] - v[0], c[1] - v[1]) == rumbo and v == pos
                        clave = (dist[v] + 1, not derecho, c[1], c[0])
                        if mejor is None or clave < mejor[0]:
                            mejor = (clave, c)
            if mejor is None:
                return
            c = mejor[1]
            rumbo = (c[0] - pos[0], c[1] - pos[1]) if abs(c[0] - pos[0]) + abs(c[1] - pos[1]) == 1 else (0, 0)
            orden.append(c)
            hecho.add(c)
            pendientes.discard(c)
            pos = c

    abrir()
    cola = list(r.orden)
    intentos = 0
    while cola and intentos <= len(cola):
        pasada, este = cola.pop(0)
        hecha = None
        for sentido in (este, not este):
            celdas = pasada.celdas(sentido)
            x, y = celdas[0]
            antes = (x - 1, y) if sentido else (x + 1, y)
            if antes in hecho or antes in transitables:
                hecha = (celdas, antes, sentido)
                break
        if hecha is None:
            cola.append((pasada, este))
            intentos += 1
            continue
        intentos = 0
        celdas, antes, sentido = hecha
        entradas[celdas[0]] = (antes, "E" if sentido else "O")
        orden.extend(celdas)
        hecho.update(celdas)
        pos = celdas[-1]
        rumbo = (1, 0) if sentido else (-1, 0)
        abrir()
    sin_alcance = len(pendientes) + sum(p.largo for p, _ in cola)
    for pasada, este in cola:  # no debería pasar: se cosechan al final y el traslado decide
        orden.extend(pasada.celdas(este))
    orden.extend(sorted(pendientes, key=lambda c: (c[1], c[0])))
    return orden, entradas, sin_alcance
