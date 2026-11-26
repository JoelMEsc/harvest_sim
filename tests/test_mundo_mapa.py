"""Mundo con mapa real: escenario G (El Pueblito), R12, R13, zonas y descripción 2.3.  [Dueños: Carlos y Joel]

Especificación: docs/especificacion_terreno.md §6, §7 y §9.
"""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from harvest_sim.config import cargar_config
from harvest_sim.datos import TraceBuilder, validar_trace
from harvest_sim.datos.campo import celdas_de_campo
from harvest_sim.mundo import Mundo

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config"


class Dummy:
    def __init__(self, agent_id, capacidad=120):
        self.agent_id, self.capacidad, self.carga = agent_id, capacidad, 0
        self.estado, self.posicion = "EN_BASE", None


@pytest.fixture(scope="module")
def config_g():
    return cargar_config(CONFIG / "escenario_g.json")


@pytest.fixture
def mundo_g(config_g):
    return Mundo(config_g)


def test_g_toma_tamano_y_obstaculos_del_mapa(config_g):
    mapa = json.loads((CONFIG / "mapas" / "el_pueblito.json").read_text(encoding="utf-8"))
    assert (config_g.ancho, config_g.alto) == (mapa["ancho"], mapa["alto"])
    assert config_g.mapa["archivo"] == "mapas/el_pueblito.json" and len(config_g.mapa["sha256"]) == 64
    assert config_g.politica["respetar_cultivo"] is True


def _escribir(tmp_path, **cambios):
    datos = json.loads((CONFIG / "escenario_g.json").read_text(encoding="utf-8"))
    datos.update(cambios)
    datos["mapa"] = str((CONFIG / "mapas" / "el_pueblito.json").resolve())
    ruta = tmp_path / "g.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


@pytest.mark.parametrize("cambios,patron", [
    ({"ancho": 10}, "no coincide con el del mapa"),
    ({"obstaculos": {"celdas": [[1, 1]], "regiones": []}}, "los obstáculos vienen del mapa"),
    ({"num_carros": 5, "num_cosechadoras": 4}, "bases"),
    ({"politica": {"respetar_cultivo": "si"}}, "respetar_cultivo"),
])
def test_config_con_mapa_invalida(tmp_path, cambios, patron):
    with pytest.raises(ValueError, match=patron):
        cargar_config(_escribir(tmp_path, **cambios))


def test_mapa_inexistente(tmp_path):
    ruta = tmp_path / "g.json"
    datos = json.loads((CONFIG / "escenario_g.json").read_text(encoding="utf-8"))
    datos["mapa"] = "mapas/no_existe.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match="no existe el mapa"):
        cargar_config(ruta)


