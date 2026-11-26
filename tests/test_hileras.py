"""Plan de hileras y rutas: realismo del movimiento de las cosechadoras.  [Joel]

Fase H0: la bandera `politica.movimiento` y la medición desde el log (`metricas.movimiento_cosechadoras`).
"""

import json
from pathlib import Path

import pytest

from harvest_sim.config import cargar_config
from harvest_sim.datos.metricas import movimiento_cosechadoras

RAIZ = Path(__file__).resolve().parents[1]


def _trace(movimientos, cosechadas):
    """Trace mínimo con una cosechadora: `movimientos` = poses por tick, `cosechadas` = {tick: celda}."""
    agentes = [{"id": "cosechadora_1", "tipo": "cosechadora", "capacidad": 10, "base": [0, 0]}]
    ticks = []
    for t, (x, y, o) in enumerate(movimientos):
        cambios = [{"tipo": "AGENTE", "id": "cosechadora_1",
                    "set": {"pose": {"x": x, "y": y, "orientacion": o},
                            "estado": "EN_BASE" if t == 0 else "COSECHANDO", "carga": 0}}]
        if t in cosechadas:
            cambios.append({"tipo": "CELDA_COSECHADA", "celda": list(cosechadas[t]), "agente": "cosechadora_1"})
        ticks.append({"tick": t, "cambios": cambios})
    return {"schema_version": "2.2", "meta": {"total_ticks": len(movimientos) - 1}, "config": {},
            "mundo": {"ancho": 4, "alto": 4, "bodega": [0, 0], "bases": {"cosechadora_1": [0, 0]}, "obstaculos": []},
            "agentes": agentes, "ticks": ticks}


def test_a_lo_largo_de_la_hilera_es_realista():
    t = _trace([(0, 0, "S"), (0, 1, "S"), (1, 1, "E"), (2, 1, "E"), (3, 1, "E")], {1: (0, 1), 2: (1, 1), 3: (2, 1), 4: (3, 1)})
    r = movimiento_cosechadoras(t)
    # entrar a (0, 1) desde la fila de servicio es de lado: así arranca hoy la serpentina
    assert (r["entradas_de_lado"], r["pasos_sobre_cultivo"], r["vueltas_instantaneas"]) == (1, 0, 0)


def test_cambio_de_pasada_de_lado_y_vuelta_instantanea():
    """Fin de la hilera y=1 en x=3; la serpentina baja de lado a (3, 2), la cosecha y regresa hacia el oeste."""
    poses = [(0, 0, "S"), (0, 1, "S"), (1, 1, "E"), (2, 1, "E"), (3, 1, "E"), (3, 2, "S"), (2, 2, "O")]
    t = _trace(poses, {1: (0, 1), 2: (1, 1), 3: (2, 1), 4: (3, 1), 5: (3, 2), 6: (2, 2)})
    r = movimiento_cosechadoras(t)
    assert r["entradas_de_lado"] == 2 and r["vueltas_instantaneas"] == 0  # E → S → O son dos giros de 90°
    t2 = _trace([(0, 0, "S"), (1, 0, "E"), (0, 0, "O")], {})
    assert movimiento_cosechadoras(t2)["vueltas_instantaneas"] == 1


def test_pisar_cultivo_sin_cosecharlo():
    t = _trace([(0, 0, "S"), (0, 1, "S"), (0, 2, "S")], {})
    assert movimiento_cosechadoras(t)["pasos_sobre_cultivo"] == 2


def test_bandera_de_movimiento(tmp_path):
    datos = json.loads((RAIZ / "config" / "escenario_a.json").read_text(encoding="utf-8"))
    assert cargar_config(RAIZ / "config" / "escenario_a.json").politica["movimiento"] == "celdas"
    datos["politica"] = {"movimiento": "en diagonal"}
    ruta = tmp_path / "a.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match="politica.movimiento"):
        cargar_config(ruta)


# --- H1: cabecera, pasadas, bloques y orden (mapa/cobertura.py) ------------------------------------------------

import math  # noqa: E402

from harvest_sim.mapa import cobertura as cb  # noqa: E402
from harvest_sim.mapa.dubins import camino, tipo_de_vuelta  # noqa: E402


def _rect(x0, x1, y0, y1):
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


def test_cabecera_de_un_rectangulo():
    celdas = _rect(0, 9, 0, 5)
    cab = cb.cabecera(celdas, 2)
    # extremos de las hileras: x 0-1 y 8-9 en cada fila; orillas: filas 0 y 5
    assert cab == {c for c in celdas if c[0] <= 1 or c[0] >= 8 or c[1] in (0, 5)}
    assert cb.celdas_de_cabecera(7.5, 12) == 2 and cb.celdas_de_cabecera(20, 12) == 4


