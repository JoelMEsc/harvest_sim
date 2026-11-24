"""Experimentos: barrido de parámetros, repeticiones y resumen estadístico.  [Dueño: Joel]

Se usa el generador de ejemplo como simulador (la simulación del equipo todavía no existe).
"""

import csv

import pytest

from ayuda_datos import RAIZ, cargar_script
from harvest_sim.datos.experimentos import combinaciones, correr_experimento, intervalo_95, resumen_por_grupo


@pytest.fixture(scope="module")
def gen():
    return cargar_script("tools/generar_trace_ejemplo.py")


def test_combinaciones():
    assert combinaciones(None) == [{}]
    assert combinaciones({"a": [1, 2], "b": [3]}) == [{"a": 1, "b": 3}, {"a": 2, "b": 3}]


def test_barrido_de_2_valores_en_2_escenarios_da_4_filas(gen):
    escenarios = {"a": dict(gen.CONFIG, nombre="a"), "b": dict(gen.CONFIG, nombre="b", ancho=5)}
    filas = correr_experimento(escenarios, {"tasa_transferencia": [1, 3]}, 1, gen.generar)
    assert [(f["escenario"], f["tasa_transferencia"]) for f in filas] == [("a", 1), ("a", 3), ("b", 1), ("b", 3)]
    assert all("tiempo_ocioso_cosechadora" in f and "por_agente" not in f for f in filas)
    # transferir más rápido acorta la corrida en el mismo escenario
    assert filas[1]["tiempo_completacion"] < filas[0]["tiempo_completacion"]


def test_repeticiones_cambian_la_seed_y_el_resumen_detecta_que_no_hay_variacion(gen):
    filas = correr_experimento({"a": gen.CONFIG}, None, 3, gen.generar)
    assert [f["seed"] for f in filas] == [0, 1, 2]
    resumen = resumen_por_grupo(filas)
    assert len(resumen) == 1 and resumen[0]["n"] == 3
    assert resumen[0]["variacion"] == "sin variación"  # el generador (y la simulación) son deterministas
    assert resumen[0]["tiempo_ocioso_cosechadora_ic95"] == 0


def test_intervalo_de_confianza_calculado_a_mano():
    """Valores 2, 4, 6: media 4, desviación muestral 2, t(0.975, 2 gl) = 4.303, IC = 4.303 * 2 / sqrt(3) = 4.9687."""
    media, desv, ic = intervalo_95([2, 4, 6])
    assert (media, desv, round(ic, 4)) == (4, 2, 4.9687)
    assert intervalo_95([5]) == (5, 0.0, 0.0)
    filas = [{"escenario": "a", "p": 1, "x": v} for v in (2, 4, 6)] + [{"escenario": "a", "p": 2, "x": 1}]
    resumen = resumen_por_grupo(filas, ["p"], ["x"])
    assert resumen[0] == {"escenario": "a", "p": 1, "n": 3, "x_media": 4, "x_desv": 2, "x_ic95": 4.9687,
                          "variacion": "con variación"}
    assert resumen[1]["n"] == 1 and resumen[1]["variacion"] == "sin variación"


def test_repeticiones_invalidas(gen):
    with pytest.raises(ValueError):
        correr_experimento({"a": gen.CONFIG}, None, 0, gen.generar)