def test_el_mapa_se_encuentra_desde_un_directorio_temporal(tmp_path):
    """Los experimentos y el servidor escriben la configuración en otro lado: el mapa se busca en config/."""
    ruta = tmp_path / "g.json"
    ruta.write_text((CONFIG / "escenario_g.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert cargar_config(ruta).mapa["archivo"] == "mapas/el_pueblito.json"


def test_bodega_y_bases_del_mapa(mundo_g, config_g):
    assert mundo_g.bodega == tuple(config_g.mapa["bodega"])
    bases = [mundo_g.base_de(a) for a in ("carro_1", "carro_2", "cosechadora_1", "cosechadora_2")]
    assert bases == [tuple(b) for b in config_g.mapa["bases"][:4]]
    assert all(b in mundo_g.celdas_camino for b in bases)


def test_r12_fuera_de_campo_es_fijo_para_todos(mundo_g):
    for agente in ("carro_1", "cosechadora_1"):
        assert mundo_g.fuera_de_campo <= mundo_g.bloqueadas_fijas(agente)
        assert mundo_g.obstaculos <= mundo_g.bloqueadas_fijas(agente)
    assert mundo_g.bodega in mundo_g.bloqueadas_fijas("cosechadora_1")
    ruta = mundo_g.ruta_bfs(mundo_g.bodega, mundo_g.camino("cosechadora_1")[-1], set())
    assert ruta and not set(ruta) & (mundo_g.fuera_de_campo | mundo_g.obstaculos)


def test_r13_cultivo_en_pie_solo_para_carros(mundo_g):
    campo = mundo_g.cultivo_en_pie()
    assert len(campo) == 1762
    assert campo <= mundo_g.bloqueadas_para("carro_1")
    assert not campo & mundo_g.bloqueadas_para("cosechadora_1")
    cosechadora = Dummy("cosechadora_1")
    mundo_g.registrar(cosechadora)
    celda = mundo_g.camino("cosechadora_1")[0]
    cosechadora.posicion = celda
    mundo_g.cosechar("cosechadora_1", celda)
    assert celda not in mundo_g.bloqueadas_para("carro_1")  # ya es rastrojo
    assert celda not in mundo_g.cultivo_en_pie()


def test_sin_respetar_cultivo_nada_cambia(config_g):
    mundo = Mundo(replace(config_g, politica={**config_g.politica, "respetar_cultivo": False}))
    assert mundo.bloqueadas_para("carro_1") == mundo.bloqueadas_fijas("carro_1")


def test_zonas_cubren_el_campo_una_vez_y_empiezan_en_un_camino(mundo_g):
    caminos = [mundo_g.camino(f"cosechadora_{j}") for j in (1, 2)]
    todas = [c for cam in caminos for c in cam]
    assert len(todas) == len(set(todas)) == len(mundo_g._celdas_campo)
    assert set(todas) == mundo_g._celdas_campo
    for cam in caminos:
        assert any(v in mundo_g.celdas_camino for v in mundo_g.vecinos(cam[0]))
    assert sorted(mundo_g.zonas().values()) == [["A", "B"], ["C"]]
    assert max(len(c) for c in caminos) / len(todas) < 0.6  # reparto parejo


def test_una_fila_es_una_pasada(mundo_g):
    """Una fila de la cuadrícula es una pasada: dentro de cada tramo de la misma fila, la cosechadora avanza
    siempre en el mismo sentido (x creciente o decreciente), y las filas se alternan (boustrophedon)."""
    for j in (1, 2):
        cam = mundo_g.camino(f"cosechadora_{j}")
        tramos, actual = [], [cam[0]]
        for c in cam[1:]:
            if c[1] == actual[-1][1]:
                actual.append(c)
            else:
                tramos.append(actual)
                actual = [c]
        tramos.append(actual)
        for t in tramos:
            xs = [x for x, _ in t]
            assert xs == sorted(xs) or xs == sorted(xs, reverse=True), t
        sentidos = [t[-1][0] - t[0][0] for t in tramos if len(t) > 1]
        alternos = sum(1 for a, b in zip(sentidos, sentidos[1:]) if (a > 0) != (b > 0))
        assert alternos >= 0.8 * (len(sentidos) - 1)


def test_mas_cosechadoras_que_lotes_parte_el_mas_grande(config_g):
    mundo = Mundo(replace(config_g, num_cosechadoras=4, num_carros=2))
    zonas = mundo.zonas()
    assert len(zonas) == 4 and all(zonas.values())
    todas = [c for j in range(1, 5) for c in mundo.camino(f"cosechadora_{j}")]
    assert len(todas) == len(set(todas)) == 1762


def test_descripcion_23_valida(mundo_g, config_g):
    """El mundo con mapa se describe con los campos 2.3 y un trace con ese mundo valida."""
    d = mundo_g.descripcion()
    for clave in ("tamano_celda_m", "caminos", "fuera_de_campo", "lotes", "geo"):
        assert clave in d
    assert celdas_de_campo(d) == mundo_g._celdas_campo
    agentes = [{"id": a, "tipo": a.split("_")[0], "capacidad": 120 if a.startswith("cos") else 360,
                "base": list(mundo_g.base_de(a))} for a in ("cosechadora_1", "cosechadora_2", "carro_1", "carro_2")]
    builder = TraceBuilder({"nombre": "g", "seed": 0}, d, agentes)
    builder.agregar_tick(0, [{"tick": 0, "agent_id": a["id"], "tipo": a["tipo"],
                              "pose": {"x": a["base"][0], "y": a["base"][1], "orientacion": "N"},
                              "estado": "EN_BASE", "carga": {"actual": 0, "capacidad": a["capacidad"]}}
                             for a in agentes], [])
    trace = builder.construir()
    assert trace["schema_version"] == "2.3"
    assert validar_trace(trace) == []


def test_sin_mapa_el_mundo_es_el_de_siempre():
    mundo = Mundo(cargar_config(CONFIG / "escenario_a.json"))
    d = mundo.descripcion()
    assert not {"tamano_celda_m", "caminos", "fuera_de_campo", "lotes", "geo"} & set(d)
    assert mundo.bodega == (0, 0) and not mundo.respetar_cultivo
    assert mundo.bloqueadas_para("carro_1") == mundo.bloqueadas_fijas("carro_1")
