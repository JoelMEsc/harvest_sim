"""BFS, vecindad y resolución de conflictos de movimiento (R1, R2, §4.2).  [Dueño: Oswaldo]

Convención: (x, y) con origen arriba a la izquierda; N = y - 1, E = x + 1, S = y + 1, O = x - 1.
"""

from itertools import product

from harvest_sim.rutas import bfs, elegir_celda_objetivo, siguiente_paso, vecinos

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
