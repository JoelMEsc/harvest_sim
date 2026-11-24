"""Campo, obstáculos y grano esperado (la fórmula en un solo lugar).  [Dueño: Joel]"""

import pytest

from harvest_sim.datos import celdas_de_campo, expandir_obstaculos, grano_esperado, obstaculos, rendimiento


def mundo(**cambios):
    return {"ancho": 4, "alto": 3, "grano_por_celda": 1, "obstaculos": [], **cambios}


def test_campo_sin_obstaculos():
    """4 x 3: el campo son las filas 1 y 2, 4 x 2 = 8 celdas; con 2 de grano por celda, 16."""
    assert celdas_de_campo(mundo()) == {(x, y) for x in range(4) for y in (1, 2)}
    assert grano_esperado(mundo()) == 8
    assert grano_esperado(mundo(grano_por_celda=2)) == 16


def test_campo_con_obstaculos():
    """Dos obstáculos en el campo: 8 - 2 = 6 celdas."""
    m = mundo(obstaculos=[[1, 1], [2, 2]])
    assert obstaculos(m) == {(1, 1), (2, 2)}
    assert (1, 1) not in celdas_de_campo(m) and len(celdas_de_campo(m)) == 6
    assert grano_esperado(m) == 6


def test_mundo_sin_tamano_o_sin_lista_de_obstaculos():
    assert grano_esperado({}) is None and celdas_de_campo({}) == set()
    assert grano_esperado({"ancho": 4, "alto": 3}) == 8  # sin la lista (trace viejo): sin obstáculos


def test_expandir_celdas_y_regiones():
    """Región que empieza en (1, 2) de 2 x 2 en un mapa de 6 x 5: (1,2), (2,2), (1,3), (2,3). La celda (2, 2)
    también viene suelta: cuenta una vez. Resultado ordenado por fila (y) y luego columna (x)."""
    seccion = {"celdas": [[4, 1], [2, 2]], "regiones": [{"inicio": [1, 2], "tamano": [2, 2]}]}
    assert expandir_obstaculos(seccion, 6, 5) == [[4, 1], [1, 2], [2, 2], [1, 3], [2, 3]]
    assert expandir_obstaculos({"celdas": [], "regiones": []}, 6, 5) == []
    assert expandir_obstaculos(None, 6, 5) == []


@pytest.mark.parametrize("seccion, fragmento", [
    ({"celdas": [[6, 1]]}, "fuera del mapa"),
    ({"celdas": [[1, -1]]}, "fuera del mapa"),
    ({"celdas": [[2, 0]]}, "fila 0"),
    ({"regiones": [{"inicio": [4, 3], "tamano": [3, 1]}]}, "fuera del mapa"),
    ({"regiones": [{"inicio": [1, 1], "tamano": [0, 2]}]}, "tamaño debe ser >= 1"),
    ({"celdas": [[1, "2"]]}, "debe ser [x, y]"),
    ({"regiones": [{"inicio": [1, 1]}]}, "inicio"),
    ({"otra": []}, "solo las claves"),
    # una pared completa en la fila 1 deja las filas 2..4 sin acceso desde la bodega
    ({"regiones": [{"inicio": [0, 1], "tamano": [6, 1]}]}, "sin acceso"),
])
def test_restricciones_de_los_obstaculos(seccion, fragmento):
    with pytest.raises(ValueError, match=None) as error:
        expandir_obstaculos(seccion, 6, 5)
    assert fragmento in str(error.value)


def test_grano_esperado_con_rendimiento_variable():
    """Mundo 3 × 3 (campo: filas 1 y 2), rendimiento por celda: 1+2+3 + 2+2+1 = 11; un obstáculo en (1, 2)
    vale 0 y no cuenta. `rendimiento` de una celda sin matriz es grano_por_celda."""
    m = mundo(ancho=3, alto=3, rendimiento=[[0, 0, 0], [1, 2, 3], [2, 0, 1]], obstaculos=[[1, 2]])
    assert grano_esperado(m) == 1 + 2 + 3 + 2 + 1
    assert rendimiento(m, (2, 1)) == 3 and rendimiento(mundo(grano_por_celda=4), (0, 1)) == 4