def test_pasadas_paralelas_a_las_hileras_y_cobertura_completa():
    celdas = _rect(0, 9, 0, 5)
    r = cb.cobertura(celdas, 2)
    assert all(p.x0 == 2 and p.x1 == 7 for p in r.pasadas) and [p.y for p in r.pasadas] == [1, 2, 3, 4]
    cubiertas = r.cabecera | {c for p, _ in r.orden for c in p.celdas()}
    assert cubiertas == celdas and len(r.cabecera) + sum(p.largo for p in r.pasadas) == len(celdas)
    # boustrophedon: sentidos alternos y cada pasada empieza del lado donde terminó la anterior
    sentidos = [e for _, e in r.orden]
    assert all(a != b for a, b in zip(sentidos, sentidos[1:]))


def test_un_obstaculo_parte_en_bloques_y_rodea_de_cabecera():
    celdas = _rect(0, 19, 0, 7) - _rect(9, 10, 3, 4)
    r = cb.cobertura(celdas, 2)
    assert len(r.bloques) >= 3
    assert {(8, 3), (11, 3), (9, 2), (9, 5)} <= r.cabecera  # alrededor del obstáculo
    assert r.cabecera | {c for p, _ in r.orden for c in p.celdas()} == celdas


def test_orden_snake_como_fields2cover():
    assert cb.secuencia(6, "snake") == [0, 2, 4, 5, 3, 1]
    assert cb.secuencia(5, "snake") == [0, 2, 4, 3, 1]
    assert cb.secuencia(4, "boustrophedon") == [0, 1, 2, 3]


def test_el_patron_se_elige_por_el_costo_de_las_vueltas():
    celdas = _rect(0, 11, 0, 9)
    # vuelta muy cara entre pasadas vecinas (Ω) y barata saltando una (U): gana snake
    def vuelta(a, _ra, b, _rb):
        return 10 if abs(a[1] - b[1]) == 1 else abs(a[1] - b[1])
    assert set(cb.cobertura(celdas, 2, vuelta=vuelta).patron.values()) == {"snake"}
    assert set(cb.cobertura(celdas, 2).patron.values()) == {"boustrophedon"}


def test_el_pueblito_se_cubre_completo():
    mapa = json.loads((RAIZ / "config" / "mapas" / "el_pueblito.json").read_text(encoding="utf-8"))
    k = cb.celdas_de_cabecera(7.5, mapa["tamano_celda_m"])
    for nombre, lista in mapa["lotes"].items():
        celdas = {tuple(c) for c in lista}
        r = cb.cobertura(celdas, k)
        assert r.cabecera | {c for p, _ in r.orden for c in p.celdas()} == celdas, nombre
        assert len(r.cabecera) + sum(p.largo for p in r.pasadas) == len(celdas), nombre
        assert set(cb.recorrido_cabecera(r.cabecera, None)) == r.cabecera


# --- H2: curvas de Dubins (mapa/dubins.py) ---------------------------------------------------------------------

R = 7.5


@pytest.mark.parametrize("fin,largo,palabra", [
    ((30, 0, 0), 30.0, "LSL"),                       # recta
    ((0, 15, math.pi), math.pi * R, "LSL"),          # U exacta con d = 2R: media circunferencia
    ((0, 24, math.pi), math.pi * R + 9, "LSL"),      # U con recta de d - 2R
    ((0, -24, math.pi), math.pi * R + 9, "RSR"),     # la misma hacia la derecha
])
def test_largos_analiticos(fin, largo, palabra):
    c = camino((0, 0, 0), fin, R)
    assert c.largo == pytest.approx(largo) and c.palabra == palabra
    x, y, th = c.muestrear(0.5)[-1]
    assert (x, y) == pytest.approx(fin[:2], abs=1e-6)
    assert math.cos(th - fin[2]) == pytest.approx(1)


def test_vuelta_omega_cuando_no_cabe_la_u():
    assert tipo_de_vuelta(24, R) == "U" and tipo_de_vuelta(12, R) == "Ω"
    c = camino((0, 0, 0), (0, 12, math.pi), R)
    assert c.palabra in ("RLR", "LRL") and c.largo > math.pi * R
    profundidad = max(x for x, _, _ in c.muestrear(0.5))
    assert profundidad < 2 * 12  # cabe en una cabecera de 2 celdas de 12 m


def test_el_camino_respeta_el_radio():
    c = camino((0, 0, 0), (5, 40, math.pi / 2), R)
    paso = 0.01  # muestras a lo largo del arco: el giro entre dos muestras no puede pasar de paso / R
    poses = c.muestrear(paso)
    for (_, _, t0), (_, _, t1) in zip(poses, poses[1:]):
        giro = abs((t1 - t0 + math.pi) % (2 * math.pi) - math.pi)
        assert giro <= paso / R * 1.001 + 1e-9  # curvatura <= 1/R


# --- H3: la cosechadora respeta las hileras (R14) ---------------------------------------------------------------

import logging  # noqa: E402
from dataclasses import replace  # noqa: E402

from harvest_sim.datos import validar_trace  # noqa: E402
from harvest_sim.datos.experimentos import aplicar_estrategia, simulador_real  # noqa: E402
from harvest_sim.mundo import Mundo  # noqa: E402


