"""Servidor FastAPI (especificación de la segunda entrega §14).  [Dueño: Joel]

Se prueba con un simulador falso (el generador de ejemplo): así no depende de la simulación completa.
"""

import copy

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ayuda_datos import RAIZ, cargar_script  # noqa: E402
from harvest_sim.servidor import crear_app  # noqa: E402

GENERADOR = cargar_script("tools/generar_trace_ejemplo.py")


class Simulador:
    """Cuenta las llamadas y devuelve el trace de ejemplo (1 + 1) de la configuración recibida."""

    def __init__(self, falla=None, romper_trace=False):
        self.llamadas = []
        self.falla = falla
        self.romper_trace = romper_trace

    def __call__(self, config):
        self.llamadas.append(copy.deepcopy(config))
        if self.falla:
            raise self.falla
        trace = GENERADOR.generar({k: config[k] for k in GENERADOR.CONFIG if k in config})
        if self.romper_trace:
            trace["schema_version"] = "9.9"
        return trace


@pytest.fixture
def cliente():
    simulador = Simulador()
    return TestClient(crear_app(simulador=simulador, carpeta_config=RAIZ / "config")), simulador


def test_salud(cliente):
    c, _ = cliente
    r = c.get("/api/salud")
    assert r.status_code == 200 and r.json() == {"estado": "ok", "schema_version": "2.2", "simulador": "personalizado"}


def test_lista_de_escenarios_y_estrategias(cliente):
    c, _ = cliente
    datos = c.get("/api/escenarios").json()
    nombres = [e["nombre"] for e in datos["escenarios"]]
    assert {"escenario_a", "escenario_b", "escenario_c"} <= set(nombres)
    a = datos["escenarios"][nombres.index("escenario_a")]["parametros"]
    assert (a["ancho"], a["alto"], a["capacidad_cosechadora"], a["obstaculos"]) == (8, 7, 10, 0)
    assert datos["estrategias"] == ["base", "subasta", "anticipada", "anticipada_plus"]


def test_trace_de_un_escenario_con_estrategia_y_seed(cliente):
    c, simulador = cliente
    r = c.get("/api/escenarios/escenario_a/trace", params={"seed": 3, "estrategia": "anticipada"})
    assert r.status_code == 200
    trace = r.json()
    assert trace["schema_version"] == "2.2" and trace["meta"]["escenario"] == "escenario_a"
    config = simulador.llamadas[0]
    assert config["seed"] == 3 and config["politica"]["umbral_aviso"] == 0.7


def test_cache_por_configuracion(cliente):
    c, simulador = cliente
    for _ in range(3):
        assert c.get("/api/escenarios/escenario_b/trace").status_code == 200
    assert len(simulador.llamadas) == 1
    c.get("/api/escenarios/escenario_b/trace", params={"seed": 1})
    assert len(simulador.llamadas) == 2


def test_post_con_escenario_y_cambios_o_con_config_completa(cliente):
    c, simulador = cliente
    r = c.post("/api/simulaciones", json={"escenario": "escenario_c", "estrategia": "base", "seed": 2,
                                          "cambios": {"tasa_descarga": 3}})
    assert r.status_code == 200
    assert simulador.llamadas[-1]["tasa_descarga"] == 3 and simulador.llamadas[-1]["seed"] == 2
    config = {**GENERADOR.CONFIG, "nombre": "mio"}
    r = c.post("/api/simulaciones", json={"config": config})
    assert r.status_code == 200 and r.json()["meta"]["escenario"] == "mio"


@pytest.mark.parametrize("ruta, cuerpo, codigo, texto", [
    ("/api/escenarios/no_existe/trace", None, 404, "no existe"),
    ("/api/escenarios/escenario_a/trace?estrategia=otra", None, 422, "estrategia inválida"),
    ("/api/escenarios/escenario_a/trace?seed=-1", None, 422, ""),
    ("/api/simulaciones", {}, 422, "falta config o escenario"),
])
def test_errores_del_cliente(cliente, ruta, cuerpo, codigo, texto):
    c, _ = cliente
    r = c.post(ruta, json=cuerpo) if cuerpo is not None else c.get(ruta)
    assert r.status_code == codigo
    assert texto in r.text


def test_configuracion_invalida_trace_invalido_y_simulacion_no_disponible():
    casos = [(Simulador(falla=ValueError("capacidad_carro < capacidad_cosechadora")), 422, "configuración inválida"),
             (Simulador(romper_trace=True), 422, "el trace generado no es válido"),
             (Simulador(falla=NotImplementedError("Bloque B")), 503, "aún no está disponible")]
    for simulador, codigo, texto in casos:
        c = TestClient(crear_app(simulador=simulador, carpeta_config=RAIZ / "config"))
        r = c.get("/api/escenarios/escenario_a/trace")
        assert r.status_code == codigo and texto in r.text, (codigo, r.text)


def test_cors_para_origenes_locales(cliente):
    c, _ = cliente
    local = c.get("/api/salud", headers={"Origin": "http://localhost:8080"})
    assert local.headers.get("access-control-allow-origin") == "http://localhost:8080"
    externo = c.get("/api/salud", headers={"Origin": "https://ejemplo.com"})
    assert "access-control-allow-origin" not in externo.headers


def test_modo_ejemplo_por_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("HARVEST_SIMULADOR", "ejemplo")
    c = TestClient(crear_app(carpeta_config=RAIZ / "config"))
    assert c.get("/api/salud").json()["simulador"] == "ejemplo"
    assert c.get("/api/escenarios/escenario_a/trace").status_code == 200
