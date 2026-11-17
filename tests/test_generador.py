"""Generador de datos de ejemplo: escenarios A, B y C (tarea 7 de Datos).  [Dueño: Joel]"""

import itertools

import pytest

from ayuda_datos import cargar_script
from harvest_sim.datos import calcular_metricas, cargar_trace, validar_trace


@pytest.fixture(scope="module")
def gen():
    return cargar_script("tools/generar_trace_ejemplo.py")


def test_los_tres_escenarios_son_validos_y_distintos(gen, tmp_path):
    rutas = gen.generar_escenarios(tmp_path)
    assert [r.parent.name for r in rutas] == ["ejemplo_a", "ejemplo_b", "ejemplo_c"]
    resumen = {}
    for ruta in rutas:
        trace = cargar_trace(ruta)
        assert validar_trace(trace) == [], ruta
        assert trace["meta"]["escenario"] == ruta.parent.name
        m = calcular_metricas(trace)
        resumen[ruta.parent.name] = (m["tiempo_ocioso_cosechadora"], m["tiempo_completacion"])
    # cada escenario da resultados distintos (si no, la comparación no mostraría nada)
    assert len(set(resumen.values())) == 3, resumen


def test_generar_escenarios_es_determinista(gen, tmp_path):
    primera = gen.generar_escenarios(tmp_path / "1")
    segunda = gen.generar_escenarios(tmp_path / "2")
    for a, b in zip(primera, segunda):
        assert a.read_bytes() == b.read_bytes()


def test_cli_escenarios(gen, tmp_path, capsys):
    assert gen.main(["--escenarios", "--salida", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    for nombre in ("ejemplo_a", "ejemplo_b", "ejemplo_c"):
        assert (tmp_path / nombre / "trace.json").exists()
        assert nombre in salida
    assert "ocioso" in salida and "completación" in salida


def test_el_generador_es_robusto_con_otras_configuraciones(gen):
    """Una muestra de configuraciones (tamaño, capacidades y tasas) genera traces válidos.
    Protege contra la fragilidad que apareció cuando el destino estaba ocupado al planear la ruta."""
    for ancho, alto, cap, mult, tasa in itertools.product((3, 5, 8), (2, 3, 5), (1, 3, 6), (1, 2), (1, 3)):
        cfg = dict(gen.CONFIG, ancho=ancho, alto=alto, capacidad_cosechadora=cap, capacidad_carro=cap * mult,
                   tasa_transferencia=tasa, tasa_descarga=tasa)
        assert validar_trace(gen.generar(cfg)) == [], cfg


def test_el_generador_rechaza_obstaculos(gen):
    """El generador de ejemplo no recorre obstáculos: si la configuración trae alguno, falla con claridad."""
    assert validar_trace(gen.generar(dict(gen.CONFIG, obstaculos={"celdas": [], "regiones": []}))) == []
    with pytest.raises(ValueError, match="no soporta obstáculos"):
        gen.generar(dict(gen.CONFIG, obstaculos={"celdas": [[1, 1]], "regiones": []}))
