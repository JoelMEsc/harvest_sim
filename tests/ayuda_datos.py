"""Ayudas compartidas por las pruebas de Datos (no es un archivo de pruebas).  [Dueño: Joel]

- `construir_trace()`: un guion de 20 ticks (mapa de 4x3, una cosechadora y un carro) cuyos valores
  esperados están calculados a mano en las pruebas, no salen del código que se prueba.
- `trace_a_mano(...)`: arma un trace chico con cualquier número de agentes a partir de sus posiciones y
  estados por tick (para las pruebas con varios agentes).
- `cargar_script(ruta)`: carga un script de tools/ o viz/ como módulo.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

from harvest_sim.datos import TraceBuilder

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE = RAIZ / "tests" / "fixtures" / "trace_ejemplo.json"

H, C = "cosechadora_1", "carro_1"
CAPACIDAD = {H: 4, C: 8}
TIPO = {H: "cosechadora", C: "carro"}
CONFIG = {"nombre": "ejemplo_mini", "seed": 0, "ancho": 4, "alto": 3, "capacidad_cosechadora": 4}
MUNDO = {"ancho": 4, "alto": 3, "bodega": [0, 0], "bases": {C: [1, 0], H: [2, 0]}, "grano_por_celda": 1,
         "obstaculos": []}
AGENTES = [
    {"id": H, "tipo": "cosechadora", "capacidad": 4, "base": [2, 0]},
    {"id": C, "tipo": "carro", "capacidad": 8, "base": [1, 0]},
]
TOTAL = 20


def cargar_script(ruta: str | Path):
    """Carga un script (por ejemplo tools/generar_trace_ejemplo.py) como módulo."""
    ruta = RAIZ / ruta
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def pose(x, y, o):
    return {"x": x, "y": y, "orientacion": o}


def cel(celda, agente=H):
    return {"tipo": "CELDA_COSECHADA", "celda": celda, "agente": agente}


def enviado(i, tipo_mensaje, de, a, payload, entrega_en, performativa=None):
    performativa = performativa or {"LLENA": "request", "TRANSFERENCIA_TERMINADA": "inform"}.get(tipo_mensaje, "inform")
    return {"tipo": "MENSAJE_ENVIADO", "id": i, "tipo_mensaje": tipo_mensaje, "performativa": performativa,
            "de": de, "a": a, "payload": payload, "entrega_en": entrega_en}


def entregado(i, a):
    return {"tipo": "MENSAJE_ENTREGADO", "id": i, "a": a}


def deposito(agente, cantidad, total):
    return {"tipo": "DEPOSITO", "agente": agente, "cantidad": cantidad, "entregado_total": total}


def bloqueo(agente):
    return {"tipo": "BLOQUEO", "agente": agente}


# Qué campos cambian en cada tick (los demás se mantienen). Los ticks 12, 18 y 20 no cambian nada.
GUION = {
    0: {H: dict(pose=pose(2, 0, "S"), estado="EN_BASE", carga=0),
        C: dict(pose=pose(1, 0, "N"), estado="EN_BASE", carga=0)},
    1: {H: dict(estado="YENDO_A_CAMPO")},
    2: {H: dict(pose=pose(2, 1, "S"))},
    3: {H: dict(pose=pose(1, 1, "O"))},
    4: {H: dict(pose=pose(0, 1, "O"), estado="COSECHANDO", carga=1)},
    5: {H: dict(pose=pose(1, 1, "E"), carga=2)},
    6: {H: dict(pose=pose(2, 1, "E"), carga=3)},
    7: {H: dict(pose=pose(3, 1, "E"), carga=4, estado="LLENA_ESPERANDO")},
    8: {C: dict(estado="YENDO_A_COSECHADORA")},
    9: {C: dict(pose=pose(2, 0, "E"))},
    10: {C: dict(pose=pose(3, 0, "E"), estado="ESPERANDO_TRANSFERENCIA")},
    11: {H: dict(estado="TRANSFIRIENDO")},
    13: {H: dict(carga=0, estado="COSECHANDO"), C: dict(carga=4)},
    14: {H: dict(pose=pose(3, 2, "S"), carga=1), C: dict(estado="YENDO_A_BODEGA")},
    15: {C: dict(pose=pose(2, 0, "O"))},
    16: {C: dict(pose=pose(1, 0, "O"))},
    17: {C: dict(pose=pose(0, 0, "O"), estado="DESCARGANDO")},
    19: {C: dict(carga=0, estado="REGRESANDO_A_BASE")},
}
EVENTOS = {
    4: [cel([0, 1])],
    5: [cel([1, 1])],
    6: [cel([2, 1])],
    7: [cel([3, 1]), enviado(1, "LLENA", H, C, {"x": 3, "y": 1, "carga": 4}, 8)],
    8: [entregado(1, C)],
    13: [enviado(2, "TRANSFERENCIA_TERMINADA", H, C, {"cantidad": 4}, 14)],
    14: [entregado(2, C), cel([3, 2])],
    17: [bloqueo(H)],
    19: [deposito(C, 4, 4)],
}


def registro(tick, agente, e, tipo=None, capacidad=None):
    return {
        "tick": tick, "agent_id": agente, "tipo": tipo or TIPO[agente],
        "pose": copy.deepcopy(e["pose"]), "estado": e["estado"],
        "carga": {"actual": e["carga"], "capacidad": capacidad or CAPACIDAD[agente]},
    }


def densos():
    """(tick, registros completos, eventos) para los ticks 0..TOTAL, con el estado arrastrado."""
    estado = {H: {}, C: {}}
    salida = []
    for t in range(TOTAL + 1):
        for agente, campos in GUION.get(t, {}).items():
            estado[agente].update(copy.deepcopy(campos))
        salida.append((t, [registro(t, a, estado[a]) for a in (H, C)], copy.deepcopy(EVENTOS.get(t, []))))
    return salida


def construir_trace():
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    entradas = densos()
    for t, regs, evs in entradas:
        b.agregar_tick(t, regs, evs)
    return b.construir(), entradas


def por_tick(trace):
    return {t["tick"]: t for t in trace["ticks"]}


def trace_a_mano(agentes, ticks, eventos=None, mundo=None, nombre="a_mano"):
    """Trace con cualquier número de agentes.

    `agentes`: [(id, tipo)]; `ticks`: lista (uno por tick) de {id: (x, y, estado, carga)}, con todos los
    agentes en cada tick; `eventos`: {tick: [eventos]}. Capacidad 10 para todos.
    """
    eventos = eventos or {}
    mundo = mundo or {"ancho": 6, "alto": 4, "bodega": [0, 0], "grano_por_celda": 1, "obstaculos": [],
                      "bases": {a: [i + 1, 0] for i, (a, _) in enumerate(agentes)}}
    catalogo = [{"id": a, "tipo": tipo, "capacidad": 10, "base": mundo["bases"][a]} for a, tipo in agentes]
    b = TraceBuilder({"nombre": nombre, "seed": 0}, mundo, catalogo)
    tipos = dict(agentes)
    for t, estados in enumerate(ticks):
        regs = [registro(t, a, {"pose": pose(x, y, "N"), "estado": est, "carga": carga}, tipos[a], 10)
                for a, (x, y, est, carga) in estados.items()]
        b.agregar_tick(t, regs, copy.deepcopy(eventos.get(t, [])))
    return b.construir()
