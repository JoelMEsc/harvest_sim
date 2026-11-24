"""Rutas: BFS y reglas de movimiento sobre el grid.  [Oswaldo]

Funciones puras (sin estado, sin importar Mundo ni agentes) para poder probarlas
solas. Mundo.vecinos y Mundo.ruta_bfs delegan aquí.

Especificación primera entrega: §4.2 (conflictos de celda) y §5.2 (BFS y celda objetivo
del carro). Segunda entrega: §5 (reservas espacio-tiempo), §7 (costo de la oferta) y §10
(restricciones registradas).

Convención de tiempo de las rutas en el tiempo: una entrada (celda, t) es dónde está el
agente AL FINAL del tick t. En el paso del tick t el agente está en (pos, t - 1), así que
llama bfs_tiempo(pos, destino, t - 1, ...) y el primer elemento es la celda donde termina
el tick t.
"""

from __future__ import annotations

from collections import deque

Celda = tuple[int, int]  # (x, y); origen arriba a la izquierda, y crece hacia abajo
PasoEnTiempo = tuple[Celda, int]  # (celda, tick)
Reservas = dict[PasoEnTiempo, str]  # {(celda, tick): agent_id}

HORIZONTE = 10  # ticks en que cuentan las reservas (§5)

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


# ============================================================ segunda entrega


def distancias(origen: Celda, ancho: int, alto: int, bloqueadas: set[Celda]) -> dict[Celda, int]:
    """Distancia BFS (en pasos) desde `origen` a cada celda alcanzable, sin pasar por `bloqueadas`.

    El origen vale 0 y nunca se considera bloqueado. Mismo orden N, E, S, O que `bfs`.
    """
    dist: dict[Celda, int] = {origen: 0}
    fila: deque[Celda] = deque([origen])
    while fila:
        actual = fila.popleft()
        for siguiente in vecinos(actual, ancho, alto):
            if siguiente in dist or siguiente in bloqueadas:
                continue
            dist[siguiente] = dist[actual] + 1
            fila.append(siguiente)
    return dist


def bfs_tiempo(
    origen: Celda,
    destino: Celda,
    tick: int,
    ancho: int,
    alto: int,
    bloqueadas: set[Celda],
    reservas: Reservas,
    horizonte: int = HORIZONTE,
    permanencia: int | None = None,
) -> list[PasoEnTiempo] | None:
    """Ruta en espacio-tiempo desde (origen, tick) hasta `destino` (§5, idea de A* cooperativo).

    Cada paso es esperar en la celda o moverse a un vecino; se expande en el orden fijo
    esperar, N, E, S, O (determinista). Mientras t <= tick + horizonte:
      - nunca usa una (celda, t) de `reservas` (reservadas por OTROS agentes: el que llama
        pasa mundo.reservas(excepto=su_id));
      - nunca se intercambia: si otro tiene (c2, t) y (c1, t + 1), no va de c1 a c2 entre t y t + 1;
      - solo llega al destino en un tick t si nadie más lo tiene reservado durante los
        `permanencia` ticks siguientes (el tiempo que se va a quedar ahí, por ejemplo lo que
        dura la descarga en la bodega). None = el resto del horizonte (se estaciona).
    Después del horizonte las reservas ya no cuentan: la búsqueda sigue como BFS normal
    (sin esperas), pero siempre sin pasar por `bloqueadas`.

    Devuelve [(celda, t), ...] sin el origen y con el destino (un elemento por tick, así que
    las esperas aparecen como la misma celda repetida); [] si origen == destino; None si el
    destino está bloqueado o no hay ruta. Siempre termina: hay a lo más celdas × (horizonte + 1)
    estados con tiempo, más uno por celda después del horizonte.
    """
    return _bfs_tiempo(
        origen, destino, tick, ancho, alto, bloqueadas, reservas, horizonte, True, permanencia
    )


def _bfs_tiempo(
    origen: Celda,
    destino: Celda,
    tick: int,
    ancho: int,
    alto: int,
    bloqueadas: set[Celda],
    reservas: Reservas,
    horizonte: int,
    evitar_intercambio: bool,
    permanencia: int | None = None,
) -> list[PasoEnTiempo] | None:
    """bfs_tiempo con el chequeo de intercambio opcional (apagarlo solo sirve a clasificar_desvio)."""
    if origen == destino:
        return []
    if destino in bloqueadas:
        return None

    limite = tick + horizonte
    # Ticks (dentro del horizonte) en que otro agente tiene el destino.
    ocupado_destino = sorted(t for (celda, t) in reservas if celda == destino and tick < t <= limite)

    def puede_quedarse(t_llegada: int) -> bool:
        hasta = limite if permanencia is None else t_llegada + permanencia
        return not any(t_llegada < t <= hasta for t in ocupado_destino)

    def clave(celda: Celda, t: int) -> tuple[Celda, int | None]:
        # Después del horizonte el tiempo ya no importa: un solo estado por celda.
        return (celda, t) if t <= limite else (celda, None)

    padre: dict[tuple[Celda, int | None], PasoEnTiempo | None] = {clave(origen, tick): None}
    fila: deque[PasoEnTiempo] = deque([(origen, tick)])

    while fila:
        celda, t = fila.popleft()
        t_sig = t + 1
        con_reservas = t_sig <= limite
        # Esperar solo tiene sentido mientras haya reservas que esquivar.
        opciones = ([celda] if con_reservas else []) + vecinos(celda, ancho, alto)

        for siguiente in opciones:
            if siguiente in bloqueadas:
                continue
            k = clave(siguiente, t_sig)
            if k in padre:
                continue
            if con_reservas:
                if (siguiente, t_sig) in reservas:
                    continue
                if evitar_intercambio and siguiente != celda:
                    otro = reservas.get((siguiente, t))
                    if otro is not None and reservas.get((celda, t_sig)) == otro:
                        continue
            padre[k] = (celda, t)
            if siguiente == destino and puede_quedarse(t_sig):
                return _reconstruir_tiempo(padre, (siguiente, t_sig), clave)
            fila.append((siguiente, t_sig))

    return None


