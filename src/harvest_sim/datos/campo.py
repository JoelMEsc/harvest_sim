"""El campo, los obstáculos y el grano esperado: la fórmula en un solo lugar.  [Joel]

Fórmula (para cualquier mundo; documentada en docs/decisiones.md y docs/equipo/README.md):

    celdas_de_campo(mundo) = celdas (x, y) con 0 <= x < ancho y 1 <= y < alto, menos los obstáculos
    grano_esperado(mundo)  = número de celdas de campo x grano_por_celda

La fila y = 0 es la fila de servicio (bodega y bases): no es campo y no puede tener obstáculos.

Obstáculos en la configuración (sección `obstaculos`, por ahora vacía en los escenarios):

    "obstaculos": {"celdas": [[3, 2], [4, 2]],
                   "regiones": [{"inicio": [1, 4], "tamano": [2, 3]}]}

Una región es el rectángulo que empieza en `inicio` (x, y) y mide `tamano` (ancho, alto) celdas.
`expandir_obstaculos` valida la sección y devuelve la lista de celdas que va en `mundo.obstaculos`
del trace. La usa config.py (Carlos) para validar la configuración.
"""

from __future__ import annotations

from collections import deque


def _es_entero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _es_par(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(_es_entero(c) for c in v)


def expandir_obstaculos(seccion: dict | None, ancho: int, alto: int) -> list[list[int]]:
    """Valida la sección `obstaculos` de la configuración y devuelve sus celdas, ordenadas por (y, x)
    y sin repetir. Lanza ValueError con un mensaje claro si algo no cumple las restricciones:

    - `celdas` es una lista de [x, y] enteros; `regiones` es una lista de {inicio: [x, y], tamano: [ancho, alto]}
      con tamaño >= 1 en ambos ejes (no se aceptan otras claves);
    - toda celda y toda región completa quedan dentro del mapa (0 <= x < ancho, 0 <= y < alto);
    - nada en la fila 0 (servicio: bodega y bases);
    - cada celda de campo libre se puede alcanzar desde la bodega (0, 0) sin cruzar obstáculos.
    """
    if seccion is None:
        return []
    if not isinstance(seccion, dict) or set(seccion) - {"celdas", "regiones"}:
        raise ValueError("obstaculos debe ser un objeto con solo las claves 'celdas' y 'regiones'")
    celdas: set[tuple[int, int]] = set()

    def agregar(x, y, origen):
        if not (0 <= x < ancho and 0 <= y < alto):
            raise ValueError(f"obstaculos: {origen} queda fuera del mapa ({ancho} x {alto}) en ({x}, {y})")
        if y == 0:
            raise ValueError(f"obstaculos: {origen} está en la fila 0 (servicio: bodega y bases) en ({x}, {y})")
        celdas.add((x, y))

    lista = seccion.get("celdas", [])
    if not isinstance(lista, list):
        raise ValueError("obstaculos.celdas debe ser una lista de [x, y]")
    for i, c in enumerate(lista):
        if not _es_par(c):
            raise ValueError(f"obstaculos.celdas[{i}] debe ser [x, y] con enteros, es {c!r}")
        agregar(c[0], c[1], f"la celda {i}")

    regiones = seccion.get("regiones", [])
    if not isinstance(regiones, list):
        raise ValueError("obstaculos.regiones debe ser una lista de {inicio, tamano}")
    for i, r in enumerate(regiones):
        if not (isinstance(r, dict) and set(r) == {"inicio", "tamano"} and _es_par(r["inicio"]) and _es_par(r["tamano"])):
            raise ValueError(f"obstaculos.regiones[{i}] debe ser {{\"inicio\": [x, y], \"tamano\": [ancho, alto]}} con enteros")
        (x0, y0), (w, h) = r["inicio"], r["tamano"]
        if w < 1 or h < 1:
            raise ValueError(f"obstaculos.regiones[{i}]: el tamaño debe ser >= 1 en ambos ejes, es {[w, h]}")
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                agregar(x, y, f"la región {i}")

    libres = {(x, y) for x in range(ancho) for y in range(alto)} - celdas
    alcanzadas = {(0, 0)}
    cola = deque([(0, 0)])
    while cola:
        x, y = cola.popleft()
        for n in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if n in libres and n not in alcanzadas:
                alcanzadas.add(n)
                cola.append(n)
    aisladas = sorted(libres - alcanzadas, key=lambda c: (c[1], c[0]))
    if aisladas:
        raise ValueError(f"obstaculos: dejan celdas de campo sin acceso desde la bodega, por ejemplo {list(aisladas[0])}")
    return [[x, y] for x, y in sorted(celdas, key=lambda c: (c[1], c[0]))]


def obstaculos(mundo: dict) -> set[tuple[int, int]]:
    """Celdas con obstáculo del `mundo` del trace (vacío si el mundo no trae la lista)."""
    return {(c[0], c[1]) for c in mundo.get("obstaculos") or []}


def celdas_de_campo(mundo: dict) -> set[tuple[int, int]]:
    """Celdas que se cosechan: y >= 1, dentro del mapa y sin obstáculo. Vacío si no se conoce el tamaño."""
    ancho, alto = mundo.get("ancho"), mundo.get("alto")
    if not (_es_entero(ancho) and _es_entero(alto)):
        return set()
    return {(x, y) for x in range(ancho) for y in range(1, alto)} - obstaculos(mundo)


def rendimiento(mundo: dict, celda: tuple[int, int]) -> int:
    """Grano de una celda: `mundo.rendimiento[y][x]` si el mundo lo trae (2.2, rendimiento variable);
    si no, `grano_por_celda`."""
    x, y = celda
    matriz = mundo.get("rendimiento")
    if isinstance(matriz, list) and 0 <= y < len(matriz) and 0 <= x < len(matriz[y]):
        return matriz[y][x]
    return mundo.get("grano_por_celda", 1)


def grano_esperado(mundo: dict) -> int | None:
    """Grano total del campo = suma del rendimiento de cada celda de campo. Sin `mundo.rendimiento`,
    celdas de campo x grano_por_celda. None si no se conoce el tamaño."""
    if not (_es_entero(mundo.get("ancho")) and _es_entero(mundo.get("alto"))):
        return None
    if isinstance(mundo.get("rendimiento"), list):
        return sum(rendimiento(mundo, c) for c in celdas_de_campo(mundo))
    return len(celdas_de_campo(mundo)) * mundo.get("grano_por_celda", 1)
