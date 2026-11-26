"""Despacho aprendido (M1): Q-learning y SARSA tabulares para decidir cuándo pedir carro.  [Joel]

Especificación: docs/especificacion_mejoras.md §M1.
"""

import json
import logging
from pathlib import Path

import pytest

from ayuda_datos import cargar_script
from harvest_sim.aprendizaje import PEDIR, SEGUIR, Despachador, clave, estado_de, ruta_tabla
from harvest_sim.config import cargar_config
from harvest_sim.datos import validar_trace
from harvest_sim.datos.experimentos import ESTRATEGIAS, TODAS_LAS_ESTRATEGIAS, aplicar_estrategia, simulador_real

RAIZ = Path(__file__).resolve().parents[1]
P = {"alfa": 0.5, "gamma": 0.9, "epsilon": 0.0, "costo_solicitud": 10.0, "castigo_cliff": 100.0}


class Agente:
    def __init__(self, agent_id, estado="COSECHANDO", posicion=(0, 0), carga=0, capacidad=10):
        self.agent_id, self.estado, self.posicion = agent_id, estado, posicion
        self.carga, self.capacidad = carga, capacidad
        self.servicio = self.contratado = None


class MundoFalso:
    ancho, alto = 10, 10

    def __init__(self, *agentes):
        self._agentes = {a.agent_id: a for a in agentes}

    def estado_de(self, a):
        return self._agentes[a].estado

    def posicion(self, a):
        return self._agentes[a].posicion


def test_estado_tramos_carros_libres_distancia_y_otra():
    h1 = Agente("cosechadora_1", carga=7, posicion=(5, 5))
    h2 = Agente("cosechadora_2")
    h2.servicio = "cosechadora_2#1"
    mundo = MundoFalso(h1, h2, Agente("carro_1", "EN_BASE", (5, 6)), Agente("carro_2", "YENDO_A_BODEGA", (0, 0)))
    assert estado_de(h1, mundo) == (3, 1, 0, 1)
    assert estado_de(h1, mundo, llena=True)[0] == 5
    h2.servicio = None
    mundo._agentes["carro_1"].posicion = (0, 9)
    assert estado_de(h1, mundo) == (3, 1, 2, 0)


def test_q_learning_usa_el_maximo_y_sarsa_la_accion_tomada():
    """Misma experiencia: s --pedir (r = −10, más −3 de ocio)--> s' donde se elige seguir."""
    for algoritmo, esperado in (("qlearning", 0.5 * (-13 + 0.9 * 4.0)), ("sarsa", 0.5 * (-13 + 0.9 * -2.0))):
        d = Despachador(algoritmo, P, aprender=True, tabla={"1,0,0,0": [-2.0, 4.0]})
        d._pendiente["h"] = ("0,0,0,0", PEDIR, -13.0)
        d._transicion("h", "1,0,0,0", SEGUIR)
        assert d.q["0,0,0,0"][PEDIR] == pytest.approx(esperado)


def test_cliff_castiga_y_obliga_a_pedir():
    h = Agente("cosechadora_1", carga=10)
    mundo = MundoFalso(h, Agente("carro_1", "EN_BASE"))
    d = Despachador("qlearning", P, aprender=True)
    d.decidir(h, mundo, umbral=False)  # seguir (empate, sin umbral)
    d.forzada(h, mundo)
    assert d.cliffs == 1
    s_lleno = clave(estado_de(h, mundo, llena=True))
    assert d._pendiente["cosechadora_1"][:2] == (s_lleno, PEDIR)
    assert d.recompensa_episodio == -100 - 10
    d.terminar()
    assert d.q[s_lleno][PEDIR] == pytest.approx(0.5 * -10)


def test_q_learning_no_toma_el_maximo_en_el_estado_forzado():
    """En la tolva llena solo se puede pedir: el objetivo usa Q(llena, pedir), no el 0 de Q(llena, seguir)."""
    h = Agente("cosechadora_1", carga=10)
    mundo = MundoFalso(h, Agente("carro_1", "EN_BASE"))
    s_lleno = clave(estado_de(h, mundo, llena=True))
    d = Despachador("qlearning", P, aprender=True, tabla={s_lleno: [0.0, -50.0]})
    d._pendiente["cosechadora_1"] = ("4,1,0,0", SEGUIR, 0.0)
    d.forzada(h, mundo)
    assert d.q["4,1,0,0"][SEGUIR] == pytest.approx(0.5 * (-100 + 0.9 * -50.0))


def test_ocio_se_cobra_a_quien_espera():
    d = Despachador("qlearning", P, aprender=True)
    llena, cosechando = Agente("h1", "LLENA_ESPERANDO"), Agente("h2")
    d._pendiente = {"h1": ("s", PEDIR, 0.0), "h2": ("s", SEGUIR, 0.0)}
    d.tick([llena, cosechando])
    d.tick([llena, cosechando])
    assert d._pendiente["h1"][2] == -2 and d._pendiente["h2"][2] == 0


