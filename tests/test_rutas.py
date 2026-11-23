"""BFS, vecindad y resolución de conflictos de movimiento (R1, R2, §4.2).  [Dueño: Oswaldo]

Convención: (x, y) con origen arriba a la izquierda; N = y - 1, E = x + 1, S = y + 1, O = x - 1.
"""

from itertools import product

from harvest_sim.rutas import (
    R3_CELDA_OCUPADA,
    R4_INTERCAMBIO,
    R10_OBSTACULO,
    _bfs_tiempo,
    bfs,
    bfs_tiempo,
    clasificar_desvio,
    distancias,
    elegir_celda_objetivo,
    estimar_costo,
    reservas_de_ruta,
    siguiente_paso,
    vecinos,
)

BODEGA = (0, 0)


def _celdas(ancho, alto):
    return [(x, y) for y in range(alto) for x in range(ancho)]


def _dentro(celda, ancho, alto):
    return 0 <= celda[0] < ancho and 0 <= celda[1] < alto


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _todas_las_rutas(ancho, alto, bloqueadas=frozenset()):
    """(origen, destino, ruta) para cada par de celdas libres del mapa."""
    libres = [c for c in _celdas(ancho, alto) if c not in bloqueadas]
    for origen, destino in product(libres, repeat=2):
        yield origen, destino, bfs(origen, destino, ancho, alto, set(bloqueadas))


def test_movimiento_dentro_del_mapa():
    """R1: toda celda de una ruta y todo vecino están dentro del mapa."""
    for ancho, alto in [(4, 3), (5, 5), (1, 4), (7, 2)]:
        for celda in _celdas(ancho, alto):
            assert all(_dentro(v, ancho, alto) for v in vecinos(celda, ancho, alto))
        for _, _, ruta in _todas_las_rutas(ancho, alto):
            assert ruta is not None
            assert all(_dentro(c, ancho, alto) for c in ruta)


def test_movimiento_un_paso_cuatro_vecinos():
    """R2: celdas consecutivas de una ruta son vecinas de 4 (sin diagonales ni saltos)."""
    for ancho, alto in [(4, 3), (5, 5)]:
        for origen, _, ruta in _todas_las_rutas(ancho, alto, bloqueadas={(2, 1)}):
            camino = [origen, *ruta]
            for a, b in zip(camino, camino[1:]):
                assert _manhattan(a, b) == 1, f"salto de {a} a {b}"

    # siguiente_paso también avanza una sola celda en vecindad de 4.
    for destino in [(3, 2), (0, 2), (3, 0)]:
        pos, ruta = (0, 0), bfs((0, 0), destino, 4, 3, set())
        while pos != destino:
            paso, ruta = siguiente_paso(pos, ruta, destino, 4, 3, set(), set())
            assert paso is not None and _manhattan(pos, paso) == 1
            pos = paso


def test_vecinos_orden_nesw():
    """vecinos() devuelve N, E, S, O en ese orden y descarta los que caen fuera del mapa."""
    assert vecinos((1, 1), 4, 3) == [(1, 0), (2, 1), (1, 2), (0, 1)]  # interior: los 4
    assert vecinos((0, 0), 4, 3) == [(1, 0), (0, 1)]  # esquina sup. izq.: sin N ni O
    assert vecinos((3, 2), 4, 3) == [(3, 1), (2, 2)]  # esquina inf. der.: sin E ni S
    assert vecinos((2, 0), 4, 3) == [(3, 0), (2, 1), (1, 0)]  # borde superior: sin N
    assert vecinos((0, 0), 1, 1) == []  # mapa de una celda
    assert (1, 1) not in vecinos((1, 1), 4, 3)  # una celda no es vecina de sí misma


