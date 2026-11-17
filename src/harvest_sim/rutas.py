"""Rutas: BFS y reglas de movimiento sobre el grid.  [Oswaldo]

Funciones puras (sin estado, sin importar Mundo ni agentes) para poder probarlas
solas. Mundo.vecinos y Mundo.ruta_bfs delegan aquí.

Especificación: §4.2 (conflictos de celda) y §5.2 (BFS y celda objetivo del carro).
"""

from __future__ import annotations

from collections import deque

Celda = tuple[int, int]  # (x, y); origen arriba a la izquierda, y crece hacia abajo

# Desplazamientos en el orden fijo N, E, S, O. Como y crece hacia abajo, el norte es y - 1.
# Este orden es el que hace deterministas a vecinos(), bfs() y los desempates.
DIRECCIONES: tuple[Celda, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


def vecinos(celda: Celda, ancho: int, alto: int) -> list[Celda]:
    """Vecindad de 4 en el orden N, E, S, O, solo celdas dentro del mapa (R1, R2)."""
    x, y = celda
    resultado = []
    for dx, dy in DIRECCIONES:
        nx, ny = x + dx, y + dy
        if 0 <= nx < ancho and 0 <= ny < alto:
            resultado.append((nx, ny))
    return resultado


def bfs(origen: Celda, destino: Celda, ancho: int, alto: int, bloqueadas: set[Celda]) -> list[Celda] | None:
    """Ruta más corta, determinista (expande vecinos en orden N, E, S, O).

    Devuelve la lista de celdas SIN el origen y CON el destino; [] si origen == destino;
    None si no existe ruta. Nunca pasa por celdas de `bloqueadas`: si el destino está
    bloqueado (por ejemplo, ocupado por otro agente), no hay ruta y devuelve None.
    El origen nunca se considera bloqueado (es donde ya está el agente).
    """
    if origen == destino:
        return []
    if destino in bloqueadas:
        return None

    # padre[c] = celda desde la que se descubrió c; sirve también como "visitadas".
    padre: dict[Celda, Celda | None] = {origen: None}
    fila: deque[Celda] = deque([origen])

    while fila:
        actual = fila.popleft()
        for siguiente in vecinos(actual, ancho, alto):
            if siguiente in padre or siguiente in bloqueadas:
                continue
            padre[siguiente] = actual
            if siguiente == destino:
                return _reconstruir(padre, destino)
            fila.append(siguiente)

    return None


def _reconstruir(padre: dict[Celda, Celda | None], destino: Celda) -> list[Celda]:
    """Recorre los padres desde el destino hasta el origen y voltea la lista (sin el origen)."""
    ruta = []
    celda: Celda | None = destino
    while padre[celda] is not None:
        ruta.append(celda)
        celda = padre[celda]
    ruta.reverse()
    return ruta


def elegir_celda_objetivo(
    origen: Celda,
    objetivo: Celda,
    ancho: int,
    alto: int,
    bloqueadas: set[Celda],
    evitar: set[Celda],
) -> Celda | None:
    """Celda vecina de `objetivo` donde se estaciona el carro (§5.2).

    Orden de decisión:
      1. Excluir celdas fuera del mapa, bloqueadas (bodega, ocupadas por otros agentes).
      2. Excluir las de `evitar` (la siguiente celda de la serpentina), salvo que sea
         la única opción.
      3. Elegir la de menor distancia BFS desde `origen`.
      4. Desempate: orden N, E, S, O.
    Devuelve None si ninguna celda es alcanzable.

    Las distancias se miden con `bloqueadas` más la propia celda `objetivo` (ahí está
    la cosechadora, así que el carro no puede cruzarla). "Única opción" se entiende
    como "única alcanzable": si ninguna celda fuera de `evitar` tiene ruta, se usa
    una de `evitar`.
    """
    bloqueadas_ruta = bloqueadas | {objetivo}

    preferida: tuple[int, Celda] | None = None  # (distancia, celda) fuera de `evitar`
    respaldo: tuple[int, Celda] | None = None  # (distancia, celda) dentro de `evitar`

    # vecinos() ya viene en orden N, E, S, O: con "<" estricto, a igual distancia
    # se queda la primera que se vio, que es el desempate del paso 4.
    for candidata in vecinos(objetivo, ancho, alto):
        if candidata in bloqueadas:
            continue
        ruta = bfs(origen, candidata, ancho, alto, bloqueadas_ruta)
        if ruta is None:
            continue
        distancia = len(ruta)
        if candidata in evitar:
            if respaldo is None or distancia < respaldo[0]:
                respaldo = (distancia, candidata)
        elif preferida is None or distancia < preferida[0]:
            preferida = (distancia, candidata)

    if preferida is not None:
        return preferida[1]
    if respaldo is not None:
        return respaldo[1]
    return None


def siguiente_paso(
    pos: Celda,
    ruta: list[Celda],
    destino: Celda,
    ancho: int,
    alto: int,
    ocupadas: set[Celda],
    bloqueadas_fijas: set[Celda],
) -> tuple[Celda | None, list[Celda]]:
    """Un paso de movimiento con resolución de conflictos (§4.2).

    - Si la siguiente celda de `ruta` está libre: devuelve (esa celda, ruta restante).
    - Si está en `ocupadas`: recalcula con BFS tratando `ocupadas | bloqueadas_fijas`
      como bloqueadas y da el primer paso de la nueva ruta.
    - Si no hay ruta: devuelve (None, ruta) -> el agente espera un tick.

    Casos de borde:
    - Si `pos == destino` devuelve (None, []): ya llegó y no hay nada que mover. El
      agente debe revisar si llegó ANTES de pedir un paso; ese (None, []) no es un bloqueo.
    - Si `ruta` viene vacía, o su primera celda no es vecina de `pos` (ruta vieja),
      se recalcula igual que con una celda ocupada.
    No modifica `ruta`: siempre devuelve una lista nueva.
    """
    if pos == destino:
        return None, []

    if ruta and ruta[0] in vecinos(pos, ancho, alto):
        siguiente = ruta[0]
        if siguiente not in ocupadas and siguiente not in bloqueadas_fijas:
            return siguiente, list(ruta[1:])

    nueva = bfs(pos, destino, ancho, alto, ocupadas | bloqueadas_fijas)
    if not nueva:
        return None, list(ruta)
    return nueva[0], nueva[1:]
