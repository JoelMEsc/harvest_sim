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