def test_bfs_ruta_mas_corta_y_determinista():
    """Misma entrada -> misma ruta; la longitud es la mínima; sin el origen y con el destino."""
    assert bfs((0, 0), (2, 0), 4, 3, set()) == [(1, 0), (2, 0)]
    # Expandiendo N, E, S, O, primero agota el E y después baja.
    assert bfs((0, 0), (2, 2), 4, 3, set()) == [(1, 0), (2, 0), (2, 1), (2, 2)]

    for origen, destino, ruta in _todas_las_rutas(5, 4):
        assert len(ruta) == _manhattan(origen, destino)  # sin obstáculos, la mínima
        if ruta:
            assert origen not in ruta
            assert ruta[-1] == destino
        assert bfs(origen, destino, 5, 4, set()) == ruta  # determinista

    # Con un muro la ruta rodea y sigue siendo la más corta (6 pasos en vez de 2).
    muro = {(1, 0), (1, 1), (1, 2)}
    ruta = bfs((0, 1), (2, 1), 4, 4, muro)
    assert len(ruta) == 6
    assert ruta == bfs((0, 1), (2, 1), 4, 4, set(muro))


def test_bfs_respeta_bloqueadas_y_devuelve_none():
    """No pasa por celdas bloqueadas (p. ej. la bodega, R9); sin ruta posible devuelve None."""
    # Sin bloquear, el camino más corto de (0, 1) a (1, 0) cruza la bodega.
    assert bfs((0, 1), (1, 0), 4, 3, set()) == [(0, 0), (1, 0)]
    # Con la bodega bloqueada (cosechadora, R9) la rodea.
    assert bfs((0, 1), (1, 0), 4, 3, {BODEGA}) == [(1, 1), (1, 0)]

    for bloqueadas in [{BODEGA}, {BODEGA, (2, 1), (2, 2)}]:
        for _, _, ruta in _todas_las_rutas(5, 4, bloqueadas):
            assert ruta is not None
            assert not set(ruta) & bloqueadas

    # Destino encerrado: no hay ruta.
    assert bfs((0, 2), (3, 0), 4, 3, {(2, 0), (3, 1)}) is None
    # Origen encerrado: no hay ruta.
    assert bfs((0, 0), (3, 2), 4, 3, {(1, 0), (0, 1)}) is None
    # Destino bloqueado (p. ej. ocupado por otro agente): no hay ruta.
    assert bfs((0, 2), BODEGA, 4, 3, {BODEGA}) is None
    # Muro que parte el mapa en dos.
    assert bfs((0, 1), (3, 1), 4, 3, {(2, 0), (2, 1), (2, 2)}) is None


def test_bfs_origen_igual_destino():
    """Devuelve lista vacía."""
    assert bfs((1, 1), (1, 1), 4, 3, set()) == []
    assert bfs((0, 0), (0, 0), 1, 1, set()) == []
    # Aunque el agente esté rodeado, ya está donde quería.
    assert bfs((1, 1), (1, 1), 4, 3, {(1, 0), (2, 1), (1, 2), (0, 1)}) == []


def test_celda_objetivo_excluye_siguiente_de_serpentina():
    """§5.2: evita la siguiente celda del camino salvo que sea la única opción."""
    # Mapa 5 x 4. La cosechadora espera en (2, 1) y la siguiente celda de su serpentina
    # es (3, 1). El carro está en (4, 1): (3, 1) es la vecina más cercana (1 paso).
    cosechadora, carro, siguiente = (2, 1), (4, 1), (3, 1)
    bloqueadas = {BODEGA, cosechadora}

    assert elegir_celda_objetivo(carro, cosechadora, 5, 4, bloqueadas, set()) == siguiente
    # Si hay que evitarla, toma la mejor de las demás: N (2, 0) y S (2, 2) a 3 pasos; gana N.
    assert elegir_celda_objetivo(carro, cosechadora, 5, 4, bloqueadas, {siguiente}) == (2, 0)

    # Única opción: cosechadora en (0, 1); N es la bodega y S (0, 2) está ocupada.
    # Solo queda E (1, 1), que es la siguiente de la serpentina: la usa de todos modos.
    bloqueadas = {BODEGA, (0, 1), (0, 2)}
    assert elegir_celda_objetivo((3, 0), (0, 1), 4, 3, bloqueadas, {(1, 1)}) == (1, 1)

    # La única otra opción existe pero no se puede alcanzar: también usa la de `evitar`.
    # Cosechadora en (1, 1) en un mapa 3 x 3; O (0, 1) queda encerrada por la bodega y (0, 2).
    bloqueadas = {BODEGA, (1, 1), (1, 0), (0, 2), (1, 2)}
    assert elegir_celda_objetivo((2, 0), (1, 1), 3, 3, bloqueadas, {(2, 1)}) == (2, 1)

    # Nunca devuelve la bodega ni una ocupada; si no queda nada alcanzable, None.
    bloqueadas = {BODEGA, (0, 1), (1, 1), (0, 2)}
    assert elegir_celda_objetivo((3, 2), (0, 1), 4, 3, bloqueadas, set()) is None