def test_sin_aprender_respalda_con_el_umbral_en_estados_nuevos():
    h = Agente("cosechadora_1", carga=5)
    mundo = MundoFalso(h, Agente("carro_1", "EN_BASE"))
    d = Despachador("qlearning", P, aprender=False, tabla={})
    assert d.decidir(h, mundo, umbral=False) is False
    assert d.decidir(h, mundo, umbral=True) is False  # mismo tramo: no es una decisión nueva
    h.carga = 8
    assert d.decidir(h, mundo, umbral=True) is True  # tramo nuevo, estado nuevo: respaldo del umbral
    assert d.respaldo_umbral == 2 and d.decisiones == 2 and d.q == {}  # evaluar no cambia la tabla
    h.carga = 3
    s = clave(estado_de(h, mundo))
    d.q[s] = [-1.0, -5.0]
    assert d.decidir(h, mundo, umbral=True) is False  # la tabla manda sobre el umbral


def test_una_decision_por_tramo_y_ciclo():
    h = Agente("cosechadora_1", carga=0)
    mundo = MundoFalso(h, Agente("carro_1", "EN_BASE"))
    d = Despachador("qlearning", P, aprender=False, tabla={"0,1,0,0": [0.0, -1.0], "1,1,0,0": [-1.0, 0.0]})
    assert [d.decidir(h, mundo, False) for _ in range(3)] == [False, False, False] and d.decisiones == 1
    h.carga = 2
    assert d.decidir(h, mundo, False) is True  # tramo 1: pide
    h.carga = 0  # después de la transferencia, el ciclo nuevo vuelve a decidir en el tramo 0
    assert d.decidir(h, mundo, False) is False and d.decisiones == 3


def test_guardar_y_cargar(tmp_path):
    d = Despachador("sarsa", P, tabla={"0,0,0,0": [1.23456, -2.0]})
    ruta = d.guardar(tmp_path / "t.json", escenario="x")
    otro = Despachador.cargar(ruta)
    assert otro.algoritmo == "sarsa" and otro.q == {"0,0,0,0": [1.2346, -2.0]} and not otro.aprender
    assert json.loads(ruta.read_text())["escenario"] == "x"


def test_ruta_por_defecto_y_explicita():
    assert ruta_tabla({"aviso": "sarsa"}, "escenario_d").name == "qtabla_sarsa_escenario_d.json"
    assert ruta_tabla({"aviso": "qlearning", "qtabla": "/tmp/q.json"}, "x") == Path("/tmp/q.json")


def _config(tmp_path, **politica):
    datos = json.loads((RAIZ / "config" / "escenario_d.json").read_text(encoding="utf-8"))
    datos["politica"] = {**datos.get("politica", {}), **politica}
    ruta = tmp_path / "d.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


@pytest.mark.parametrize("politica,patron", [
    ({"aviso": "intuicion"}, "politica.aviso"),
    ({"aviso": "qlearning", "asignacion": "directa"}, "requiere politica.asignacion = subasta"),
    ({"aviso": "qlearning", "asignacion": "subasta", "qtabla": ""}, "politica.qtabla"),
])
def test_config_invalida(tmp_path, politica, patron):
    with pytest.raises(ValueError, match=patron):
        cargar_config(_config(tmp_path, **politica))


def test_sin_tabla_falla_con_instrucciones(tmp_path):
    config = cargar_config(_config(tmp_path, aviso="qlearning", asignacion="subasta", qtabla=str(tmp_path / "no.json")))
    from harvest_sim.simulacion import ejecutar
    with pytest.raises(ValueError, match="entrenar_despacho.py"):
        ejecutar(config)


def test_las_4_estrategias_no_cambian():
    assert list(ESTRATEGIAS) == ["base", "subasta", "anticipada", "anticipada_plus"]
    assert list(TODAS_LAS_ESTRATEGIAS)[4:] == ["qlearning", "sarsa"]


def test_entrenar_evaluar_y_reproducir(tmp_path):
    """Entrenar 3 episodios en D llena la tabla; con la tabla, la corrida valida, entrega todo y es determinista."""
    logging.disable(logging.WARNING)
    entrenador = cargar_script("tools/entrenar_despacho.py")
    base = json.loads((RAIZ / "config" / "escenario_d.json").read_text(encoding="utf-8"))
    despachador, curva = entrenador.entrenar(base, "qlearning", 3, {"epsilon": 0.3})
    assert [f["seed"] for f in curva] == [1000, 1001, 1002]
    assert all(f["decisiones"] > 0 for f in curva) and despachador.q
    tabla = despachador.guardar(tmp_path / "q.json")
    config = {**aplicar_estrategia(base, "qlearning"), "seed": 0}
    config["politica"]["qtabla"] = str(tabla)
    a, b = simulador_real(config), simulador_real(config)
    logging.disable(logging.NOTSET)
    assert validar_trace(a) == [] and a["metricas"]["porcentaje_entregado"] == 100.0
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["config"]["politica"]["aviso"] == "qlearning"


# --- M1 en el log y en Unity: evento DECISION_DESPACHO, procedencia de la tabla y métricas -------------------

def _corrida(estrategia, escenario="escenario_d", seed=0):
    logging.disable(logging.WARNING)
    base = json.loads((RAIZ / "config" / f"{escenario}.json").read_text(encoding="utf-8"))
    trace = simulador_real({**aplicar_estrategia(base, estrategia), "seed": seed})
    logging.disable(logging.NOTSET)
    return trace


