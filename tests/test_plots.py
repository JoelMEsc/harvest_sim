"""Gráficas y tabla comparativa (viz/plots.py).  [Dueño: Joel]

Las imágenes se generan sin ventana (backend Agg). Aquí se comprueba que existen, que son PNG válidos y
que la tabla trae los valores correctos; cómo se ven se revisa a ojo.
"""

import copy
import csv
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from ayuda_datos import FIXTURE, cargar_script, trace_a_mano  # noqa: E402
from harvest_sim.datos import TraceBuilder, cargar_trace, escribir_trace  # noqa: E402
from harvest_sim.datos.experimentos import resumen_por_grupo  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(scope="module")
def plots():
    return cargar_script("viz/plots.py")


def es_png(ruta):
    datos = Path(ruta).read_bytes()
    return datos.startswith(PNG) and len(datos) > 5000


def con_nombre(trace, nombre):
    otro = copy.deepcopy(trace)
    otro["meta"]["escenario"] = nombre
    return otro


def test_las_seis_graficas_de_un_trace_se_generan(plots, tmp_path):
    rutas = plots.graficas_de_un_trace(FIXTURE, tmp_path)
    assert [r.name for r in rutas] == [
        "1_linea_de_tiempo_estados.png", "2_ocioso_acumulado.png", "3_distancia_cosechadora_carro.png",
        "4_flujo_del_grano.png", "5_mapa_espera.png", "6_mapa_trafico.png",
    ]
    assert all(es_png(r) for r in rutas)


def test_graficas_con_varios_agentes_y_opcion_agente(plots, tmp_path):
    """Un trace con 2 cosechadoras y 1 carro genera las 6 gráficas (promedio) y las de una cosechadora."""
    agentes = [("h1", "cosechadora"), ("h2", "cosechadora"), ("c1", "carro")]
    ticks = [{"h1": (1, 1, "COSECHANDO", 0), "h2": (4, 1, "COSECHANDO", 0), "c1": (0, 0, "EN_BASE", 0)},
             {"h1": (1, 1, "LLENA_ESPERANDO", 4), "h2": (4, 2, "COSECHANDO", 1), "c1": (1, 0, "YENDO_A_COSECHADORA", 0)},
             {"h1": (1, 1, "LLENA_ESPERANDO", 4), "h2": (4, 2, "LLENA_ESPERANDO", 2), "c1": (2, 0, "YENDO_A_COSECHADORA", 0)}]
    ruta = tmp_path / "varios" / "trace.json"
    escribir_trace(trace_a_mano(agentes, ticks, nombre="varios"), ruta)
    assert all(es_png(r) for r in plots.graficas_de_un_trace(ruta, tmp_path / "prom"))
    assert all(es_png(r) for r in plots.graficas_de_un_trace(ruta, tmp_path / "h2", agente="h2"))
    with pytest.raises(ValueError, match="no es una cosechadora"):
        plots.graficas_de_un_trace(ruta, tmp_path / "x", agente="c1")


