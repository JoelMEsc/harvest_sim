"""Métricas, series y mapas por celda, para cualquier número de agentes.  [Dueño: Joel]

Todos los valores esperados están calculados a mano (en el docstring de cada prueba está el cálculo).
"""

import copy
import json

import pytest

from ayuda_datos import C, CONFIG, FIXTURE, H, MUNDO, AGENTES, construir_trace, enviado, entregado, bloqueo, \
    pose, registro, trace_a_mano
from harvest_sim.datos import (
    TraceBuilder,
    calcular_metricas,
    cargar_trace,
    linea_de_tiempo,
    mapa_por_celda,
    series_temporales,
)

ORDEN_METRICAS = [
    "agentes", "tiempo_completacion", "tick_fin_cosecha", "tiempo_ocioso_cosechadora", "porcentaje_ocioso",
    "tiempo_transfiriendo", "espera_promedio_por_ciclo", "num_ciclos", "distancia_cosechadora", "distancia_carro",
    "distancia_total", "distancia_cosechadora_carro_promedio", "distancia_cosechadora_carro_minima",
    "distancia_cosechadora_carro_maxima", "utilizacion_carro", "ticks_bloqueados", "colisiones",
    "mensajes_enviados", "grano_cosechado_total", "grano_total_entregado", "grano_esperado_total",
    "porcentaje_entregado", "por_agente",
]


def sin_detalle(m):
    return {k: v for k, v in m.items() if k != "por_agente"}


def test_metricas_del_fixture():
    """Fixture (1 cosechadora y 1 carro, 50 ticks): LLENA_ESPERANDO en 6-10, 19-26 y 32-41 (rachas 5, 8 y
    10 = 23 ticks, 46 %); TRANSFIRIENDO en 11-13, 27-29 y 42-43; última transferencia en el tick 44; la
    cosechadora recorre 14 celdas y el carro 18; el carro está en EN_BASE 10 de 50 ticks; 2 bloqueos."""
    trace = cargar_trace(FIXTURE)
    original = copy.deepcopy(trace)
    m = calcular_metricas(trace)
    assert list(m) == ORDEN_METRICAS
    assert sin_detalle(m) == {
        "agentes": {"cosechadoras": 1, "carros": 1},
        "tiempo_completacion": 49, "tick_fin_cosecha": 44,
        "tiempo_ocioso_cosechadora": 23, "porcentaje_ocioso": 46.0, "tiempo_transfiriendo": 8,
        "espera_promedio_por_ciclo": 7.6667, "num_ciclos": 3,
        "distancia_cosechadora": 14, "distancia_carro": 18, "distancia_total": 32,
        "distancia_cosechadora_carro_promedio": 1.9, "distancia_cosechadora_carro_minima": 1,
        "distancia_cosechadora_carro_maxima": 4,
        "utilizacion_carro": 0.8, "ticks_bloqueados": 2, "colisiones": 0,
        "mensajes_enviados": {"LLENA": 3, "TRANSFERENCIA_TERMINADA": 3},
        "grano_cosechado_total": 8, "grano_total_entregado": 8, "grano_esperado_total": 8,
        "porcentaje_entregado": 100.0,
    }
    assert m["por_agente"] == {
        H: {"tipo": "cosechadora", "tiempo_ocioso": 23, "porcentaje_ocioso": 46.0, "tiempo_transfiriendo": 8,
            "num_ciclos": 3, "espera_por_ciclo": [5, 8, 10], "distancia": 14, "distancia_al_carro_promedio": 1.9,
            "ticks_bloqueados": 2,
            "ticks_por_estado": {"EN_BASE": 1, "YENDO_A_CAMPO": 3, "COSECHANDO": 9, "LLENA_ESPERANDO": 23,
                                 "TRANSFIRIENDO": 8, "REGRESANDO_A_BASE": 4, "FIN": 2}},
        C: {"tipo": "carro", "distancia": 18, "utilizacion": 0.8, "ticks_bloqueados": 0,
            "ticks_por_estado": {"EN_BASE": 10, "YENDO_A_COSECHADORA": 7, "ESPERANDO_TRANSFERENCIA": 14,
                                 "YENDO_A_BODEGA": 8, "DESCARGANDO": 8, "REGRESANDO_A_BASE": 3}},
    }
    assert isinstance(m["tiempo_ocioso_cosechadora"], int)  # un promedio entero se queda entero
    assert trace == original  # no modifica el trace
    assert calcular_metricas(linea_de_tiempo(trace)) == m  # mismo resultado con trace o con línea de tiempo