def test_cli_con_el_experimento_de_ejemplo(tmp_path, capsys):
    """El experimento de config/experimentos corre con el simulador de ejemplo sobre los escenarios reales."""
    cli = cargar_script("tools/correr_experimento.py")
    ruta = RAIZ / "config" / "experimentos" / "tasa_transferencia.json"
    assert cli.main([str(ruta), "--simulador", "ejemplo", "--salida", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    assert "12 corridas" in salida and "generador de ejemplo" in salida
    carpeta = tmp_path / "tasa_transferencia"
    with open(carpeta / "resultados.csv", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 3 * 4
    with open(carpeta / "resumen.csv", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 3 * 4
    assert (carpeta / "sensibilidad_tasa_transferencia.png").read_bytes().startswith(b"\x89PNG")


def test_cli_con_un_experimento_invalido(tmp_path, capsys):
    cli = cargar_script("tools/correr_experimento.py")
    malo = tmp_path / "malo.json"
    malo.write_text('{"escenarios": []}', encoding="utf-8")
    assert cli.main([str(malo), "--simulador", "ejemplo"]) == 2
    assert "nombre" in capsys.readouterr().err


def test_estrategias_de_la_segunda_entrega():
    """Las 4 estrategias solo cambian la política; `base` es la línea base (directa, umbral 1)."""
    from harvest_sim.datos.experimentos import ESTRATEGIAS, aplicar_estrategia
    assert list(ESTRATEGIAS) == ["base", "subasta", "anticipada", "anticipada_plus"]
    assert ESTRATEGIAS["base"]["politica"]["asignacion"] == "directa"
    assert ESTRATEGIAS["anticipada"]["politica"]["umbral_aviso"] == 0.7
    config = {"nombre": "x", "politica": {"espera_propuestas": 4, "umbral_aviso": 1.0}}
    nueva = aplicar_estrategia(config, "anticipada_plus")
    assert nueva["politica"] == {"espera_propuestas": 4, "umbral_aviso": 0.7, "asignacion": "subasta",
                                 "atender_desde_bodega": True, "encadenar_servicios": True}
    assert config["politica"]["umbral_aviso"] == 1.0          # no modifica la original
    assert aplicar_estrategia({"nombre": "y"}, "base")["politica"]["asignacion"] == "directa"
    with pytest.raises(ValueError, match="no es una de"):
        aplicar_estrategia(config, "otra")


# --- Segunda entrega: estrategias, seeds, comparación pareada y ablación ------------------------
# Simulador falso: la cosechadora espera k ticks y termina (ocio = completación = k). k depende de la seed y
# de la estrategia, así los resultados se calculan a mano.
K_BASE = {0: 10, 1: 12, 2: 14}
DESVIO_PLUS = {0: -1, 1: 1, 2: 0}


def simulador_falso(config):
    from ayuda_datos import trace_a_mano
    politica = config.get("politica") or {}
    k = K_BASE[config["seed"]]
    if politica.get("umbral_aviso", 1.0) < 1.0:
        k -= 3
    if politica.get("encadenar_servicios"):
        k = K_BASE[config["seed"]] + DESVIO_PLUS[config["seed"]]
    estados = [{"h1": (1, 1, "LLENA_ESPERANDO", 0), "c1": (1, 0, "EN_BASE", 0)}] * k
    return trace_a_mano([("h1", "cosechadora"), ("c1", "carro")],
                        estados + [{"h1": (1, 1, "FIN", 0), "c1": (1, 0, "EN_BASE", 0)}],
                        nombre=config["nombre"])


@pytest.fixture(scope="module")
def filas_estrategias():
    from harvest_sim.datos.experimentos import ESTRATEGIAS
    return correr_experimento({"d": {"nombre": "d", "seed": 0}}, None, simulador=simulador_falso,
                              estrategias=list(ESTRATEGIAS), seeds=[0, 1, 2])


def test_filas_por_estrategia_y_seed(filas_estrategias):
    assert len(filas_estrategias) == 4 * 3
    assert [(f["estrategia"], f["seed"]) for f in filas_estrategias[:4]] == [("base", 0), ("base", 1), ("base", 2),
                                                                             ("subasta", 0)]
    anticipada = [f["tiempo_ocioso_total"] for f in filas_estrategias if f["estrategia"] == "anticipada"]
    assert anticipada == [7, 9, 11]
    # J = k (tiempo) + 5 k (ocio): 6 × 10 en la seed 0 de la base, con sus términos como columnas
    base0 = filas_estrategias[0]
    assert (base0["costo_total"], base0["costo_tiempo"], base0["costo_ocio"]) == (60, 10, 50)
    resumen = resumen_por_grupo(filas_estrategias)
    assert [r["estrategia"] for r in resumen] == ["base", "subasta", "anticipada", "anticipada_plus"]
    assert resumen[0]["tiempo_ocioso_total_media"] == 12


def test_comparacion_pareada_contra_la_base(filas_estrategias):
    """anticipada: −3 en cada seed → mejora con IC 0; subasta: igual; anticipada_plus: diferencias −1, +1, 0
    → media 0, IC 4.303 · 1 / √3 = 2.4843 → no concluyente."""
    from harvest_sim.datos.experimentos import comparar_contra_base
    comp = {(c["estrategia"], c["metrica"]): c
            for c in comparar_contra_base(filas_estrategias, ["tiempo_ocioso_total", "num_ciclos"])}
    a = comp[("anticipada", "tiempo_ocioso_total")]
    assert (a["media_base"], a["media_estrategia"], a["diferencia"], a["ic95"], a["cambio_pct"], a["veredicto"]) == \
        (12, 9, -3, 0, -25.0, "mejora")
    assert comp[("subasta", "tiempo_ocioso_total")]["veredicto"] == "igual"
    plus = comp[("anticipada_plus", "tiempo_ocioso_total")]
    assert (plus["diferencia"], plus["ic95"], plus["veredicto"]) == (0, 2.4843, "no concluyente")
    assert comp[("anticipada", "num_ciclos")]["veredicto"] == "informativa"
    assert ("base", "tiempo_ocioso_total") not in comp


def test_ablacion_del_costo(filas_estrategias):
    from harvest_sim.datos.experimentos import ablacion_costo
    filas = ablacion_costo(filas_estrategias)
    completo = filas[0]
    assert completo["sin_termino"] == "ninguno"
    # anticipada_plus: k = 9, 13, 14 (media 12) → J 72, empata con base y subasta (desempate por nombre)
    assert completo["orden"] == "anticipada < anticipada_plus < base < subasta"
    assert (completo["J_anticipada"], completo["J_base"], completo["J_anticipada_plus"]) == (54, 72, 72)
    sin_ocio = next(f for f in filas if f["sin_termino"] == "ocio")
    assert (sin_ocio["J_anticipada"], sin_ocio["cambia_orden"]) == (9, False)
    # con filas hechas a mano: quitar la distancia invierte el orden
    # (con todo: b 10 < a 12; sin la distancia: a 4 < b 9)
    hechas = [{"escenario": "x", "estrategia": "a", "seed": 0, "costo_total": 12, "costo_distancia": 8},
              {"escenario": "x", "estrategia": "b", "seed": 0, "costo_total": 10, "costo_distancia": 1}]
    sin_distancia = next(f for f in ablacion_costo(hechas) if f["sin_termino"] == "distancia")
    assert (sin_distancia["orden"], sin_distancia["cambia_orden"]) == ("a < b", True)


def test_barrido_con_clave_de_seccion_y_procesos():
    """`politica.umbral_aviso` entra a la sección; con 2 procesos las filas salen iguales y en el mismo orden."""
    from harvest_sim.datos.experimentos import aplicar_cambios
    assert aplicar_cambios({"politica": {"a": 1}}, {"politica.umbral_aviso": 0.6, "seed": 3}) == \
        {"politica": {"a": 1, "umbral_aviso": 0.6}, "seed": 3}
    args = ({"d": {"nombre": "d", "seed": 0}}, {"politica.umbral_aviso": [0.6, 1.0]})
    uno = correr_experimento(*args, simulador=simulador_falso, seeds=[0, 1])
    dos = correr_experimento(*args, simulador=simulador_falso, seeds=[0, 1], procesos=2)
    assert uno == dos
    assert [(f["politica.umbral_aviso"], f["tiempo_ocioso_total"]) for f in uno] == [(0.6, 7), (0.6, 9), (1.0, 10),
                                                                                    (1.0, 12)]


def test_cli_con_estrategias_y_seeds(tmp_path, capsys, monkeypatch):
    """El JSON con estrategias y seeds escribe resultados, resumen, comparación y ablación."""
    import json
    cli = cargar_script("tools/correr_experimento.py")
    monkeypatch.setattr(cli, "simulador_ejemplo", simulador_falso)
    escenario = tmp_path / "escenario_x.json"
    escenario.write_text(json.dumps({"nombre": "x", "seed": 0}), encoding="utf-8")
    experimento = tmp_path / "exp.json"
    experimento.write_text(json.dumps({"nombre": "exp", "escenarios": [str(escenario)],
                                       "estrategias": ["base", "anticipada"], "seeds": {"desde": 0, "cantidad": 3}}),
                           encoding="utf-8")
    assert cli.main([str(experimento), "--simulador", "ejemplo", "--salida", str(tmp_path / "salida")]) == 0
    carpeta = tmp_path / "salida" / "exp"
    for nombre in ("resultados.csv", "resumen.csv", "comparacion.csv", "ablacion.csv"):
        assert (carpeta / nombre).exists(), nombre
    with open(carpeta / "comparacion.csv", encoding="utf-8") as f:
        filas = {r["metrica"]: r for r in csv.DictReader(f)}
    assert filas["tiempo_ocioso_total"]["veredicto"] == "mejora"
    experimento.write_text(json.dumps({"nombre": "exp", "escenarios": [str(escenario)], "estrategias": ["otra"]}),
                           encoding="utf-8")
    assert cli.main([str(experimento), "--simulador", "ejemplo"]) == 2
    assert "estrategias desconocidas" in capsys.readouterr().err
