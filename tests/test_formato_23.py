"""Trace 2.3: mapa real (caminos, fuera de campo, lotes, relieve y geometría).  [Dueño: Joel]

Contrato en docs/especificacion_terreno.md §6. El fixture es el guion `tools/traces_ejemplo_23.py`
(campo en L con dos lotes); cada prueba rompe una sola regla en una copia y revisa el mensaje.
"""

import copy
import json
from pathlib import Path

import pytest

from ayuda_datos import cargar_script
from harvest_sim.datos import calcular_checksum, cargar_trace, validar_trace
from harvest_sim.datos.campo import celdas_de_campo, grano_esperado, tiene_mapa

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE_23 = RAIZ / "tests" / "fixtures" / "trace_ejemplo_23.json"


@pytest.fixture(scope="module")
def base():
    return cargar_trace(FIXTURE_23)


def resellar(trace):
    for t in trace["ticks"]:
        t["checksum"] = calcular_checksum({"tick": t["tick"], "cambios": t["cambios"]})
    return trace


def test_el_fixture_es_el_guion_y_valida(base):
    guion = cargar_script("tools/traces_ejemplo_23.py").generar()
    assert json.dumps(guion, sort_keys=True) == json.dumps(base, sort_keys=True)
    assert base["schema_version"] == "2.3"
    assert validar_trace(base) == []


def test_campo_con_mapa(base):
    """Con mapa la fila 0 no es especial: el campo es todo menos caminos, fuera, obstáculos y servicio."""
    mundo = base["mundo"]
    assert tiene_mapa(mundo)
    campo = celdas_de_campo(mundo)
    assert len(campo) == 15 and grano_esperado(mundo) == 15
    assert campo == {tuple(c) for celdas in mundo["lotes"].values() for c in celdas}
    assert not campo & {tuple(c) for c in mundo["caminos"] + mundo["fuera_de_campo"] + mundo["obstaculos"]}


def test_sin_mapa_sigue_la_regla_de_siempre():
    mundo = {"ancho": 3, "alto": 3, "obstaculos": [[1, 1]]}
    assert not tiene_mapa(mundo)
    assert celdas_de_campo(mundo) == {(0, 1), (2, 1), (0, 2), (1, 2), (2, 2)}


def test_la_simulacion_sin_mapa_sigue_siendo_2_2():
    from harvest_sim.config import cargar_config
    from harvest_sim.simulacion import ejecutar
    trace = ejecutar(cargar_config(RAIZ / "config" / "escenario_a.json"))
    assert trace["schema_version"] == "2.2"


def _con(base, **cambios):
    t = copy.deepcopy(base)
    for clave, valor in cambios.items():
        if valor is None:
            del t["mundo"][clave]
        else:
            t["mundo"][clave] = valor
    return resellar(t)


@pytest.mark.parametrize("clave,valor,patron", [
    ("tamano_celda_m", 0, "tamano_celda_m"),
    ("caminos", [[9, 9]], "caminos tiene la celda"),
    ("caminos", [[0, 0], [0, 0]], "caminos tiene celdas repetidas"),
    ("fuera_de_campo", [[0, 1]], "caminos y en fuera_de_campo"),
    ("fuera_de_campo", [[5, 4]], "fuera_de_campo y en obstaculos"),
    ("altura_m", [[1.0]], "altura_m debe ser una matriz"),
    ("geo", {"epsg": 32613}, "mundo.geo: falta origen_utm"),
])
def test_campos_del_mapa_invalidos(base, clave, valor, patron):
    errores = validar_trace(_con(base, **{clave: valor}))
    assert any(patron in e for e in errores), errores[:3]


def test_lotes_deben_cubrir_el_campo(base):
    t = copy.deepcopy(base)
    t["mundo"]["lotes"]["A"] = t["mundo"]["lotes"]["A"][:-1]
    assert any("no coinciden con el campo" in e for e in validar_trace(resellar(t)))


def test_campos_23_exigen_la_version_23(base):
    t = resellar(copy.deepcopy(base))
    t["schema_version"] = "2.2"
    assert any("requieren schema_version 2.3" in e for e in validar_trace(t))


def test_obstaculo_en_la_fila_0_se_permite_con_mapa(base):
    t = copy.deepcopy(base)
    t["mundo"]["fuera_de_campo"] = [c for c in t["mundo"]["fuera_de_campo"] if c != [5, 0]]
    t["mundo"]["obstaculos"] = t["mundo"]["obstaculos"] + [[5, 0]]
    assert validar_trace(resellar(t)) == []


def test_visor_acepta_23(base):
    viewer = cargar_script("viz/viewer.py")
    assert viewer.Reproductor(base).total == base["meta"]["total_ticks"]