def test_celda_objetivo_desempate_nesw():
    """A igual distancia BFS, gana el orden N, E, S, O."""
    cosechadora = (2, 2)
    bloqueadas = {BODEGA, cosechadora}
    # Las cuatro vecinas de (2, 2): N (2, 1), E (3, 2), S (2, 3), O (1, 2).

    # N y E a 1 paso -> N.
    assert elegir_celda_objetivo((3, 1), cosechadora, 5, 5, bloqueadas, set()) == (2, 1)
    # E y S a 2 pasos (N y O a 4) -> E.
    assert elegir_celda_objetivo((4, 3), cosechadora, 5, 5, bloqueadas, set()) == (3, 2)
    # S y O a 1 paso -> S.
    assert elegir_celda_objetivo((1, 3), cosechadora, 5, 5, bloqueadas, set()) == (2, 3)
    # Gana la distancia antes que el orden: O a 1 paso, N a 3 -> O.
    assert elegir_celda_objetivo((0, 2), cosechadora, 5, 5, bloqueadas, set()) == (1, 2)
    # El carro ya está en una vecina: distancia 0, se queda ahí.
    assert elegir_celda_objetivo((1, 2), cosechadora, 5, 5, bloqueadas, set()) == (1, 2)


def test_siguiente_paso_recalcula_o_espera():
    """§4.2: celda ocupada -> recalcula con BFS; sin ruta -> (None, ruta) y el agente espera."""
    ruta = [(1, 1), (2, 1)]

    # Celda libre: da el paso y devuelve el resto de la ruta, sin modificar la original.
    assert siguiente_paso((0, 1), ruta, (2, 1), 4, 3, set(), set()) == ((1, 1), [(2, 1)])
    assert ruta == [(1, 1), (2, 1)]

    # Celda ocupada: recalcula esquivándola. Sin bloqueadas fijas, rodea por arriba.
    paso, resto = siguiente_paso((0, 1), ruta, (2, 1), 4, 3, {(1, 1)}, set())
    assert (paso, resto) == ((0, 0), [(1, 0), (2, 0), (2, 1)])

    # Con la bodega bloqueada (cosechadora), rodea por abajo.
    paso, resto = siguiente_paso((0, 1), ruta, (2, 1), 4, 3, {(1, 1)}, {BODEGA})
    assert (paso, resto) == ((0, 2), [(1, 2), (2, 2), (2, 1)])
    assert not {paso, *resto} & {(1, 1), BODEGA}

    # Sin ruta: espera, devuelve (None, ruta original).
    encerrado = {(1, 1), (0, 2)}
    assert siguiente_paso((0, 1), ruta, (2, 1), 4, 3, encerrado, {BODEGA}) == (None, ruta)
    # Destino ocupado por otro agente y ya está a un paso: también espera.
    assert siguiente_paso((1, 1), [(2, 1)], (2, 1), 4, 3, {(2, 1)}, set()) == (None, [(2, 1)])

    # Ruta vacía o vieja (su primera celda no es vecina): la calcula de nuevo.
    assert siguiente_paso((0, 1), [], (2, 1), 4, 3, set(), set()) == ((1, 1), [(2, 1)])
    assert siguiente_paso((0, 1), [(3, 2)], (2, 1), 4, 3, set(), set()) == ((1, 1), [(2, 1)])

    # Ya llegó: nada que mover.
    assert siguiente_paso((2, 1), [], (2, 1), 4, 3, set(), set()) == (None, [])

    # R4: dos agentes que van uno hacia el otro nunca intercambian posiciones,
    # porque cada uno ve la celda del otro como ocupada.
    a, b = (0, 1), (1, 1)
    paso_a, _ = siguiente_paso(a, [b], (2, 1), 4, 3, {b}, set())
    assert paso_a != b