def test_metricas_del_guion_de_20_ticks():
    """Guion de 20 ticks: LLENA_ESPERANDO 7-10, TRANSFIRIENDO 11-12, una sola carga, un bloqueo de la
    cosechadora, un depósito de 4; la cosechadora avanza 7 celdas y el carro 5; el carro sale de EN_BASE en
    el tick 8 (13 de 21 ticks). Distancias Manhattan por tick: 51 en 21 ticks (2.4286), mínima 1, máxima 5.
    Campo de 4 x 2 = 8; se cosecharon 5 y llegaron 4: 50 %."""
    trace, _ = construir_trace()
    m = calcular_metricas(trace)
    assert sin_detalle(m) == {
        "agentes": {"cosechadoras": 1, "carros": 1},
        "tiempo_completacion": 20, "tick_fin_cosecha": 13,
        "tiempo_ocioso_cosechadora": 4, "porcentaje_ocioso": 19.05, "tiempo_transfiriendo": 2,
        "espera_promedio_por_ciclo": 4, "num_ciclos": 1,
        "distancia_cosechadora": 7, "distancia_carro": 5, "distancia_total": 12,
        "distancia_cosechadora_carro_promedio": 2.4286, "distancia_cosechadora_carro_minima": 1,
        "distancia_cosechadora_carro_maxima": 5,
        "utilizacion_carro": 0.619, "ticks_bloqueados": 1, "colisiones": 0,
        "mensajes_enviados": {"LLENA": 1, "TRANSFERENCIA_TERMINADA": 1},
        "grano_cosechado_total": 5, "grano_total_entregado": 4, "grano_esperado_total": 8,
        "porcentaje_entregado": 50.0,
    }
    assert m["por_agente"][H]["ticks_por_estado"] == {
        "EN_BASE": 1, "YENDO_A_CAMPO": 3, "COSECHANDO": 11, "LLENA_ESPERANDO": 4, "TRANSFIRIENDO": 2}
    assert m["por_agente"][C]["ticks_por_estado"] == {
        "EN_BASE": 8, "YENDO_A_COSECHADORA": 2, "ESPERANDO_TRANSFERENCIA": 4, "YENDO_A_BODEGA": 3,
        "DESCARGANDO": 2, "REGRESANDO_A_BASE": 2}
    assert (m["por_agente"][H]["ticks_bloqueados"], m["por_agente"][C]["ticks_bloqueados"]) == (1, 0)


# --- Varios agentes ------------------------------------------------------------------------------
DOS_COSECHADORAS = [("h1", "cosechadora"), ("h2", "cosechadora"), ("c1", "carro")]
TICKS_2H = [
    {"h1": (1, 1, "COSECHANDO", 0), "h2": (4, 1, "COSECHANDO", 0), "c1": (0, 0, "EN_BASE", 0)},
    {"h1": (1, 1, "LLENA_ESPERANDO", 4), "h2": (4, 2, "COSECHANDO", 1), "c1": (1, 0, "YENDO_A_COSECHADORA", 0)},
    {"h1": (1, 1, "LLENA_ESPERANDO", 4), "h2": (4, 2, "LLENA_ESPERANDO", 2), "c1": (2, 0, "YENDO_A_COSECHADORA", 0)},
    {"h1": (1, 1, "TRANSFIRIENDO", 4), "h2": (4, 2, "LLENA_ESPERANDO", 2), "c1": (2, 0, "ESPERANDO_TRANSFERENCIA", 0)},
]
EVENTOS_2H = {
    1: [enviado(1, "LLENA", "h1", "c1", {"x": 1, "y": 1, "carga": 4}, 2)],
    2: [entregado(1, "c1"), bloqueo("h2"), enviado(2, "LLENA", "h2", "c1", {"x": 4, "y": 2, "carga": 2}, 3)],
    3: [entregado(2, "c1"), bloqueo("c1")],
}


