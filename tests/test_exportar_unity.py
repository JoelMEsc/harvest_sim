"""Exportar traces validados al proyecto de Unity (tools/exportar_traces_unity.py).  [Dueño: Joel]"""

import pytest

from ayuda_datos import RAIZ, cargar_script
from harvest_sim.datos import cargar_trace, validar_trace

EXPORTAR = cargar_script("tools/exportar_traces_unity.py")
GENERADOR = cargar_script("tools/generar_trace_ejemplo.py")


def simulador(config):
    return GENERADOR.generar({k: config[k] for k in GENERADOR.CONFIG if k in config})


def test_exporta_escenarios_por_estrategia_y_seed(tmp_path):
    rutas = EXPORTAR.exportar(tmp_path, ["escenario_a", "escenario_c"], ["base", "anticipada"], seed=4,
                              simulador=simulador)
    assert [r.name for r in rutas] == ["escenario_a__base__seed4.json", "escenario_a__anticipada__seed4.json",
                                       "escenario_c__base__seed4.json", "escenario_c__anticipada__seed4.json"]
    assert all(validar_trace(cargar_trace(r)) == [] for r in rutas)


def test_no_exporta_un_trace_invalido_ni_un_escenario_inexistente(tmp_path):
    def roto(config):
        trace = simulador(config)
        trace["schema_version"] = "0.1"
        return trace
    with pytest.raises(ValueError, match="no es válido"):
        EXPORTAR.exportar(tmp_path, ["escenario_a"], simulador=roto)
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="inexistentes"):
        EXPORTAR.exportar(tmp_path, ["escenario_z"], simulador=simulador)


def test_cli_con_ejemplos(tmp_path, capsys):
    assert EXPORTAR.main([str(tmp_path), "--ejemplo"]) == 0
    assert (tmp_path / "ejemplo_22.json").read_bytes() == (RAIZ / "tests/fixtures/trace_ejemplo_22.json").read_bytes()
    assert len(list((tmp_path / "ejemplos_1x1").glob("*/trace.json"))) == 3
    assert "ejemplo_22.json" in capsys.readouterr().out


def test_exporta_estrategias_aprendidas_con_sus_decisiones(tmp_path):
    """M1 en Unity: qlearning y sarsa se exportan con la simulación real (D tiene tabla) y traen DECISION_DESPACHO."""
    import logging
    logging.disable(logging.WARNING)
    rutas = EXPORTAR.exportar(tmp_path, ["escenario_d"], ["sarsa"], seed=0)
    logging.disable(logging.NOTSET)
    assert [r.name for r in rutas] == ["escenario_d__sarsa__seed0.json"]
    trace = cargar_trace(rutas[0])
    assert validar_trace(trace) == []
    assert any(e["tipo"] == "DECISION_DESPACHO" for t in trace["ticks"] for e in t["cambios"])
    assert EXPORTAR.main([str(tmp_path), "--escenarios", "escenario_d", "--estrategias", "qlearning", "--seed", "0"]) == 0