def test_comparacion_y_tabla_resumen(plots, tmp_path):
    base = cargar_trace(FIXTURE)
    traces = {"escenario_a": con_nombre(base, "escenario_a"), "escenario_b": con_nombre(base, "escenario_b")}
    # en B el carro también se bloquea una vez (un tick que ya tiene cambios): el total de bloqueos pasa a 3
    traces["escenario_b"]["ticks"][10]["cambios"].append({"tipo": "BLOQUEO", "agente": "carro_1"})
    assert es_png(plots.grafica_comparacion(traces, tmp_path / "comparacion.png"))

    ruta_csv, ruta_md = plots.tabla_resumen(traces, tmp_path / "resumen.csv", tmp_path / "resumen.md")
    with open(ruta_csv, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    assert [f["escenario"] for f in filas] == ["escenario_a", "escenario_b"]
    # el CSV lleva TODAS las métricas, incluido el detalle por agente; valores calculados a mano
    a = filas[0]
    assert (a["agentes.cosechadoras"], a["agentes.carros"]) == ("1", "1")
    assert (a["tiempo_ocioso_cosechadora"], a["tick_fin_cosecha"], a["tiempo_completacion"]) == ("23", "44", "49")
    assert (a["distancia_total"], a["num_ciclos"], a["espera_promedio_por_ciclo"]) == ("32", "3", "7.6667")
    assert (a["utilizacion_carro"], a["grano_total_entregado"], a["colisiones"]) == ("0.8", "8", "0")
    assert (a["porcentaje_ocioso"], a["porcentaje_entregado"], a["grano_esperado_total"]) == ("46.0", "100.0", "8")
    assert a["por_agente.cosechadora_1.espera_por_ciclo"] == "5;8;10"
    assert (a["por_agente.cosechadora_1.ticks_por_estado.LLENA_ESPERANDO"],
            a["por_agente.carro_1.ticks_por_estado.EN_BASE"]) == ("23", "10")
    assert (a["mensajes_enviados.LLENA"], a["mensajes_enviados.TRANSFERENCIA_TERMINADA"]) == ("3", "3")
    assert (a["ticks_bloqueados"], filas[1]["ticks_bloqueados"]) == ("2", "3")
    assert filas[1]["por_agente.carro_1.ticks_bloqueados"] == "1"  # el bloqueo agregado a B

    lineas = Path(ruta_md).read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2 + 2  # encabezado, separador y una fila por escenario
    assert lineas[0].startswith("| Escenario | Agentes (cosechadoras + carros) | Tiempo de completación |")
    assert lineas[2] == "| escenario_a | 1 + 1 | 49 | 23 | 46 | 7.6667 | 32 | 1.9 | 0.8 | 2 | 0 | 3 | 100 |"
    assert " | 0.8 | 3 | 0 | 3 | 100 |" in lineas[3]  # B: 3 bloqueos en total


def test_todos_los_estados_tienen_categoria_y_color_validado(plots):
    estados = {a["estado"] for t in cargar_trace(FIXTURE)["ticks"] for e in t["cambios"]
               if e["tipo"] == "AGENTE" for a in [e["set"]] if "estado" in a}
    assert estados and estados <= set(plots.CATEGORIA_DE_ESTADO)
    colores = [c[2] for c in plots.CATEGORIAS]
    assert len(set(colores)) == len(colores)  # un color por categoría
    assert set(colores) <= set(plots.SERIES) | {plots.EJE}  # solo la paleta validada y el gris neutro


def test_un_estado_desconocido_se_dibuja_como_otros(plots, tmp_path):
    trace = copy.deepcopy(cargar_trace(FIXTURE))
    trace["ticks"][1]["cambios"][0]["set"]["estado"] = "ESTADO_NUEVO"
    assert es_png(plots.grafica_estados(trace, tmp_path / "estados.png"))


def test_la_comparacion_tiene_limite_de_escenarios(plots, tmp_path):
    base = cargar_trace(FIXTURE)
    demasiados = {f"e{i}": con_nombre(base, f"e{i}") for i in range(len(plots.SERIES) + 1)}
    with pytest.raises(ValueError):
        plots.grafica_comparacion(demasiados, tmp_path / "x.png")


def test_sin_esperas_las_graficas_no_fallan(plots, tmp_path):
    """Un trace en el que la cosechadora nunca espera (y sin tamaño de mapa) genera las gráficas sin fallar."""
    agentes = [{"id": "cosechadora_1", "tipo": "cosechadora", "capacidad": 3, "base": [2, 0]},
               {"id": "carro_1", "tipo": "carro", "capacidad": 6, "base": [1, 0]}]
    b = TraceBuilder({"nombre": "sin_esperas"}, {}, agentes)
    for t in range(3):
        regs = [{"tick": t, "agent_id": a["id"], "tipo": a["tipo"],
                 "pose": {"x": a["base"][0], "y": 0, "orientacion": "S"}, "estado": "EN_BASE",
                 "carga": {"actual": 0, "capacidad": a["capacidad"]}} for a in agentes]
        b.agregar_tick(t, regs, [])
    trace = b.construir()
    assert es_png(plots.grafica_ocioso_acumulado(trace, tmp_path / "ocioso.png"))
    assert es_png(plots.grafica_distancia(trace, tmp_path / "distancia.png"))
    assert es_png(plots.grafica_flujo_grano(trace, tmp_path / "grano.png"))


def test_grafica_de_sensibilidad(plots, tmp_path):
    filas = [{"escenario": e, "capacidad_carro": c, "tiempo_ocioso_cosechadora": v}
             for e, c, v in [("a", 10, 30), ("a", 20, 20), ("b", 10, 25), ("b", 20, 22), ("b", 20, 24)]]
    resumen = resumen_por_grupo(filas, ["capacidad_carro"], ["tiempo_ocioso_cosechadora"])
    assert es_png(plots.grafica_sensibilidad(resumen, "capacidad_carro", "tiempo_ocioso_cosechadora",
                                             tmp_path / "sens.png"))


def test_grafica_de_sensibilidad_con_varias_estrategias(plots, tmp_path):
    """Con dos estrategias en el barrido hay una línea por estrategia (antes se mezclaban en una sola)."""
    filas = [{"escenario": "d", "estrategia": e, "capacidad_carro": c, "tiempo_ocioso_total": v}
             for e, c, v in [("base", 8, 331), ("base", 16, 331), ("anticipada_plus", 8, 313),
                             ("anticipada_plus", 16, 199)]]
    resumen = resumen_por_grupo(filas, ["capacidad_carro"], ["tiempo_ocioso_total"])
    assert len({(f["estrategia"], f["capacidad_carro"]) for f in resumen}) == 4
    assert es_png(plots.grafica_sensibilidad(resumen, "capacidad_carro", "tiempo_ocioso_total", tmp_path / "s.png"))


def test_main_genera_graficas_comparacion_y_tabla(plots, tmp_path, capsys):
    base = cargar_trace(FIXTURE)
    rutas = []
    for nombre in ("escenario_a", "escenario_b"):
        ruta = tmp_path / "entrada" / nombre / "trace.json"
        escribir_trace(con_nombre(base, nombre), ruta)
        rutas.append(str(ruta))
    assert plots.main(rutas + ["--salida", str(tmp_path / "salida")]) == 0
    salida = tmp_path / "salida"
    for nombre in ("escenario_a", "escenario_b"):
        assert es_png(salida / nombre / "1_linea_de_tiempo_estados.png")
        assert es_png(salida / nombre / "5_mapa_espera.png")
    assert es_png(salida / "comparacion" / "comparacion_escenarios.png")
    assert (salida / "comparacion" / "resumen.csv").exists() and (salida / "comparacion" / "resumen.md").exists()
    assert str(salida / "comparacion" / "resumen.md") in capsys.readouterr().out
    # --agente con un id que no es cosechadora: error claro y código 2
    assert plots.main(rutas[:1] + ["--salida", str(tmp_path / "otra"), "--agente", "carro_1"]) == 2
    assert "no es una cosechadora" in capsys.readouterr().err


def test_grafica_de_combustible_con_el_trace_2_2(plots, tmp_path):
    """El trace de ejemplo 2.2 trae combustible: sale la gráfica 7; el fixture 2.1 no la genera."""
    ejemplo = FIXTURE.parent / "trace_ejemplo_22.json"
    rutas = plots.graficas_de_un_trace(ejemplo, tmp_path / "con")
    assert rutas[-1].name == "7_combustible.png" and all(es_png(r) for r in rutas)
    assert len(plots.graficas_de_un_trace(FIXTURE, tmp_path / "sin")) == 6
    with pytest.raises(ValueError, match="no trae combustible"):
        plots.grafica_combustible(cargar_trace(FIXTURE), tmp_path / "x.png")


def test_graficas_de_estrategias(plots, tmp_path):
    from harvest_sim.datos.experimentos import ablacion_costo, comparar_contra_base, resumen_por_grupo  # noqa: F401
    filas = [{"escenario": esc, "estrategia": e, "seed": s, "tiempo_ocioso_total": base - d + s,
              "tiempo_completacion": 100 + s, "costo_total": 6 * (base - d + s), "costo_ocio": 5 * (base - d + s),
              "costo_tiempo": base - d + s}
             for esc, base in (("escenario_d", 30), ("escenario_e", 40))
             for e, d in (("base", 0), ("subasta", 2), ("anticipada", 8)) for s in (0, 1, 2)]
    resumen = resumen_por_grupo(filas)
    assert es_png(plots.grafica_estrategias(resumen, tmp_path / "estrategias.png"))
    assert es_png(plots.grafica_costo_j(filas, tmp_path / "costo.png"))
    assert es_png(plots.grafica_diferencias(comparar_contra_base(filas), tmp_path / "dif.png"))


def test_main_sin_comparacion_solo_graficas_del_trace(plots, tmp_path):
    """G (campo real) se grafica solo, sin tocar la comparación de A–F (scripts/correr_todos.sh)."""
    ruta = tmp_path / "entrada" / "escenario_g" / "trace.json"
    escribir_trace(cargar_trace(Path(__file__).parent / "fixtures" / "trace_ejemplo_23.json"), ruta)
    assert plots.main([str(ruta), "--salida", str(tmp_path / "salida"), "--sin-comparacion"]) == 0
    assert any((tmp_path / "salida").rglob("6_mapa_trafico.png"))
    assert not (tmp_path / "salida" / "comparacion").exists()