# =========================================================== segunda entrega: rutas en el tiempo


def _verificar_ruta_en_tiempo(origen, ruta, tick, ancho, alto, bloqueadas, reservas, horizonte=10):
    """Cada paso: un tick después del anterior, esperar o vecino de 4 (R1, R2), nunca bloqueada
    (R10) y, dentro del horizonte, ni reservada por otro (R3) ni intercambio (R4)."""
    anterior = (origen, tick)
    for celda, t in ruta:
        c0, t0 = anterior
        assert t == t0 + 1, f"salto de tiempo de {t0} a {t}"
        assert _dentro(celda, ancho, alto)
        assert celda == c0 or _manhattan(celda, c0) == 1, f"salto de {c0} a {celda}"
        assert celda not in bloqueadas
        if t <= tick + horizonte:
            assert (celda, t) not in reservas, f"usa ({celda}, {t}), reservada"
            otro = reservas.get((celda, t0))
            assert celda == c0 or otro is None or reservas.get((c0, t)) != otro, "intercambio"
        anterior = (celda, t)


def _como_reservas(agente, pasos):
    return {paso: agente for paso in pasos}


def test_bfs_tiempo_sin_reservas_es_la_ruta_mas_corta():
    """Sin reservas llega en la distancia BFS, sin esperar; determinista; [] y None como bfs."""
    muro = {(2, 0), (2, 1), (2, 2)}
    for bloqueadas in (set(), muro):
        for origen in _celdas(5, 4):
            if origen in bloqueadas:
                continue
            dist = distancias(origen, 5, 4, bloqueadas)
            for destino in dist:
                ruta = bfs_tiempo(origen, destino, 7, 5, 4, bloqueadas, {})
                assert len(ruta) == dist[destino] == len(bfs(origen, destino, 5, 4, bloqueadas))
                assert ruta == bfs_tiempo(origen, destino, 7, 5, 4, bloqueadas, {})
                if ruta:
                    assert ruta[-1] == (destino, 7 + len(ruta))
                _verificar_ruta_en_tiempo(origen, ruta, 7, 5, 4, bloqueadas, {})

    assert bfs_tiempo((1, 1), (1, 1), 0, 4, 3, set(), {}) == []
    assert bfs_tiempo((0, 2), (3, 0), 0, 4, 3, {(2, 0), (3, 1)}, {}) is None  # destino encerrado
    assert bfs_tiempo((0, 2), BODEGA, 0, 4, 3, {BODEGA}, {}) is None  # destino bloqueado
    assert bfs_tiempo((0, 1), (3, 1), 0, 4, 3, {(2, 0), (2, 1), (2, 2)}, {}) is None  # mapa partido


def test_bfs_tiempo_respeta_reservas():
    """Pasillo de 1 celda: dos rutas opuestas. La segunda espera; ninguna (celda, t) se repite
    entre las dos y no hay intercambio."""
    # Mapa 5 x 3 con un muro en x = 2 y un hueco en (2, 1):
    #   y=0   A  .  #  .  B
    #   y=1   .  .  _  .  .
    #   y=2   .  .  #  .  .
    muro = {(2, 0), (2, 2)}
    ruta_a = bfs_tiempo((0, 0), (4, 2), 0, 5, 3, muro, {})
    assert len(ruta_a) == 6  # sin nadie más, la más corta
    reservas_a = _como_reservas("carro_1", reservas_de_ruta((0, 0), ruta_a, 0))

    ruta_b = bfs_tiempo((4, 0), (0, 2), 0, 5, 3, muro, reservas_a)
    assert ruta_b is not None
    assert len(ruta_b) > 6  # tuvo que esperar a que A cruzara el hueco
    _verificar_ruta_en_tiempo((4, 0), ruta_b, 0, 5, 3, muro, reservas_a)

    # Ninguna (celda, t) compartida, contando las celdas finales en las que se quedan.
    pasos_a = reservas_de_ruta((0, 0), ruta_a, 0, horizonte=20)
    pasos_b = reservas_de_ruta((4, 0), ruta_b, 0, horizonte=20)
    assert not set(pasos_a) & set(pasos_b)
    # Y ningún intercambio: posiciones de los dos en cada tick.
    pos_a = {t: c for c, t in pasos_a}
    pos_b = {t: c for c, t in pasos_b}
    for t in range(20):
        assert not (pos_a[t] == pos_b[t + 1] and pos_b[t] == pos_a[t + 1])