def test_secuencia_alcanzable_rodea_un_obstaculo_sin_cruzar_cultivo():
    """Un lote con un obstáculo en medio: la cabecera del obstáculo es una isla que solo se alcanza cuando las
    pasadas llegan a ella. Cada celda se cosecha desde rastrojo o camino; cada pasada se entra de frente."""
    celdas = _rect(0, 19, 0, 9) - _rect(9, 10, 4, 5)
    caminos = {(x, -1) for x in range(-1, 21)}
    r = cb.cobertura(celdas, 2)
    orden, entradas, sin_alcance = cb.secuencia_alcanzable(r, (0, -1), caminos)
    assert sin_alcance == 0 and sorted(orden) == sorted(celdas) and len(orden) == len(celdas)
    hecho = set()
    for c in orden:
        if c in entradas:
            antes, rumbo = entradas[c]
            assert antes in hecho and (c[0] - antes[0], c[1] - antes[1]) == ((1, 0) if rumbo == "E" else (-1, 0))
        else:
            x, y = c
            assert {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} & (hecho | caminos), c
        hecho.add(c)
    isla = {(8, 4), (11, 4), (9, 3), (9, 6)}
    assert isla <= r.cabecera and max(orden.index(c) for c in isla) > orden.index(r.orden[0][0].celdas(r.orden[0][1])[0])


def test_hileras_requiere_mapa(tmp_path):
    datos = json.loads((RAIZ / "config" / "escenario_a.json").read_text(encoding="utf-8"))
    datos["politica"] = {"movimiento": "hileras"}
    ruta = tmp_path / "a.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match="requiere un mapa"):
        cargar_config(ruta)


@pytest.fixture(scope="module")
def mundo_g_hileras():
    c = cargar_config(RAIZ / "config" / "escenario_g.json")
    return Mundo(replace(c, politica={**c.politica, "movimiento": "hileras"}))


def test_el_recorrido_cubre_g_y_cada_pasada_tiene_entrada(mundo_g_hileras):
    m = mundo_g_hileras
    todas = m.camino("cosechadora_1") + m.camino("cosechadora_2")
    assert len(todas) == len(set(todas)) == len(m._celdas_campo)
    assert m.cabecera and m._entradas
    for inicio, (antes, rumbo) in m._entradas.items():
        assert antes[1] == inicio[1] and abs(antes[0] - inicio[0]) == 1 and rumbo in ("E", "O")
        assert antes in m.cabecera or antes in m.celdas_camino


def test_la_vuelta_cuesta_lo_que_la_curva_de_dubins(mundo_g_hileras):
    m = mundo_g_hileras
    # pasada vecina hacia el otro lado (Ω, d = 12 m < 2R = 15 m): 37.1 m → 37.1 / 12 · 6 / 5 = 3.7 → 4 ticks
    assert m._vuelta_ticks((10, 10), "E", (10, 11), "O") == 4
    # saltando una pasada (U, d = 24 m): πR + 9 = 32.6 m → 3.3 → 4 ticks
    assert m._vuelta_ticks((10, 10), "E", (10, 12), "O") == 4


@pytest.fixture(scope="module")
def corrida_g_hileras():
    logging.disable(logging.WARNING)
    base = json.loads((RAIZ / "config" / "escenario_g.json").read_text(encoding="utf-8"))
    config = aplicar_estrategia(base, "anticipada_plus")
    config["politica"] = {**config["politica"], "movimiento": "hileras"}
    trace = simulador_real(config)
    logging.disable(logging.NOTSET)
    return trace


def test_g_con_hileras_respeta_r14(corrida_g_hileras, mundo_g_hileras):
    t = corrida_g_hileras
    assert validar_trace(t) == [] and t["metricas"]["porcentaje_entregado"] == 100.0
    assert t["metricas"]["colisiones"] == 0 and t["metricas"]["pasos_sobre_cultivo"] == 0
    assert t["config"]["maquinas"]["radio_giro_m"] == 7.5
    cab = mundo_g_hileras.cabecera
    pos, cosechadas = {}, set()
    lado_en_pasada = 0
    for tick in t["ticks"]:
        nuevas = {tuple(e["celda"]) for e in tick["cambios"] if e["tipo"] == "CELDA_COSECHADA"}
        for e in tick["cambios"]:
            if e["tipo"] == "AGENTE" and e["id"].startswith("cosechadora") and "pose" in e["set"]:
                p = (e["set"]["pose"]["x"], e["set"]["pose"]["y"])
                if e["id"] in pos and p in nuevas and p not in cab and p[1] != pos[e["id"]][1]:
                    lado_en_pasada += 1
                pos[e["id"]] = p
        cosechadas |= nuevas
    assert lado_en_pasada == 0  # fuera de la cabecera nadie corta de lado
    reglas = [e["regla"] for tk in t["ticks"] for e in tk["cambios"] if e["tipo"] == "RESTRICCION"]
    assert "R14_hileras" in reglas


def test_sin_la_bandera_g_es_el_de_siempre(mundo_g_hileras):
    c = cargar_config(RAIZ / "config" / "escenario_g.json")
    m = Mundo(c)
    assert not m.hileras and not m.cabecera and not m._entradas
