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