def test_dos_cosechadoras_y_un_carro():
    """4 ticks (T = 4). h1: ocioso 2 (racha [2]), transfiere 1, no se mueve. h2: ocioso 2 (racha [2]), se
    mueve 1. c1: EN_BASE 1 tick (utilización 0.75), se mueve 2.
    Promedios: ocioso (2 + 2) / 2 = 2; % ocioso 4 / 8 = 50; transfiriendo (1 + 0) / 2 = 0.5; espera por
    ciclo (2 + 2) / 2 = 2; distancia cosechadora (0 + 1) / 2 = 0.5. Totales: distancia 3, 2 ciclos, 2 bloqueos.
    Distancia al carro más cercano: h1 [2, 1, 2, 2], h2 [5, 5, 4, 4]: 25 / 8 = 3.125, mínima 1, máxima 5."""
    m = calcular_metricas(trace_a_mano(DOS_COSECHADORAS, TICKS_2H, EVENTOS_2H))
    assert m["agentes"] == {"cosechadoras": 2, "carros": 1}
    assert (m["tiempo_ocioso_cosechadora"], m["porcentaje_ocioso"], m["tiempo_transfiriendo"]) == (2, 50.0, 0.5)
    assert (m["espera_promedio_por_ciclo"], m["num_ciclos"], m["ticks_bloqueados"]) == (2, 2, 2)
    assert (m["distancia_cosechadora"], m["distancia_carro"], m["distancia_total"]) == (0.5, 2, 3)
    assert (m["distancia_cosechadora_carro_promedio"], m["distancia_cosechadora_carro_minima"],
            m["distancia_cosechadora_carro_maxima"]) == (3.125, 1, 5)
    assert m["utilizacion_carro"] == 0.75 and m["colisiones"] == 0
    h1, h2, c1 = (m["por_agente"][a] for a in ("h1", "h2", "c1"))
    assert (h1["tiempo_ocioso"], h1["espera_por_ciclo"], h1["distancia"], h1["distancia_al_carro_promedio"]) == (2, [2], 0, 1.75)
    assert (h2["tiempo_ocioso"], h2["espera_por_ciclo"], h2["distancia"], h2["distancia_al_carro_promedio"]) == (2, [2], 1, 4.5)
    assert (h1["num_ciclos"], h2["num_ciclos"]) == (1, 1)
    assert (h1["ticks_bloqueados"], h2["ticks_bloqueados"], c1["ticks_bloqueados"]) == (0, 1, 1)
    assert (c1["utilizacion"], c1["distancia"]) == (0.75, 2)


def test_series_con_dos_cosechadoras():
    """Ocio acumulado: h1 [0, 1, 2, 2] y h2 [0, 0, 1, 2], promedio [0, 0.5, 1.5, 2]. Distancia promedio al
    carro: [(2+5)/2, (1+5)/2, (2+4)/2, (2+4)/2] = [3.5, 3, 3, 3]. En tránsito (suma de cargas): [0, 5, 6, 6]."""
    s = series_temporales(trace_a_mano(DOS_COSECHADORAS, TICKS_2H, EVENTOS_2H))
    assert s["ocioso_acumulado"] == [0, 0.5, 1.5, 2]
    assert s["distancia_cosechadora_carro"] == [3.5, 3, 3, 3]
    assert s["en_transito"] == [0, 5, 6, 6]
    assert s["por_agente"]["h1"]["ocioso_acumulado"] == [0, 1, 2, 2]
    assert s["por_agente"]["h2"]["distancia_al_carro"] == [5, 5, 4, 4]
    assert s["por_agente"]["c1"] == {"carga": [0, 0, 0, 0]}  # los carros solo llevan su carga
    assert s["bloqueos_acumulados"] == [0, 0, 1, 2]


