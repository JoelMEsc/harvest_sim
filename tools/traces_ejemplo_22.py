#!/usr/bin/env python3
"""Trace de ejemplo 2.2 con dos cosechadoras, dos carros, subasta, recargas y restricciones.  [Joel]

NO es la simulación: es un **guion** escrito a mano (decisión D5 del plan de Datos). Sirve para
desarrollar y probar el visor, Unity, el validador y las métricas nuevas sin esperar la simulación
completa. Lo que se escribe a mano son las acciones de cada tick (moverse, cambiar de estado, cosechar,
enviar mensajes); el guion calcula solo lo mecánico: orientación, combustible (consumo y recarga en la
base, con las reglas de la especificación §9), entregas de mensajes en su `entrega_en` y el checksum.

Antes de escribir, comprueba: el validador no da errores, nunca hay dos agentes en la misma celda ni se
intercambian, cada agente se mueve a lo más una celda por tick y el grano se conserva en cada tick.

Qué muestra (mapa 6 × 4, obstáculo en (1, 2), rendimiento variable):
- Subasta de `cosechadora_2#1`: llamada a los dos carros; `carro_1` ofrece y `carro_2` rechaza por
  combustible (con su RESTRICCION `combustible_reserva`); gana `carro_1`.
- Subasta de `cosechadora_1#1`: ofrecen los dos carros (la oferta de `carro_2` llega con 1 tick de retraso);
  gana `carro_1` por menor costo y `carro_2` recibe RECHAZO_PROPUESTA.
- `carro_2` empieza con poco combustible y se recarga en su base (eventos RECARGA).
- `carro_1` atiende los dos servicios seguidos (encadena) y descarga 7 unidades en la bodega.

Uso:
    python tools/traces_ejemplo_22.py                     # escribe tests/fixtures/trace_ejemplo_22.json
    python tools/traces_ejemplo_22.py --salida carpeta/   # además, una copia en esa carpeta
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import TraceBuilder, escribir_trace, validar_trace  # noqa: E402
from harvest_sim.datos.formato import PERFORMATIVAS  # noqa: E402

DESTINO = RAIZ / "tests" / "fixtures" / "trace_ejemplo_22.json"
H1, H2, C1, C2 = "cosechadora_1", "cosechadora_2", "carro_1", "carro_2"

CONFIG = {
    "nombre": "ejemplo_22", "seed": 0, "ancho": 6, "alto": 4,
    "num_carros": 2, "num_cosechadoras": 2, "grano_por_celda": 1,
    "capacidad_cosechadora": 4, "capacidad_carro": 8,
    "tasa_transferencia": 3, "tasa_descarga": 4, "max_ticks": 500,
    "obstaculos": {"celdas": [[1, 2]], "regiones": []},
    "politica": {"asignacion": "subasta", "umbral_aviso": 0.5, "atender_desde_bodega": False,
                 "encadenar_servicios": True, "espera_propuestas": 2, "reintento_subasta": 3},
    "incertidumbre": {"rendimiento": {"minimo": 1, "maximo": 2}, "duracion_extra_maxima": 0,
                      "retraso_mensajes": {"probabilidad": 0.1, "maximo": 1}},
    "combustible": {"tanque_cosechadora": 50, "tanque_carro": 30,
                    "consumo_por_celda_cosechadora": 2.0, "consumo_por_celda_carro": 1.0,
                    "consumo_por_tick_encendido": 0.5, "reserva": 0.15, "tasa_recarga": 5},
    "costo": {"pesos": {"tiempo": 1.0, "distancia": 0.5, "colisiones": 1000.0, "ocio": 5.0,
                        "combustible": 0.2, "restricciones": 10.0}},
}
RENDIMIENTO = [
    [0, 0, 0, 0, 0, 0],
    [1, 1, 1, 1, 2, 1],
    [1, 0, 2, 1, 1, 2],   # (1, 2) es obstáculo: 0
    [1, 1, 2, 1, 1, 1],
]
TIPO = {H1: "cosechadora", H2: "cosechadora", C1: "carro", C2: "carro"}
BASE = {C1: (1, 0), C2: (2, 0), H1: (3, 0), H2: (4, 0)}
ORDEN = [H1, H2, C1, C2]  # orden del tick: cosechadoras y luego carros (especificación §3)
INICIAL = {
    H1: {"pos": (3, 0), "ori": "S", "estado": "EN_BASE", "carga": 0, "combustible": 50.0},
    H2: {"pos": (4, 0), "ori": "S", "estado": "EN_BASE", "carga": 0, "combustible": 50.0},
    C1: {"pos": (1, 0), "ori": "N", "estado": "EN_BASE", "carga": 0, "combustible": 30.0},
    C2: {"pos": (2, 0), "ori": "N", "estado": "EN_BASE", "carga": 0, "combustible": 8.0},
}
TOTAL = 24


def m(tipo, de, a, payload, retraso=0):
    """Un mensaje enviado en el tick del guion (se entrega en t + 1 + retraso)."""
    return ("mensaje", tipo, de, a, payload, retraso)


# Acciones por tick. Agente: {"mover": celda, "estado": ..., "cosechar": True, "carga": n}.
# "eventos": eventos del mundo (RESTRICCION, DEPOSITO); "mensajes": mensajes enviados, en orden.
GUION = {
    1: {H1: {"mover": (3, 1), "estado": "COSECHANDO", "cosechar": True},
        H2: {"mover": (4, 1), "estado": "COSECHANDO", "cosechar": True},
        "mensajes": [m("SOLICITUD_SERVICIO", H2, C1, {"servicio": "cosechadora_2#1", "x": 4, "y": 1, "carga": 2, "capacidad": 4}),
                     m("SOLICITUD_SERVICIO", H2, C2, {"servicio": "cosechadora_2#1", "x": 4, "y": 1, "carga": 2, "capacidad": 4})]},
    2: {H1: {"mover": (2, 1), "cosechar": True},
        H2: {"mover": (5, 1), "cosechar": True},
        "eventos": [{"tipo": "RESTRICCION", "agente": C2, "regla": "combustible_reserva",
                     "detalle": "rechaza cosechadora_2#1: no le alcanza el combustible sin bajar de la reserva"}],
        "mensajes": [m("SOLICITUD_SERVICIO", H1, C1, {"servicio": "cosechadora_1#1", "x": 2, "y": 1, "carga": 2, "capacidad": 4}),
                     m("SOLICITUD_SERVICIO", H1, C2, {"servicio": "cosechadora_1#1", "x": 2, "y": 1, "carga": 2, "capacidad": 4}),
                     m("PROPUESTA", C1, H2, {"servicio": "cosechadora_2#1", "costo": 6}),
                     m("RECHAZO", C2, H2, {"servicio": "cosechadora_2#1", "motivo": "combustible"})]},
    3: {H1: {"mover": (2, 2), "cosechar": True, "estado": "LLENA_ESPERANDO"},
        H2: {"estado": "LLENA_ESPERANDO"},   # la siguiente celda (5, 2) rinde 2 y ya no cabe: se considera llena
        "mensajes": [m("PROPUESTA", C1, H1, {"servicio": "cosechadora_1#1", "costo": 10}),
                     m("PROPUESTA", C2, H1, {"servicio": "cosechadora_1#1", "costo": 12}, retraso=1)]},
    4: {"mensajes": [m("ACEPTACION", H2, C1, {"servicio": "cosechadora_2#1"})]},
    5: {C1: {"estado": "YENDO_A_COSECHADORA"},
        "mensajes": [m("ACEPTACION", H1, C1, {"servicio": "cosechadora_1#1"}),
                     m("RECHAZO_PROPUESTA", H1, C2, {"servicio": "cosechadora_1#1"})]},
    6: {C1: {"mover": (1, 1)}},
    7: {C1: {"mover": (2, 1)}},
    8: {C1: {"mover": (3, 1)}},
    9: {C1: {"mover": (4, 1), "estado": "ESPERANDO_TRANSFERENCIA"}},
    10: {H2: {"estado": "TRANSFIRIENDO"}},
    11: {H2: {"estado": "REGRESANDO_A_BASE", "carga": 0}, C1: {"carga": 3},
         "mensajes": [m("TRANSFERENCIA_TERMINADA", H2, C1, {"servicio": "cosechadora_2#1", "cantidad": 3})]},
    12: {H2: {"mover": (5, 0)}, C1: {"estado": "YENDO_A_COSECHADORA"}},
    13: {H2: {"mover": (4, 0), "estado": "FIN"}, C1: {"mover": (3, 1)}},
    14: {C1: {"mover": (2, 1), "estado": "ESPERANDO_TRANSFERENCIA"}},
    15: {H1: {"estado": "TRANSFIRIENDO"}},
    17: {H1: {"estado": "REGRESANDO_A_BASE", "carga": 0}, C1: {"carga": 7},
         "mensajes": [m("TRANSFERENCIA_TERMINADA", H1, C1, {"servicio": "cosechadora_1#1", "cantidad": 4})]},
    18: {C1: {"estado": "YENDO_A_BODEGA"}},
    19: {H1: {"mover": (3, 2)}, C1: {"mover": (1, 1)}},
    20: {H1: {"mover": (3, 1)}, C1: {"mover": (1, 0)}},
    21: {H1: {"mover": (3, 0), "estado": "FIN"}, C1: {"mover": (0, 0), "estado": "DESCARGANDO"}},
    23: {C1: {"estado": "REGRESANDO_A_BASE", "carga": 0},
         "eventos": [{"tipo": "DEPOSITO", "agente": C1, "cantidad": 7, "entregado_total": 7}]},
    24: {C1: {"mover": (1, 0), "estado": "EN_BASE"}},
}

ORIENTACION = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "O"}


def _consumir(estado: dict, agente: str, se_movio: bool, eventos: list) -> None:
    """Combustible del tick (especificación §9): consumo al moverse o con el motor encendido; recarga en la base."""
    c = CONFIG["combustible"]
    tipo = TIPO[agente]
    if se_movio:
        estado["combustible"] -= c[f"consumo_por_celda_{tipo}"]
    elif estado["estado"] not in ("EN_BASE", "FIN"):
        estado["combustible"] -= c["consumo_por_tick_encendido"]
    tanque = c[f"tanque_{tipo}"]
    if estado["pos"] == BASE[agente] and estado["estado"] in ("EN_BASE", "FIN") and estado["combustible"] < tanque:
        cantidad = min(c["tasa_recarga"], tanque - estado["combustible"])
        estado["combustible"] = round(estado["combustible"] + cantidad, 2)
        eventos.append({"tipo": "RECARGA", "agente": agente, "cantidad": round(cantidad, 2),
                        "nivel": estado["combustible"]})
    estado["combustible"] = round(estado["combustible"], 2)


def _registro(t: int, agente: str, e: dict) -> dict:
    capacidad = CONFIG["capacidad_cosechadora"] if TIPO[agente] == "cosechadora" else CONFIG["capacidad_carro"]
    return {"tick": t, "agent_id": agente, "tipo": TIPO[agente],
            "pose": {"x": e["pos"][0], "y": e["pos"][1], "orientacion": e["ori"]},
            "estado": e["estado"], "carga": {"actual": e["carga"], "capacidad": capacidad},
            "combustible": e["combustible"]}


def generar() -> dict:
    """Devuelve el trace de ejemplo 2.2 (dict), después de comprobar el guion."""
    mundo = {"ancho": CONFIG["ancho"], "alto": CONFIG["alto"], "bodega": [0, 0],
             "bases": {a: list(BASE[a]) for a in (C1, C2, H1, H2)}, "grano_por_celda": 1,
             "obstaculos": [[1, 2]], "rendimiento": copy.deepcopy(RENDIMIENTO)}
    catalogo = [{"id": a, "tipo": TIPO[a],
                 "capacidad": CONFIG["capacidad_cosechadora"] if TIPO[a] == "cosechadora" else CONFIG["capacidad_carro"],
                 "base": list(BASE[a])} for a in ORDEN]
    estado = copy.deepcopy(INICIAL)
    builder = TraceBuilder(CONFIG, mundo, catalogo)
    builder.agregar_tick(0, [_registro(0, a, estado[a]) for a in ORDEN], [])
    pendientes: list[dict] = []   # mensajes en tránsito
    siguiente_id, cosechado, entregado = 1, 0, 0
    for t in range(1, TOTAL + 1):
        acciones = GUION.get(t, {})
        entregas = [{"tipo": "MENSAJE_ENTREGADO", "id": p["id"], "a": p["a"]}
                    for p in sorted(pendientes, key=lambda p: p["id"]) if p["entrega_en"] == t]
        pendientes = [p for p in pendientes if p["entrega_en"] != t]
        mundo_eventos, previas = [], {a: estado[a]["pos"] for a in ORDEN}
        for a in ORDEN:
            accion = acciones.get(a, {})
            e = estado[a]
            if "mover" in accion:
                dx, dy = accion["mover"][0] - e["pos"][0], accion["mover"][1] - e["pos"][1]
                assert (dx, dy) in ORIENTACION, f"tick {t}: {a} salta de {e['pos']} a {accion['mover']}"
                e["pos"], e["ori"] = accion["mover"], ORIENTACION[(dx, dy)]
            if accion.get("cosechar"):
                cantidad = RENDIMIENTO[e["pos"][1]][e["pos"][0]]
                e["carga"] += cantidad
                cosechado += cantidad
                mundo_eventos.append({"tipo": "CELDA_COSECHADA", "celda": list(e["pos"]), "agente": a,
                                      "cantidad": cantidad})
            e["estado"] = accion.get("estado", e["estado"])
            e["carga"] = accion.get("carga", e["carga"])
        mundo_eventos += acciones.get("eventos", [])
        for ev in acciones.get("eventos", []):
            if ev["tipo"] == "DEPOSITO":
                entregado = ev["entregado_total"]
        for a in ORDEN:
            _consumir(estado[a], a, estado[a]["pos"] != previas[a], mundo_eventos)
        enviados = []
        for _, tipo, de, a, payload, retraso in acciones.get("mensajes", []):
            mensaje = {"tipo": "MENSAJE_ENVIADO", "id": siguiente_id, "tipo_mensaje": tipo,
                       "performativa": PERFORMATIVAS[tipo], "de": de, "a": a, "payload": payload,
                       "entrega_en": t + 1 + retraso}
            enviados.append(mensaje)
            pendientes.append({"id": siguiente_id, "a": a, "entrega_en": t + 1 + retraso})
            siguiente_id += 1
        # Comprobaciones del guion: sin colisiones ni intercambios, y conservación del grano.
        celdas = [estado[a]["pos"] for a in ORDEN]
        assert len(set(celdas)) == len(celdas), f"tick {t}: dos agentes en la misma celda {celdas}"
        for a in ORDEN:
            for b in ORDEN:
                assert not (a < b and estado[a]["pos"] == previas[b] and estado[b]["pos"] == previas[a]
                            and previas[a] != previas[b]), f"tick {t}: {a} y {b} se intercambian"
        assert cosechado == sum(estado[a]["carga"] for a in ORDEN) + entregado, f"tick {t}: no se conserva el grano"
        builder.agregar_tick(t, [_registro(t, a, estado[a]) for a in ORDEN], entregas + mundo_eventos + enviados)
    assert not pendientes, f"mensajes sin entregar: {pendientes}"
    trace = builder.construir()
    errores = validar_trace(trace)
    assert not errores, errores[:5]
    return trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Escribe el trace de ejemplo 2.2 (guion, no simulación).")
    parser.add_argument("--salida", help="carpeta donde escribir además una copia (por ejemplo, la de Unity)")
    args = parser.parse_args(argv)
    trace = generar()
    escribir_trace(trace, DESTINO)
    rutas = [DESTINO]
    if args.salida:
        destino = Path(args.salida) / "ejemplo_22.json"
        escribir_trace(trace, destino)
        rutas.append(destino)
    tipos = [e["tipo"] for t in trace["ticks"] for e in t["cambios"]]
    for r in rutas:
        print(f"escrito: {r}")
    print(f"ticks: {trace['meta']['total_ticks']} | eventos: {dict(sorted({x: tipos.count(x) for x in set(tipos)}.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