def test_bfs_tiempo_no_se_intercambia():
    """R4: si otro va de c2 a c1 entre t y t + 1, no se puede ir de c1 a c2."""
    # Mapa 2 x 1: A en (1, 0) va a (0, 0); B en (0, 0) quiere (1, 0). B no puede cruzarse ni
    # quedarse (A llega a su celda): no hay ruta.
    reservas = {((1, 0), 0): "A", ((0, 0), 1): "A"}
    assert bfs_tiempo((0, 0), (1, 0), 0, 2, 1, set(), reservas) is None
    # Sin el chequeo de intercambio sí "pasaría" (eso sería una colisión).
    assert _bfs_tiempo((0, 0), (1, 0), 0, 2, 1, set(), reservas, 10, False) == [((1, 0), 1)]

    # Mapa 3 x 2: con lugar para hacerse a un lado, B rodea por abajo.
    reservas = _como_reservas("A", [((1, 0), 0)] + [((0, 0), t) for t in range(1, 11)])
    ruta = bfs_tiempo((0, 0), (1, 0), 0, 3, 2, set(), reservas)
    assert ruta == [((0, 1), 1), ((1, 1), 2), ((1, 0), 3)]
    _verificar_ruta_en_tiempo((0, 0), ruta, 0, 3, 2, set(), reservas)


def test_bfs_tiempo_espera_y_horizonte():
    """Espera en vez de entrar a una celda reservada; después del horizonte las reservas no cuentan."""
    # Pasillo 3 x 1: (1, 0) está reservada en el tick 1, así que espera un tick en el origen.
    reservas = {((1, 0), 1): "X"}
    assert bfs_tiempo((0, 0), (2, 0), 0, 3, 1, set(), reservas) == [
        ((0, 0), 1), ((1, 0), 2), ((2, 0), 3),
    ]

    # No llega a un destino que otro tiene reservado más tarde: llega después de esa reserva.
    reservas = {((2, 0), 5): "X"}
    ruta = bfs_tiempo((0, 0), (2, 0), 0, 4, 1, set(), reservas)
    assert ruta[-1] == ((2, 0), 6)
    assert ((2, 0), 5) not in ruta
    # Con horizonte 3, esa reserva (tick 5) ya no cuenta: llega en 2.
    assert len(bfs_tiempo((0, 0), (2, 0), 0, 4, 1, set(), reservas, horizonte=3)) == 2

    # Una reserva que dura todo el horizonte sobre la única celda de paso: cruza después.
    reservas = _como_reservas("X", [((1, 0), t) for t in range(1, 11)])
    ruta = bfs_tiempo((0, 0), (2, 0), 0, 3, 1, set(), reservas)
    assert ruta[-2:] == [((1, 0), 11), ((2, 0), 12)]


def test_bfs_tiempo_nunca_pisa_bloqueadas_ni_reservas():
    """Con distintas reservas de otro agente, toda ruta encontrada cumple R1, R2, R3, R4 y R10."""
    obstaculos = {(2, 1), (2, 2)}
    otros = [
        ((4, 0), bfs_tiempo((4, 0), (0, 3), 0, 5, 4, obstaculos, {})),
        ((0, 3), bfs_tiempo((0, 3), (4, 0), 0, 5, 4, obstaculos, {})),
        ((3, 3), []),  # un agente quieto
    ]
    for origen_otro, ruta_otro in otros:
        reservas = _como_reservas("X", reservas_de_ruta(origen_otro, ruta_otro, 0))
        for origen in _celdas(5, 4):
            if origen in obstaculos or origen == origen_otro:
                continue
            for destino in [(0, 0), (4, 3), (1, 2), (3, 1)]:
                ruta = bfs_tiempo(origen, destino, 0, 5, 4, obstaculos, reservas)
                if ruta is not None:
                    _verificar_ruta_en_tiempo(origen, ruta, 0, 5, 4, obstaculos, reservas)
                    assert ruta == [] or ruta[-1][0] == destino