def test_la_distancia_usa_el_carro_mas_cercano():
    """1 cosechadora en (3, 2); c1 en (0, 0) a 5 celdas y c2 en (3, 1) a 1 celda: la distancia es 1, no 5
    (no se toma "el primer carro"). Utilización: c1 siempre en EN_BASE (0) y c2 nunca (1): promedio 0.5."""
    agentes = [("h1", "cosechadora"), ("c1", "carro"), ("c2", "carro")]
    ticks = [{"h1": (3, 2, "LLENA_ESPERANDO", 4), "c1": (0, 0, "EN_BASE", 0), "c2": (3, 1, "ESPERANDO_TRANSFERENCIA", 0)}] * 2
    m = calcular_metricas(trace_a_mano(agentes, ticks))
    assert m["agentes"] == {"cosechadoras": 1, "carros": 2}
    assert (m["distancia_cosechadora_carro_promedio"], m["distancia_cosechadora_carro_maxima"]) == (1, 1)
    assert m["utilizacion_carro"] == 0.5
    assert (m["por_agente"]["c1"]["utilizacion"], m["por_agente"]["c2"]["utilizacion"]) == (0.0, 1.0)


def test_las_metricas_no_dependen_de_los_nombres_de_los_agentes():
    """Renombrar los ids del fixture no cambia ninguna métrica del nivel superior (nada usa ids fijos)."""
    texto = FIXTURE.read_text(encoding="utf-8").replace('"cosechadora_1"', '"h_x"').replace('"carro_1"', '"c_y"')
    renombrado = json.loads(texto)
    original = calcular_metricas(cargar_trace(FIXTURE))
    nuevo = calcular_metricas(renombrado)
    assert sin_detalle(nuevo) == sin_detalle(original)
    assert set(nuevo["por_agente"]) == {"h_x", "c_y"}


def test_sin_carros_ni_cosechadoras_no_falla():
    """Solo un carro: las métricas de cosechadora quedan en None (no aplica) y no hay división entre cero."""
    m = calcular_metricas(trace_a_mano([("c1", "carro")], [{"c1": (1, 0, "EN_BASE", 0)}]))
    assert m["tiempo_ocioso_cosechadora"] is None and m["porcentaje_ocioso"] is None
    assert m["distancia_cosechadora_carro_promedio"] is None and m["utilizacion_carro"] == 0


# --- Series del guion y del fixture --------------------------------------------------------------
def test_series_temporales_del_guion():
    """Series del guion de 20 ticks, calculadas a mano: el ocio acumulado sube 1 por tick entre los ticks 7
    y 10; la distancia es Manhattan; el grano entra a la bodega en el tick 19; en tránsito = suma de cargas."""
    trace, _ = construir_trace()
    s = series_temporales(trace)
    assert s["tick"] == list(range(21))
    assert s["ocioso_acumulado"] == [0] * 7 + [1, 2, 3, 4] + [4] * 10
    assert s["distancia_cosechadora_carro"] == [1, 1, 2, 1, 2, 1, 2, 3, 3, 2, 1, 1, 1, 1, 2, 3, 4, 5, 5, 5, 5]
    assert s["por_agente"][H]["carga"] == [0] * 4 + [1, 2, 3] + [4] * 6 + [0] + [1] * 7
    assert s["por_agente"][C]["carga"] == [0] * 13 + [4] * 6 + [0] * 2
    assert s["cosechado_acumulado"] == [0] * 4 + [1, 2, 3, 4] + [4] * 6 + [5] * 7
    assert s["entregado_en_bodega"] == [0] * 19 + [4, 4]
    assert s["en_transito"] == [a + b for a, b in zip(s["por_agente"][H]["carga"], s["por_agente"][C]["carga"])]
    assert s["bloqueos_acumulados"] == [0] * 17 + [1] * 4
    m = calcular_metricas(trace)
    assert s["ocioso_acumulado"][-1] == m["tiempo_ocioso_cosechadora"]
    assert s["entregado_en_bodega"][-1] == m["grano_total_entregado"]


def test_series_del_fixture_son_coherentes_con_las_metricas():
    trace = cargar_trace(FIXTURE)
    s, m = series_temporales(trace), calcular_metricas(trace)
    assert all(len(v) == 50 for k, v in s.items() if k != "por_agente")
    assert s["ocioso_acumulado"][-1] == 23 == m["tiempo_ocioso_cosechadora"]
    assert s["entregado_en_bodega"][-1] == s["cosechado_acumulado"][-1] == 8
    assert s["bloqueos_acumulados"][-1] == 2
    assert all(b >= a for a, b in zip(s["ocioso_acumulado"], s["ocioso_acumulado"][1:]))  # nunca baja
    # conservación: cosechado = en tránsito + en la bodega, en cada tick
    assert all(c == t + b for c, t, b in zip(s["cosechado_acumulado"], s["en_transito"], s["entregado_en_bodega"]))
    distancias = s["distancia_cosechadora_carro"]
    assert m["distancia_cosechadora_carro_minima"] == min(distancias) == 1
    assert m["distancia_cosechadora_carro_promedio"] == round(sum(distancias) / 50, 4)


