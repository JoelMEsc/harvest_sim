#!/usr/bin/env python3
"""Trace de ejemplo 2.3: campo en L con dos lotes, camino, celdas fuera del campo y relieve.  [Joel]

NO es la simulación: es un **guion** escrito a mano, como `traces_ejemplo_22.py`. Sirve para que Unity
y el visor se adapten al trace 2.3 (docs/especificacion_terreno.md §6) antes de que exista el escenario
real de El Pueblito.

Mapa (6 × 5 celdas de 12 m; x a lo largo de los surcos):

    y\\x  0  1  2  3  4  5
    0     B  c1 h1 =  =  ·      B bodega, c1/h1 bases (patio), = camino, · fuera de campo
    1     =  A  A  A  ·  ·      A lote A, Bv lote B, # obstáculo
    2     =  A  A  A  ·  ·
    3     =  Bv Bv Bv Bv Bv
    4     =  Bv Bv Bv Bv #

Una cosechadora y un carro en modo directa. El carro solo pisa camino y rastrojo (R13): llega a la
cosechadora por la celda que ella ya cosechó.

Uso:
    python tools/traces_ejemplo_23.py                     # escribe tests/fixtures/trace_ejemplo_23.json
    python tools/traces_ejemplo_23.py --salida carpeta/   # además, una copia en esa carpeta
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import TraceBuilder, escribir_trace, validar_trace  # noqa: E402
from harvest_sim.datos.campo import celdas_de_campo  # noqa: E402
from harvest_sim.datos.formato import PERFORMATIVAS  # noqa: E402

DESTINO = RAIZ / "tests" / "fixtures" / "trace_ejemplo_23.json"
H1, C1 = "cosechadora_1", "carro_1"
CELDA_M = 12.0

CONFIG = {
    "nombre": "ejemplo_23", "seed": 0, "ancho": 6, "alto": 5,
    "num_carros": 1, "num_cosechadoras": 1, "grano_por_celda": 1,
    "capacidad_cosechadora": 4, "capacidad_carro": 8,
    "tasa_transferencia": 4, "tasa_descarga": 8, "max_ticks": 500,
    "obstaculos": {"celdas": [], "regiones": []},
    "politica": {"asignacion": "directa", "umbral_aviso": 1.0, "atender_desde_bodega": False,
                 "encadenar_servicios": False, "espera_propuestas": 2, "reintento_subasta": 3,
                 "respetar_cultivo": True},
    "mapa": {"archivo": "mapas/ejemplo_23.json", "sha256": "guion"},
}
CAMINOS = [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [0, 1], [0, 2], [0, 3], [0, 4]]
FUERA = [[5, 0], [4, 1], [5, 1], [4, 2], [5, 2]]
OBSTACULOS = [[5, 4]]
LOTES = {
    "A": [[x, y] for y in (1, 2) for x in (1, 2, 3)],
    "B": [[x, y] for y in (3, 4) for x in range(1, 6) if [x, y] != [5, 4]],
}
BASE = {C1: (1, 0), H1: (2, 0)}
TIPO = {H1: "cosechadora", C1: "carro"}
ORDEN = [H1, C1]
INICIAL = {H1: {"pos": (2, 0), "ori": "S", "estado": "EN_BASE", "carga": 0},
           C1: {"pos": (1, 0), "ori": "S", "estado": "EN_BASE", "carga": 0}}
TOTAL = 16


def _altura(x: int, y: int) -> float:
    """Relieve de juguete: una loma suave que sube hacia el sureste (en metros sobre el nivel del mar)."""
    return round(1745.0 + 0.6 * x + 0.4 * y, 2)


def _rect(x0, y0, x1, y1):
    """Rectángulo en metros del marco de la cuadrícula (de celdas x0..x1, y0..y1, exclusivas)."""
    return [[x0 * CELDA_M, y0 * CELDA_M], [x1 * CELDA_M, y0 * CELDA_M],
            [x1 * CELDA_M, y1 * CELDA_M], [x0 * CELDA_M, y1 * CELDA_M]]


def _mundo() -> dict:
    mundo = {
        "ancho": CONFIG["ancho"], "alto": CONFIG["alto"], "bodega": [0, 0],
        "bases": {a: list(BASE[a]) for a in (C1, H1)}, "grano_por_celda": 1,
        "obstaculos": OBSTACULOS,
        "tamano_celda_m": CELDA_M,
        "caminos": CAMINOS,
        "fuera_de_campo": FUERA,
        "lotes": LOTES,
        "altura_m": [[_altura(x, y) for x in range(CONFIG["ancho"])] for y in range(CONFIG["alto"])],
        "geo": {
            "epsg": 32613,
            "origen_utm": [749000.0, 2375000.0],
            "rumbo_grados": 52.4,
            "atribucion": "Guion de ejemplo (sin datos reales).",
            "formas": {
                "lotes": {"A": _rect(1, 1, 4, 3), "B": _rect(1, 3, 6, 5)},
                "obstaculos": [_rect(5, 4, 6, 5)],
                "caminos": [[[0.5 * CELDA_M, 5 * CELDA_M], [0.5 * CELDA_M, 0.5 * CELDA_M],
                             [5 * CELDA_M, 0.5 * CELDA_M]]],
            },
        },
    }
    return mundo


def m(tipo, de, a, payload):
    return (tipo, de, a, payload)


# Acciones por tick. Agente: {"mover": celda, "estado": ..., "cosechar": True, "carga": n}.
GUION = {
    1: {H1: {"estado": "YENDO_A_CAMPO"}},
    2: {H1: {"mover": (3, 0)}},                                       # por el camino
    3: {H1: {"mover": (3, 1), "estado": "COSECHANDO", "cosechar": True}},
    4: {H1: {"mover": (2, 1), "cosechar": True}},
    5: {H1: {"mover": (1, 1), "cosechar": True}},
    6: {H1: {"mover": (1, 2), "cosechar": True, "estado": "LLENA_ESPERANDO"},
        "mensajes": [m("LLENA", H1, C1, {"x": 1, "y": 2, "carga": 4})]},
    7: {C1: {"estado": "YENDO_A_COSECHADORA"}},
    8: {C1: {"mover": (1, 1), "estado": "ESPERANDO_TRANSFERENCIA"}},  # rastrojo: (1, 1) ya se cosechó
    9: {H1: {"estado": "TRANSFIRIENDO"}},
    10: {H1: {"estado": "COSECHANDO", "carga": 0}, C1: {"carga": 4},
         "mensajes": [m("TRANSFERENCIA_TERMINADA", H1, C1, {"cantidad": 4})]},
    11: {H1: {"mover": (2, 2), "cosechar": True}, C1: {"estado": "YENDO_A_BODEGA"}},
    12: {H1: {"mover": (3, 2), "cosechar": True}, C1: {"mover": (1, 0)}},
    13: {H1: {"mover": (3, 3), "cosechar": True}, C1: {"mover": (0, 0), "estado": "DESCARGANDO"}},
    14: {H1: {"mover": (2, 3), "cosechar": True, "estado": "LLENA_ESPERANDO"},
         C1: {"estado": "REGRESANDO_A_BASE", "carga": 0},
         "eventos": [{"tipo": "DEPOSITO", "agente": C1, "cantidad": 4, "entregado_total": 4}],
         "mensajes": [m("LLENA", H1, C1, {"x": 2, "y": 3, "carga": 4})]},
    15: {C1: {"mover": (1, 0), "estado": "EN_BASE"}},
    16: {C1: {"estado": "YENDO_A_COSECHADORA"}},
}

ORIENTACION = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "O"}


def _registro(t: int, agente: str, e: dict) -> dict:
    capacidad = CONFIG["capacidad_cosechadora"] if TIPO[agente] == "cosechadora" else CONFIG["capacidad_carro"]
    return {"tick": t, "agent_id": agente, "tipo": TIPO[agente],
            "pose": {"x": e["pos"][0], "y": e["pos"][1], "orientacion": e["ori"]},
            "estado": e["estado"], "carga": {"actual": e["carga"], "capacidad": capacidad}}


def generar() -> dict:
    """Devuelve el trace de ejemplo 2.3 (dict), después de comprobar el guion."""
    mundo = _mundo()
    campo = celdas_de_campo(mundo)
    fuera = {tuple(c) for c in FUERA} | {tuple(c) for c in OBSTACULOS}
    caminos = {tuple(c) for c in CAMINOS}
    catalogo = [{"id": a, "tipo": TIPO[a],
                 "capacidad": CONFIG["capacidad_cosechadora"] if TIPO[a] == "cosechadora" else CONFIG["capacidad_carro"],
                 "base": list(BASE[a])} for a in ORDEN]
    estado = {a: dict(v) for a, v in INICIAL.items()}
    builder = TraceBuilder(CONFIG, mundo, catalogo)
    builder.agregar_tick(0, [_registro(0, a, estado[a]) for a in ORDEN], [])
    pendientes, siguiente_id, cosechado, entregado, cosechadas = [], 1, 0, 0, set()
    for t in range(1, TOTAL + 1):
        acciones = GUION.get(t, {})
        entregas = [{"tipo": "MENSAJE_ENTREGADO", "id": p["id"], "a": p["a"]}
                    for p in sorted(pendientes, key=lambda p: p["id"]) if p["entrega_en"] == t]
        pendientes = [p for p in pendientes if p["entrega_en"] != t]
        eventos, previas = [], {a: estado[a]["pos"] for a in ORDEN}
        for a in ORDEN:
            accion, e = acciones.get(a, {}), estado[a]
            if "mover" in accion:
                dx, dy = accion["mover"][0] - e["pos"][0], accion["mover"][1] - e["pos"][1]
                assert (dx, dy) in ORIENTACION, f"tick {t}: {a} salta de {e['pos']} a {accion['mover']}"
                e["pos"], e["ori"] = accion["mover"], ORIENTACION[(dx, dy)]
                assert e["pos"] not in fuera, f"tick {t}: {a} entra a {e['pos']} (R10/R12)"
                if TIPO[a] == "carro":  # R13: el carro solo pisa camino y rastrojo
                    assert e["pos"] in caminos or e["pos"] in cosechadas, f"tick {t}: {a} pisa cultivo en {e['pos']}"
            if accion.get("cosechar"):
                assert e["pos"] in campo and e["pos"] not in cosechadas
                cosechadas.add(e["pos"])
                e["carga"] += 1
                cosechado += 1
                eventos.append({"tipo": "CELDA_COSECHADA", "celda": list(e["pos"]), "agente": a, "cantidad": 1})
            e["estado"] = accion.get("estado", e["estado"])
            e["carga"] = accion.get("carga", e["carga"])
        eventos += acciones.get("eventos", [])
        for ev in acciones.get("eventos", []):
            if ev["tipo"] == "DEPOSITO":
                entregado = ev["entregado_total"]
        enviados = []
        for tipo, de, a, payload in acciones.get("mensajes", []):
            enviados.append({"tipo": "MENSAJE_ENVIADO", "id": siguiente_id, "tipo_mensaje": tipo,
                             "performativa": PERFORMATIVAS[tipo], "de": de, "a": a, "payload": payload,
                             "entrega_en": t + 1})
            pendientes.append({"id": siguiente_id, "a": a, "entrega_en": t + 1})
            siguiente_id += 1
        celdas = [estado[a]["pos"] for a in ORDEN]
        assert len(set(celdas)) == len(celdas), f"tick {t}: dos agentes en la misma celda {celdas}"
        assert cosechado == sum(estado[a]["carga"] for a in ORDEN) + entregado, f"tick {t}: no se conserva el grano"
        builder.agregar_tick(t, [_registro(t, a, estado[a]) for a in ORDEN], entregas + eventos + enviados)
    trace = builder.construir()
    errores = validar_trace(trace)
    assert not errores, errores[:5]
    assert trace["schema_version"] == "2.3"
    return trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Escribe el trace de ejemplo 2.3 (guion, no simulación).")
    parser.add_argument("--salida", help="carpeta donde escribir además una copia (por ejemplo, la de Unity)")
    args = parser.parse_args(argv)
    trace = generar()
    escribir_trace(trace, DESTINO)
    rutas = [DESTINO]
    if args.salida:
        destino = Path(args.salida) / "ejemplo_23.json"
        escribir_trace(trace, destino)
        rutas.append(destino)
    for r in rutas:
        print(f"escrito: {r}")
    print(f"ticks: {trace['meta']['total_ticks']} | campo: {len(celdas_de_campo(trace['mundo']))} celdas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
