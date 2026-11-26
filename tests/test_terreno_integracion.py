"""Integración en el campo real (escenario G): R12, R13, colisiones y trace 2.3.  [Dueños: Ilan y Joel]

Especificación: docs/especificacion_terreno.md §7. Las 4 estrategias × 20 seeds se corren con
`tools/verificar_terreno.py` (tarda ~3 min); aquí va una corrida completa y los casos construidos.
"""

import json
import logging
from pathlib import Path

import pytest

from ayuda_datos import cargar_script
from harvest_sim.carro import Carro
from harvest_sim.config import cargar_config
from harvest_sim.datos import validar_trace
from harvest_sim.datos.experimentos import aplicar_estrategia, simulador_real
from harvest_sim.mundo import Mundo

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corrida_g():
    logging.disable(logging.WARNING)
    base = json.loads((RAIZ / "config" / "escenario_g.json").read_text(encoding="utf-8"))
    trace = simulador_real(aplicar_estrategia(base, "anticipada_plus"))
    logging.disable(logging.NOTSET)
    return trace


def test_g_termina_y_valida(corrida_g):
    assert corrida_g["schema_version"] == "2.3"
    assert validar_trace(corrida_g) == []
    assert corrida_g["metricas"]["porcentaje_entregado"] == 100.0
    assert "altura_m" in corrida_g["mundo"] and "geo" in corrida_g["mundo"]


def test_g_respeta_r10_r12_y_r13(corrida_g):
    """Nadie en obstáculo ni fuera del predio; ningún carro sobre cultivo en pie; sin colisiones ni bloqueos."""
    r = cargar_script("tools/verificar_terreno.py").revisar_trace(corrida_g)
    assert (r["r12"], r["r13_carros"], r["colisiones"], r["bloqueos"]) == (0, 0, 0, 0)
    assert r["cosechadora_pisa"] <= 0.02 * r["ticks"]  # traslados en bordes irregulares sin ruta por rastrojo


def test_r13_se_registra_cuando_el_carro_rodea_el_cultivo():
    """Un carro que va desde su base al camino al que más le cuesta llegar sin pisar el maíz tiene que
    rodear el cultivo: se registra una RESTRICCION R13_cultivo_en_pie (una vez por tramo).

    En la cuadrícula, rodear por un camino en escalera mide lo mismo que cruzar (pasos de vecindad 4), así
    que R13 solo alarga las rutas que tienen que retroceder; el destino se elige entre esas."""
    from harvest_sim import rutas
    mundo = Mundo(cargar_config(RAIZ / "config" / "escenario_g.json"))
    carro = Carro("carro_1", 360)
    mundo.registrar(carro)
    origen = mundo.base_de("carro_1")
    d_fijas = rutas.distancias(origen, mundo.ancho, mundo.alto, mundo.bloqueadas_fijas("carro_1"))
    d_r13 = rutas.distancias(origen, mundo.ancho, mundo.alto, mundo.bloqueadas_para("carro_1"))
    lejos = max((c for c in mundo.celdas_camino if c in d_r13), key=lambda c: (d_r13[c] - d_fijas[c], c))
    assert d_r13[lejos] > d_fijas[lejos]
    carro._destino = lejos
    bloqueadas = carro._bloqueadas(mundo) | carro._obstaculos(mundo)
    carro._registrar_desvio(1, mundo, bloqueadas, {})
    carro._registrar_desvio(2, mundo, bloqueadas, {})
    reglas = [e["regla"] for e in mundo.drenar_eventos() if e["tipo"] == "RESTRICCION"]
    assert reglas.count("R13_cultivo_en_pie") == 1


def test_carro_no_planea_por_el_cultivo_en_pie():
    mundo = Mundo(cargar_config(RAIZ / "config" / "escenario_g.json"))
    carro = Carro("carro_1", 360)
    mundo.registrar(carro)
    assert mundo.cultivo_en_pie() <= carro._bloqueadas(mundo)