# --- Casos especiales ----------------------------------------------------------------------------
def test_metricas_distancia_ignora_cambios_de_orientacion():
    """Girar sin cambiar de celda no es distancia: (1,0) E -> (1,0) S -> (2,0) S son 1 movimiento."""
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    for t, (x, y, o) in enumerate([(1, 0, "E"), (1, 0, "S"), (2, 0, "S")]):
        regs = [registro(t, H, {"pose": pose(x, y, o), "estado": "EN_BASE", "carga": 0}),
                registro(t, C, {"pose": pose(0, 0, "N"), "estado": "EN_BASE", "carga": 0})]
        b.agregar_tick(t, regs, [])
    m = calcular_metricas(b.construir())
    assert m["distancia_cosechadora"] == 1 and m["distancia_carro"] == 0


def test_metricas_detectan_colisiones_y_cuentan_ticks():
    """Misma celda en el tick 1 e intercambio de posiciones en el tick 3: son 2 ticks de colisión.
    Sin mensajes, tick_fin_cosecha es None y no hay ciclos."""
    posiciones = [((1, 0), (3, 0)), ((2, 0), (2, 0)), ((2, 0), (3, 0)), ((3, 0), (2, 0))]
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    for t, (ph, pc) in enumerate(posiciones):
        regs = [registro(t, H, {"pose": pose(*ph, "E"), "estado": "EN_BASE", "carga": 0}),
                registro(t, C, {"pose": pose(*pc, "E"), "estado": "EN_BASE", "carga": 0})]
        b.agregar_tick(t, regs, [])
    m = calcular_metricas(b.construir())
    assert m["colisiones"] == 2
    assert m["tick_fin_cosecha"] is None and m["num_ciclos"] == 0
    assert m["espera_promedio_por_ciclo"] is None and m["grano_total_entregado"] == 0
    assert m["utilizacion_carro"] == 0  # el carro nunca sale de EN_BASE


def test_el_grano_esperado_descuenta_los_obstaculos():
    """Mundo de 4 x 3 con 2 obstáculos: 8 - 2 = 6 celdas de campo; con 5 entregados, 83.33 %."""
    trace, _ = construir_trace()
    trace["mundo"]["obstaculos"] = [[1, 2], [2, 2]]
    m = calcular_metricas(trace)
    assert (m["grano_esperado_total"], m["porcentaje_entregado"]) == (6, round(100 * 4 / 6, 2))


# --- Mapas por celda -----------------------------------------------------------------------------
def test_mapa_de_espera_del_fixture():
    """La cosechadora espera exactamente en las celdas desde donde avisó LLENA, tantos ticks como cada racha
    (5, 8 y 10, en el orden de los avisos)."""
    trace = cargar_trace(FIXTURE)
    avisos = [(e["payload"]["x"], e["payload"]["y"]) for t in trace["ticks"] for e in t["cambios"]
              if e["tipo"] == "MENSAJE_ENVIADO" and e["tipo_mensaje"] == "LLENA"]
    esperado = [[0] * 4 for _ in range(3)]
    for (x, y), racha in zip(avisos, [5, 8, 10]):
        esperado[y][x] += racha
    assert mapa_por_celda(trace, "espera") == esperado


def test_mapa_de_trafico_del_fixture():
    """Entradas a celdas = 2 posiciones iniciales + 32 movimientos (distancia total) = 34."""
    trace = cargar_trace(FIXTURE)
    mapa = mapa_por_celda(trace, "trafico")
    assert len(mapa) == 3 and all(len(f) == 4 for f in mapa)
    assert sum(map(sum, mapa)) == 34
    assert mapa[0][0] == 3  # el carro entra 3 veces a la bodega (una por descarga)
    with pytest.raises(ValueError):
        mapa_por_celda(trace, "otro")
