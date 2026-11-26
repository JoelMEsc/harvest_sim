"""Del KML del cultivo al mapa de celdas (docs/especificacion_terreno.md §4–§5).  [Dueños: Oswaldo y Joel]"""

import json
import math
from collections import deque
from pathlib import Path

import pytest

pytest.importorskip("shapely")
pytest.importorskip("pyproj")

from harvest_sim.mapa import kml as K  # noqa: E402
from harvest_sim.mapa.convertir import ErrorMapa, construir_desde_config, convertir, rumbo_comun  # noqa: E402
from harvest_sim.mapa.pasadas import generar_pasadas, rumbo_de_linea, rumbo_optimo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
MAPAS = RAIZ / "config" / "mapas"
KML = MAPAS / "el_pueblito.kml"


@pytest.fixture(scope="module")
def generado():
    return construir_desde_config(MAPAS / "el_pueblito.convertidor.json")


def test_el_json_del_repo_esta_al_dia(generado):
    """config/mapas/el_pueblito.json es exactamente lo que produce el convertidor (no se edita a mano)."""
    mapa, _, salida = generado
    assert json.loads(salida.read_text(encoding="utf-8")) == json.loads(json.dumps(mapa))


def test_clasificacion_por_nombre():
    assert K.clasificar("cultivo_loteA", K.POLIGONO) == K.LOTE
    assert K.clasificar("Lote norte rumbo=45", K.POLIGONO) == K.LOTE
    assert K.clasificar("Brecha 2", K.LINEA) == K.CAMINO
    assert K.clasificar("Obstáculo poste", K.PUNTO) == K.OBSTACULO
    assert K.clasificar("Surco Lote B", K.LINEA) == K.GUIA
    assert K.clasificar("Bodega", K.PUNTO) == K.BODEGA and K.clasificar("base_1", K.PUNTO) == K.BASE
    assert K.clasificar("Ruta sin título", K.LINEA) == K.CAMINO
    assert K.clasificar("algo", K.POLIGONO) == K.OBSTACULO
    assert K.rumbo_del_nombre("cultivo_loteA rumbo=225") == 45.0
    assert K.rumbo_del_nombre("cultivo_loteA") is None


def test_el_kml_tiene_lo_esperado():
    elementos = K.leer_kml(KML)
    tipos = [e.tipo for e in elementos]
    assert tipos.count(K.LOTE) == 3 and tipos.count(K.GUIA) == 3
    assert tipos.count(K.CAMINO) == 8 and tipos.count(K.OBSTACULO) == 2


def test_rumbo_de_las_guias_como_en_pasadas_cultivo():
    """Con la proyección local de CultivoDesdeKML (equirectangular), el rumbo de cada guía es el que daría
    PasadasCultivo.cs: 57.5° (A), 55.5° (B) y 48.9° (C)."""
    elementos = K.leer_kml(KML)
    todos = [c for e in elementos for c in e.coordenadas]
    lon0 = sum(c[0] for c in todos) / len(todos)
    lat0 = sum(c[1] for c in todos) / len(todos)
    r = 6378137.0

    def local(c):
        return ((c[0] - lon0) * math.radians(1) * r * math.cos(math.radians(lat0)), (c[1] - lat0) * math.radians(1) * r)

    rumbos = {e.nombre: rumbo_de_linea([local(c) for c in e.coordenadas]) for e in elementos if e.tipo == K.GUIA}
    assert rumbos["Surco Lote A"] == pytest.approx(57.5, abs=0.1)
    assert rumbos["Surco Lote B"] == pytest.approx(55.5, abs=0.1)
    assert rumbos["Surco Lote C"] == pytest.approx(48.9, abs=0.1)


def test_rumbos_en_utm_y_rumbo_comun(generado):
    """En UTM el norte de la cuadrícula difiere del geográfico (convergencia ~0.8° aquí); el rumbo común es el
    promedio ponderado por área."""
    mapa, _, _ = generado
    r = mapa["resumen_lotes"]
    assert [r[n]["modo_rumbo"] for n in "ABC"] == ["guia"] * 3
    assert r["A"]["rumbo_grados"] == pytest.approx(57.5 - 0.8, abs=0.3)
    assert mapa["geo"]["rumbo_grados"] == pytest.approx(51.6, abs=0.2)
    assert rumbo_comun([(179.0, 1.0), (1.0, 1.0)]) in (pytest.approx(0.0, abs=1e-6), pytest.approx(180.0, abs=1e-6))


def test_area_dentro_de_la_tolerancia(generado):
    """C1: el área de las celdas de campo difiere menos de 5 % del área real cosechable."""
    mapa, reporte, _ = generado
    linea = next(x for x in reporte if x.startswith("área:"))
    error = float(linea.split("(")[1].split(",")[1].split("%")[0])
    assert abs(error) < 5
    assert {n: len(c) for n, c in mapa["lotes"].items()} == {"A": 353, "B": 487, "C": 922}


