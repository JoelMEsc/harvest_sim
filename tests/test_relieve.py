"""Relieve del DEM Copernicus en el mapa y consumo por pendiente (docs/especificacion_terreno.md §8).  [Joel]"""

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

rasterio = pytest.importorskip("rasterio")

from pyproj import Transformer  # noqa: E402

from harvest_sim.config import cargar_config  # noqa: E402
from harvest_sim.mapa.convertir import Marco  # noqa: E402
from harvest_sim.mundo import Mundo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
MAPA = json.loads((RAIZ / "config" / "mapas" / "el_pueblito.json").read_text(encoding="utf-8"))
DEM = RAIZ / "config" / "mapas" / "el_pueblito_dem.tif"


def _bilineal_a_mano(lon, lat):
    """Interpolación bilineal hecha aquí (no con reproject) entre los 4 píxeles del DEM más cercanos."""
    with rasterio.open(DEM) as f:
        datos = f.read(1).astype(float)
        col, fila = ~f.transform * (lon, lat)
    c, r = col - 0.5, fila - 0.5  # los valores del DEM están en el centro de cada píxel
    c0, r0 = math.floor(c), math.floor(r)
    tc, tr = c - c0, r - r0
    v = datos[r0:r0 + 2, c0:c0 + 2]
    return (v[0, 0] * (1 - tc) * (1 - tr) + v[0, 1] * tc * (1 - tr) + v[1, 0] * (1 - tc) * tr + v[1, 1] * tc * tr)


@pytest.mark.parametrize("celda", [(20, 20), (40, 30), (60, 10)])
def test_alturas_coinciden_con_el_dem(celda):
    x, y = celda
    s = MAPA["tamano_celda_m"]
    marco = Marco(*MAPA["geo"]["origen_utm"], MAPA["geo"]["rumbo_grados"])
    e, n = marco.a_utm((x + 0.5) * s, (y + 0.5) * s)
    lon, lat = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True).transform(e, n)
    assert MAPA["altura_m"][y][x] == pytest.approx(_bilineal_a_mano(lon, lat), abs=0.05)


def test_el_mapa_trae_relieve_y_atribucion():
    assert len(MAPA["altura_m"]) == MAPA["alto"] and all(len(f) == MAPA["ancho"] for f in MAPA["altura_m"])
    campo = [MAPA["altura_m"][y][x] for celdas in MAPA["lotes"].values() for x, y in celdas]
    assert 1690 < min(campo) < max(campo) < 1750  # Los Altos de Jalisco
    assert max(campo) - min(campo) > 5             # sí hay relieve
    assert "Copernicus DEM GLO-30" in MAPA["geo"]["atribucion"]


class Dummy:
    def __init__(self, agent_id):
        self.agent_id, self.capacidad, self.carga, self.estado, self.posicion = agent_id, 360, 0, "YENDO_A_BODEGA", None


def _subida_y_bajada(mundo):
    """Dos celdas de campo vecinas con distinta altura: (baja, alta)."""
    h = MAPA["altura_m"]
    for x, y in sorted(mundo._celdas_campo):
        if (x + 1, y) in mundo._celdas_campo and h[y][x + 1] - h[y][x] > 0.5:
            return (x, y), (x + 1, y)
    raise AssertionError("no hay dos celdas vecinas con desnivel")


def _gasto(mundo, desde, hasta):
    carro = Dummy("carro_1")
    mundo.registrar(carro)
    carro.posicion = hasta
    antes = carro.combustible
    mundo.actualizar_combustible(carro, True, desde=desde)
    return round(antes - carro.combustible, 2)


def test_con_factor_cero_el_consumo_no_cambia():
    config = cargar_config(RAIZ / "config" / "escenario_g.json")
    abajo, arriba = _subida_y_bajada(Mundo(config))
    assert _gasto(Mundo(config), abajo, arriba) == config.combustible["consumo_por_celda_carro"]


def test_subir_cuesta_mas_que_bajar():
    config = cargar_config(RAIZ / "config" / "escenario_g.json")
    config = replace(config, combustible={**config.combustible, "factor_pendiente": 2.0})
    mundo = Mundo(config)
    abajo, arriba = _subida_y_bajada(mundo)
    base = config.combustible["consumo_por_celda_carro"]
    subida = _gasto(Mundo(config), abajo, arriba)
    bajada = _gasto(Mundo(config), arriba, abajo)
    dh = MAPA["altura_m"][arriba[1]][arriba[0]] - MAPA["altura_m"][abajo[1]][abajo[0]]
    assert subida == pytest.approx(base * (1 + 2.0 * dh / MAPA["tamano_celda_m"]), abs=0.01)
    assert bajada == base < subida


def test_sin_relieve_el_factor_no_hace_nada():
    config = cargar_config(RAIZ / "config" / "escenario_a.json")
    config = replace(config, combustible={**config.combustible, "factor_pendiente": 5.0})
    assert Mundo(config).factor_pendiente((1, 1), (2, 1)) == 1.0