def _reconstruir_tiempo(padre, final: PasoEnTiempo, clave) -> list[PasoEnTiempo]:
    """Sigue los padres desde el estado final hasta el origen (que no se incluye)."""
    ruta: list[PasoEnTiempo] = []
    estado: PasoEnTiempo | None = final
    while estado is not None:
        ruta.append(estado)
        estado = padre[clave(*estado)]
    ruta.pop()  # el origen
    ruta.reverse()
    return ruta


def reservas_de_ruta(
    origen: Celda,
    ruta: list[PasoEnTiempo],
    tick: int,
    horizonte: int = HORIZONTE,
    permanencia: int | None = None,
) -> list[PasoEnTiempo]:
    """Lo que el agente reserva con mundo.reservar: (origen, tick), los pasos de `ruta` hasta
    tick + horizonte y, si la ruta termina antes, su celda final repetida:
      - permanencia None: hasta tick + horizonte (se estaciona ahí);
      - permanencia k: los k ticks siguientes a la llegada COMPLETOS, aunque pasen del horizonte.
        Es una estancia corta y conocida (la descarga); si se cortara en el horizonte, otro
        agente podría reservar el destino justo en el hueco, cuando este todavía lo ocupa.
    Con ruta == [] reserva quedarse en `origen`: así un agente quieto (en su base, esperando la
    transferencia) también se reserva.
    """
    limite = tick + horizonte
    resultado = [(origen, tick)] + [(celda, t) for celda, t in ruta if tick < t <= limite]
    celda_final, t_final = resultado[-1]
    llego = not ruta or ruta[-1][1] <= limite
    if permanencia is None or not llego:
        hasta = limite
    else:
        hasta = t_final + permanencia
    resultado.extend((celda_final, t) for t in range(t_final + 1, hasta + 1))
    return resultado


def estimar_costo(
    desde: Celda, ticks_ocupado: int, hacia: Celda, ancho: int, alto: int, bloqueadas: set[Celda]
) -> int | None:
    """Costo de la oferta de un carro (§7): ticks_ocupado + distancia BFS desde `desde` hasta
    la celda vecina de `hacia` más cercana (no se puede pasar por `hacia`: ahí está la
    cosechadora). 0 pasos si `desde` ya es vecina. None si ninguna vecina libre es alcanzable.
    """
    dist = distancias(desde, ancho, alto, bloqueadas | {hacia})
    candidatas = [dist[v] for v in vecinos(hacia, ancho, alto) if v not in bloqueadas and v in dist]
    if not candidatas:
        return None
    return ticks_ocupado + min(candidatas)


# Reglas del §10 que puede activar una ruta.
R3_CELDA_OCUPADA = "R3_celda_ocupada"
R4_INTERCAMBIO = "R4_intercambio"
R10_OBSTACULO = "R10_obstaculo"


def clasificar_desvio(
    origen: Celda,
    destino: Celda,
    tick: int,
    ancho: int,
    alto: int,
    bloqueadas: set[Celda],
    obstaculos: set[Celda],
    reservas: Reservas,
    horizonte: int = HORIZONTE,
    permanencia: int | None = None,
) -> list[str]:
    """Qué reglas del §10 alargaron la ruta de `origen` a `destino` (para el evento RESTRICCION).

    Compara cuánto tarda en llegar en cuatro versiones del problema:
      - R10_obstaculo: la ruta con obstáculos es más larga que sin ellos;
      - R3_celda_ocupada: las reservas de otros la alargan (esperar o rodear);
      - R4_intercambio: prohibir el intercambio la alarga todavía más.
    `bloqueadas` ya incluye los `obstaculos`. Devuelve las reglas en ese orden, o [] si la ruta
    es la más corta posible o si no hay ruta (eso es un bloqueo, no un desvío).
    """
    ruta = bfs_tiempo(origen, destino, tick, ancho, alto, bloqueadas, reservas, horizonte, permanencia)
    espacial = bfs(origen, destino, ancho, alto, bloqueadas)
    if ruta is None or espacial is None:
        return []

    reglas = []
    sin_obstaculos = bfs(origen, destino, ancho, alto, bloqueadas - obstaculos)
    if sin_obstaculos is not None and len(espacial) > len(sin_obstaculos):
        reglas.append(R10_OBSTACULO)

    con_intercambio = _bfs_tiempo(
        origen, destino, tick, ancho, alto, bloqueadas, reservas, horizonte, False, permanencia
    )
    if con_intercambio is not None and len(con_intercambio) > len(espacial):
        reglas.append(R3_CELDA_OCUPADA)
    if con_intercambio is None or len(ruta) > len(con_intercambio):
        reglas.append(R4_INTERCAMBIO)
    return reglas