def test_arboleda_y_poste_son_obstaculos(generado):
    mapa, _, _ = generado
    s = mapa["tamano_celda_m"]
    obstaculos = {tuple(c) for c in mapa["obstaculos"]}
    arboleda = max(mapa["geo"]["formas"]["obstaculos"], key=len)
    cx = sum(p[0] for p in arboleda) / len(arboleda)
    cy = sum(p[1] for p in arboleda) / len(arboleda)
    assert (int(cx // s), int(cy // s)) in obstaculos
    assert len(obstaculos) >= 40


def _vecinos(c):
    x, y = c
    return [(x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)]


def test_caminos_forman_una_red_que_toca_cada_lote(generado):
    """C2b: después de soldar, los caminos (y el patio) son una sola pieza que toca la bodega y cada lote."""
    mapa, _, _ = generado
    caminos = {tuple(c) for c in mapa["caminos"]}
    bodega = tuple(mapa["bodega"])
    assert bodega in caminos and all(tuple(b) in caminos for b in mapa["bases"])
    vistos, cola = {bodega}, deque([bodega])
    while cola:
        for v in _vecinos(cola.popleft()):
            if v in caminos and v not in vistos:
                vistos.add(v)
                cola.append(v)
    assert vistos == caminos
    for nombre, celdas in mapa["lotes"].items():
        assert any(v in caminos for c in celdas for v in _vecinos(tuple(c))), nombre


def test_patio_junto_al_camino_y_fuera_del_campo(generado):
    mapa, _, _ = generado
    campo = {tuple(c) for cs in mapa["lotes"].values() for c in cs}
    caminos_puros = {tuple(c) for c in mapa["caminos"]} - {tuple(mapa["bodega"])} - {tuple(b) for b in mapa["bases"]}
    for c in [mapa["bodega"]] + mapa["bases"]:
        assert tuple(c) not in campo
        assert any(v in caminos_puros for v in _vecinos(tuple(c))), c
    assert len(mapa["bases"]) == 8


def test_soldaduras_reportadas(generado):
    mapa, reporte, _ = generado
    assert len(mapa["soldaduras"]) >= 8
    assert max(sd["metros"] for sd in mapa["soldaduras"]) <= 5.0
    assert any(sd["camino"] == "camino_norte_este" and sd["metros"] == pytest.approx(3.92, abs=0.05)
               for sd in mapa["soldaduras"])
    assert sum(x.startswith("soldadura:") for x in reporte) == len(mapa["soldaduras"])


def test_sin_tolerancia_la_red_queda_partida():
    """La soldadura sí hace algo: con tolerancia 0 el KML actual queda en varias piezas."""
    with pytest.raises(ErrorMapa, match="partida"):
        convertir(KML, {"tolerancia_union_m": 0.0})


def _kml_de_prueba(tmp_path, hueco_m: float) -> Path:
    """Un lote cuadrado de ~200 m y dos caminos alineados con un hueco de `hueco_m` metros entre ellos."""
    lat, lon = 21.46, -102.47
    dlat = 1 / 111_320
    dlon = 1 / (111_320 * math.cos(math.radians(lat)))

    def c(x, y):
        return f"{lon + x * dlon:.8f},{lat + y * dlat:.8f},0"

    def pm(nombre, tipo, puntos):
        coords = " ".join(c(*p) for p in puntos)
        if tipo == "poligono":
            geom = f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
        else:
            geom = f"<LineString><coordinates>{coords}</coordinates></LineString>"
        return f"<Placemark><name>{nombre}</name>{geom}</Placemark>"

    cuerpo = (pm("cultivo_loteA", "poligono", [(0, 0), (200, 0), (200, 200), (0, 200), (0, 0)])
              + pm("camino_1", "linea", [(-3, -3), (-3, 100)])
              + pm("camino_2", "linea", [(-3, 100 + hueco_m), (-3, 203), (100, 203)]))
    ruta = tmp_path / "prueba.kml"
    ruta.write_text(f'<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>{cuerpo}'
                    f"</Document></kml>", encoding="utf-8")
    return ruta


def test_un_hueco_de_20_m_falla_con_nombre_y_distancia(tmp_path):
    with pytest.raises(ErrorMapa, match=r"camino_\d a (19\.\d|20\.\d) m de la red"):
        convertir(_kml_de_prueba(tmp_path, 20.0), {"n_bases": 2})


def test_un_hueco_de_3_m_se_suelda(tmp_path):
    mapa, reporte = convertir(_kml_de_prueba(tmp_path, 3.0), {"n_bases": 2})
    union = [sd for sd in mapa["soldaduras"] if {sd["camino"], sd["con"]} == {"camino_1", "camino_2"}]
    assert union and all(sd["metros"] == pytest.approx(3.0, abs=0.1) for sd in union), reporte
    assert len(mapa["lotes"]["A"]) > 200


def test_pasadas_de_un_rectangulo():
    """Rectángulo de 60 m (este-oeste) por 100 m (norte-sur), rumbo 0 (surcos norte-sur), ancho 6 m:
    10 pasadas de 100 - 2·8 = 84 m, en una zona, alternando el sentido."""
    lote = [(0.0, 0.0), (60.0, 0.0), (60.0, 100.0), (0.0, 100.0)]
    p = generar_pasadas(lote, 0.0)
    assert len(p) == 10
    assert all(x.largo == pytest.approx(84.0) for x in p)
    assert {x.zona for x in p} == {0}
    assert p[0].inicio[1] < p[0].fin[1] and p[1].inicio[1] > p[1].fin[1]


def test_rumbo_optimo_va_a_lo_largo():
    lote = [(0.0, 0.0), (60.0, 0.0), (60.0, 100.0), (0.0, 100.0)]
    assert rumbo_optimo(lote) in (0.0, 179.5, 0.5)


def test_un_obstaculo_parte_las_pasadas_en_zonas():
    lote = [(0.0, 0.0), (60.0, 0.0), (60.0, 100.0), (0.0, 100.0)]
    obstaculo = [(20.0, 40.0), (40.0, 40.0), (40.0, 60.0), (20.0, 60.0)]
    p = generar_pasadas(lote, 0.0, obs_poligonos=[obstaculo])
    assert len({x.zona for x in p}) > 1