def _decisiones(trace):
    return [e for t in trace["ticks"] for e in t["cambios"] if e["tipo"] == "DECISION_DESPACHO"]


@pytest.fixture(scope="module")
def corrida_sarsa_d():
    return _corrida("sarsa")


def test_el_log_trae_cada_decision_con_su_estado_y_valores(corrida_sarsa_d):
    t = corrida_sarsa_d
    assert validar_trace(t) == []
    ds = _decisiones(t)
    assert ds and all(d["agente"].startswith("cosechadora_") for d in ds)
    assert {d["origen"] for d in ds} <= {"tabla", "umbral", "forzada"}  # sin exploración al evaluar
    assert all(set(d["estado"]) == {"tramo", "carros_libres", "distancia", "otra_pidio"} for d in ds)
    for d in ds:
        if d["origen"] == "tabla":
            preferida = "pedir" if d["q"]["pedir"] > d["q"]["seguir"] else "seguir"
            assert d["accion"] == preferida  # la acción es la que la tabla prefiere
    m = t["metricas"]
    assert m["decisiones_despacho"] == len(ds)
    assert m["pedidos_tabla"] == sum(1 for d in ds if d["accion"] == "pedir" and d["origen"] == "tabla")
    assert m["cliffs_despacho"] == sum(1 for d in ds if d["origen"] == "forzada")


def test_cada_llamada_tiene_su_decision(corrida_sarsa_d):
    """Cada cfp que abre un servicio sale en el mismo tick que una decisión de pedir de esa cosechadora."""
    t = corrida_sarsa_d
    for tick in t["ticks"]:
        pedidos = {e["agente"] for e in tick["cambios"] if e["tipo"] == "DECISION_DESPACHO" and e["accion"] == "pedir"}
        for e in tick["cambios"]:
            if e["tipo"] == "DECISION_DESPACHO" and e["accion"] == "pedir":
                assert any(m["tipo"] == "MENSAJE_ENVIADO" and m["tipo_mensaje"] == "SOLICITUD_SERVICIO"
                           and m["de"] == e["agente"] for m in tick["cambios"]), tick["tick"]
        assert pedidos <= {e["de"] for e in tick["cambios"] if e["tipo"] == "MENSAJE_ENVIADO"}


def test_la_config_dice_que_tabla_decidio(corrida_sarsa_d):
    a = corrida_sarsa_d["config"]["aprendizaje"]
    ruta = RAIZ / "config" / a["tabla"]
    assert a["algoritmo"] == "sarsa" and ruta.is_file()
    import hashlib
    assert a["sha256"] == hashlib.sha256(ruta.read_bytes()).hexdigest()
    assert a["estados"] == len(json.loads(ruta.read_text())["estados"])


def test_sin_aviso_aprendido_el_log_no_cambia():
    t = _corrida("anticipada")
    assert not _decisiones(t) and "aprendizaje" not in t["config"] and "decisiones_despacho" not in t["metricas"]


def test_al_entrenar_se_marca_la_exploracion(tmp_path):
    from harvest_sim.simulacion import ejecutar
    base = json.loads((RAIZ / "config" / "escenario_d.json").read_text(encoding="utf-8"))
    ruta = tmp_path / "d.json"
    ruta.write_text(json.dumps({**aplicar_estrategia(base, "qlearning"), "seed": 1000}), encoding="utf-8")
    logging.disable(logging.WARNING)
    t = ejecutar(cargar_config(ruta), Despachador("qlearning", {"epsilon": 0.5}, aprender=True, semilla=3))
    logging.disable(logging.NOTSET)
    assert validar_trace(t) == []
    assert "exploracion" in {d["origen"] for d in _decisiones(t)}
    assert t["config"]["aprendizaje"]["entrenando"] is True


@pytest.mark.parametrize("cambio,patron", [
    ({"accion": "esperar"}, "accion"),
    ({"origen": "intuicion"}, "origen"),
    ({"estado": {"tramo": 9, "carros_libres": 0, "distancia": 0, "otra_pidio": False}}, "fuera de rango"),
    ({"estado": {"tramo": 1}}, "estado debe ser"),
    ({"q": {"seguir": "alto", "pedir": 1}}, "q debe ser"),
    ({"origen": "forzada", "accion": "seguir"}, "forzada"),
    ({"agente": "carro_1"}, "solo una cosechadora"),
])
def test_el_validador_rechaza_decisiones_mal_formadas(corrida_sarsa_d, cambio, patron):
    import copy
    from harvest_sim.datos.trace import calcular_checksum
    t = copy.deepcopy(corrida_sarsa_d)
    tick = next(tk for tk in t["ticks"] if any(e["tipo"] == "DECISION_DESPACHO" for e in tk["cambios"]))
    evento = next(e for e in tick["cambios"] if e["tipo"] == "DECISION_DESPACHO")
    evento.update(cambio)
    tick["checksum"] = calcular_checksum(tick)
    assert any(patron in e for e in validar_trace(t))