def test_reservas_de_ruta_recorta_y_rellena():
    """Reserva desde su celda actual hasta el horizonte; si la ruta acaba antes, se queda al final."""
    ruta = [((1, 0), 6), ((2, 0), 7)]
    assert reservas_de_ruta((0, 0), ruta, 5, horizonte=4) == [
        ((0, 0), 5), ((1, 0), 6), ((2, 0), 7), ((2, 0), 8), ((2, 0), 9),
    ]
    larga = [((x, 0), 5 + x) for x in range(1, 9)]
    assert reservas_de_ruta((0, 0), larga, 5, horizonte=3) == [
        ((0, 0), 5), ((1, 0), 6), ((2, 0), 7), ((3, 0), 8),
    ]
    # Agente quieto: reserva su celda todo el horizonte.
    assert reservas_de_ruta((3, 2), [], 0, horizonte=2) == [((3, 2), 0), ((3, 2), 1), ((3, 2), 2)]


def test_distancias():
    assert distancias((0, 0), 3, 2, set()) == {
        (0, 0): 0, (1, 0): 1, (0, 1): 1, (2, 0): 2, (1, 1): 2, (2, 1): 3,
    }
    assert distancias((0, 0), 3, 1, {(1, 0)}) == {(0, 0): 0}


def test_estimar_costo():
    """ticks_ocupado + distancia BFS a la vecina libre más cercana de la cosechadora."""
    # Mapa 4 x 3, cosechadora en (2, 1). Desde la base (1, 0): (2, 0) y (1, 1) a 1 paso.
    assert estimar_costo((1, 0), 0, (2, 1), 4, 3, set()) == 1
    assert estimar_costo((1, 0), 7, (2, 1), 4, 3, set()) == 8
    # Ya es vecina: solo cuenta lo que le falta de su fila.
    assert estimar_costo((2, 0), 5, (2, 1), 4, 3, set()) == 5
    # Solo queda libre la vecina S (2, 2) y no se cruza por la cosechadora: rodea (4 pasos).
    assert estimar_costo((0, 0), 0, (2, 1), 4, 3, {(2, 0), (1, 1), (3, 1)}) == 4
    # Sin vecina alcanzable: None.
    assert estimar_costo((0, 0), 0, (3, 2), 4, 3, {(3, 1), (2, 2)}) is None


def test_clasificar_desvio():
    """Una regla del §10 por cada causa del desvío; nada si la ruta ya es la más corta."""
    assert clasificar_desvio((0, 0), (2, 0), 0, 3, 2, set(), set(), {}) == []
    # R10: un obstáculo en medio obliga a rodear.
    assert clasificar_desvio((0, 0), (2, 0), 0, 3, 2, {(1, 0)}, {(1, 0)}, {}) == [R10_OBSTACULO]
    # Rodear la bodega (cosechadora) no es rodear un obstáculo.
    assert clasificar_desvio((0, 1), (1, 0), 0, 3, 2, {BODEGA}, set(), {}) == []
    # R3: la celda de paso está reservada por otro y hay que esperar.
    reservas = {((1, 0), 1): "X"}
    assert clasificar_desvio((0, 0), (2, 0), 0, 3, 1, set(), set(), reservas) == [R3_CELDA_OCUPADA]
    # R4: el otro viene de frente; sin intercambio, hay que rodear.
    reservas = _como_reservas("A", [((1, 0), 0)] + [((0, 0), t) for t in range(1, 11)])
    assert clasificar_desvio((0, 0), (1, 0), 0, 3, 2, set(), set(), reservas) == [R4_INTERCAMBIO]
    # Sin ruta: no es desvío (es bloqueo).
    assert clasificar_desvio((0, 0), (2, 0), 0, 3, 1, {(1, 0)}, {(1, 0)}, {}) == []
