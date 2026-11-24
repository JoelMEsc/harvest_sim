#!/usr/bin/env python3
"""Genera tests/fixtures/trace_ejemplo.json (tarea 2 de Datos).

NO es la simulación del equipo: es un generador DETERMINISTA (sin aleatoriedad) de datos de ejemplo
que aplica las reglas del §5 de la especificación de forma simplificada (1 cosechadora, 1 carro, sin
obstáculos), para que el visor, las métricas y los experimentos se desarrollen sin esperar la simulación
real. Arma el archivo con el propio TraceBuilder. Se queda hasta que exista `simulacion.ejecutar`;
entonces el fixture se generará con una corrida corta de la simulación real.

Convención: el tick 0 es el estado inicial (antes de cualquier paso); los pasos empiezan en el tick 1.

Uso:
    python tools/generar_trace_ejemplo.py                  # reescribe el fixture de las pruebas
    python tools/generar_trace_ejemplo.py --escenarios     # tres escenarios de ejemplo en runs/ejemplo/
    python tools/generar_trace_ejemplo.py --escenarios --salida otra/carpeta
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import (  # noqa: E402
    PERFORMATIVAS,
    TraceBuilder,
    calcular_metricas,
    cargar_trace,
    escribir_trace,
    validar_trace,
    verificar_checksums,
)

DESTINO = RAIZ / "tests" / "fixtures" / "trace_ejemplo.json"
SALIDA_ESCENARIOS = RAIZ / "runs" / "ejemplo"
H, C = "cosechadora_1", "carro_1"

CONFIG = {
    "nombre": "ejemplo_fixture",
    "seed": 0,
    "ancho": 4,
    "alto": 3,
    "num_carros": 1,
    "num_cosechadoras": 1,
    "grano_por_celda": 1,
    "capacidad_cosechadora": 3,
    "capacidad_carro": 6,
    "tasa_transferencia": 1,
    "tasa_descarga": 1,
    "max_ticks": 500,
}

DIRS = [(0, -1, "N"), (1, 0, "E"), (0, 1, "S"), (-1, 0, "O")]  # orden N, E, S, O
ORIENTACION = {(dx, dy): o for dx, dy, o in DIRS}


def vecinos(celda, ancho, alto):
    x, y = celda
    return [(x + dx, y + dy) for dx, dy, _ in DIRS if 0 <= x + dx < ancho and 0 <= y + dy < alto]


def bfs(origen, destino, ancho, alto, bloqueadas):
    """Ruta más corta y determinista, sin el origen y con el destino; None si no hay ruta."""
    if origen == destino:
        return []
    previo = {origen: None}
    cola = deque([origen])
    while cola:
        c = cola.popleft()
        for n in vecinos(c, ancho, alto):
            if n in previo or n in bloqueadas:
                continue
            previo[n] = c
            if n == destino:
                ruta = [n]
                while previo[ruta[-1]] != origen:
                    ruta.append(previo[ruta[-1]])
                return ruta[::-1]
            cola.append(n)
    return None


def simular(cfg, forzar_bloqueo=True):
    """Devuelve [(tick, registros completos, eventos que no son AGENTE)] y datos para validar.

    `forzar_bloqueo`: con 1 cosechadora y 1 carro, un bloqueo no ocurre solo (la regla real evita que
    el carro se estacione en la siguiente celda de la serpentina). Para tener un BLOQUEO en los datos
    de ejemplo, en el PRIMER viaje el carro se estaciona justo ahí: es un caso construido a propósito.
    """
    ancho, alto = cfg["ancho"], cfg["alto"]
    cap = {H: cfg["capacidad_cosechadora"], C: cfg["capacidad_carro"]}
    tipo = {H: "cosechadora", C: "carro"}
    bodega = (0, 0)
    base = {C: (1, 0), H: (2, 0)}
    camino = [
        (x, y)
        for i, y in enumerate(range(1, alto))
        for x in (range(ancho) if i % 2 == 0 else range(ancho - 1, -1, -1))
    ]
    total_campo = len(camino) * cfg["grano_por_celda"]
    ag = {
        H: dict(pos=base[H], ori="S", estado="EN_BASE", carga=0, idx=-1, ruta=[], destino=None, inicio=0, dur=0, inbox=[]),
        C: dict(pos=base[C], ori="N", estado="EN_BASE", carga=0, ruta=[], destino=None, inicio=0, dur=0, inbox=[]),
    }
    S = {"cosechado": 0, "entregado": 0, "id": 1, "viajes": 0}
    pendientes = []
    salida = []
    contabilidad = []

    def registros(t):
        return [
            {
                "tick": t, "agent_id": a, "tipo": tipo[a],
                "pose": {"x": ag[a]["pos"][0], "y": ag[a]["pos"][1], "orientacion": ag[a]["ori"]},
                "estado": ag[a]["estado"],
                "carga": {"actual": ag[a]["carga"], "capacidad": cap[a]},
            }
            for a in (H, C)
        ]

    salida.append((0, registros(0), []))
    contabilidad.append((0, 0, 0))
    t = 0
    while True:
        t += 1
        if t > cfg["max_ticks"]:
            raise RuntimeError("la simulación de ejemplo no termina")
        eventos = []

        # 1) entrega de los mensajes enviados en el tick anterior
        for m in [m for m in pendientes if m["entrega_en"] == t]:
            ag[m["a"]]["inbox"].append(m)
            eventos.append({"tipo": "MENSAJE_ENTREGADO", "id": m["id"], "a": m["a"]})
            pendientes.remove(m)

        def enviar(tipo_mensaje, de, a, payload):
            m = {"id": S["id"], "tipo_mensaje": tipo_mensaje, "performativa": PERFORMATIVAS[tipo_mensaje],
                 "de": de, "a": a, "payload": payload, "entrega_en": t + 1}
            S["id"] += 1
            pendientes.append(m)
            eventos.append({"tipo": "MENSAJE_ENVIADO", **m})

        def mover(a, destino):
            dx, dy = destino[0] - a["pos"][0], destino[1] - a["pos"][1]
            a["ori"] = ORIENTACION[(dx, dy)]
            a["pos"] = destino

        def bloqueo(nombre):
            eventos.append({"tipo": "BLOQUEO", "agente": nombre})

        def avanzar(nombre, otro, fijas):
            """Un paso por la ruta; recalcula si la celda está ocupada; si no hay ruta, espera."""
            a = ag[nombre]
            if a["ruta"] is None:  # el destino estaba ocupado al planear: se vuelve a intentar
                a["ruta"] = bfs(a["pos"], a["destino"], ancho, alto, fijas | {ag[otro]["pos"]})
                if a["ruta"] is None:
                    bloqueo(nombre)
                    return False
            nxt = a["ruta"][0]
            if nxt == ag[otro]["pos"]:
                alt = bfs(a["pos"], a["destino"], ancho, alto, fijas | {ag[otro]["pos"]})
                if alt is None:
                    bloqueo(nombre)
                    return False
                a["ruta"] = alt
                nxt = alt[0]
            mover(a, nxt)
            a["ruta"].pop(0)
            return True

        def cosechar():
            h = ag[H]
            S["cosechado"] += cfg["grano_por_celda"]
            h["carga"] += cfg["grano_por_celda"]
            eventos.append({"tipo": "CELDA_COSECHADA", "celda": list(h["pos"]), "agente": H,
                            "cantidad": cfg["grano_por_celda"]})
            if h["carga"] == cap[H] or h["idx"] == len(camino) - 1:
                enviar("LLENA", H, C, {"x": h["pos"][0], "y": h["pos"][1], "carga": h["carga"]})
                h["estado"] = "LLENA_ESPERANDO"

        # 2) cosechadora
        h, c = ag[H], ag[C]
        if h["estado"] == "EN_BASE":
            h["estado"] = "YENDO_A_CAMPO"
            h["destino"] = camino[0]
            h["ruta"] = bfs(h["pos"], camino[0], ancho, alto, {bodega, c["pos"]})
        elif h["estado"] == "YENDO_A_CAMPO":
            if avanzar(H, C, {bodega}) and h["pos"] == camino[0]:
                h["idx"] = 0
                h["estado"] = "COSECHANDO"
                cosechar()
        elif h["estado"] == "COSECHANDO":
            nxt = camino[h["idx"] + 1]
            if nxt == c["pos"]:
                bloqueo(H)
            else:
                mover(h, nxt)
                h["idx"] += 1
                cosechar()
        elif h["estado"] == "LLENA_ESPERANDO":
            vecino = abs(h["pos"][0] - c["pos"][0]) + abs(h["pos"][1] - c["pos"][1]) == 1
            if c["estado"] == "ESPERANDO_TRANSFERENCIA" and vecino:
                h["estado"] = "TRANSFIRIENDO"
                h["inicio"], h["dur"] = t, math.ceil(h["carga"] / cfg["tasa_transferencia"])
        elif h["estado"] == "TRANSFIRIENDO":
            if t - h["inicio"] == h["dur"]:
                delta = min(h["carga"], cap[C] - c["carga"])
                h["carga"] -= delta
                c["carga"] += delta
                enviar("TRANSFERENCIA_TERMINADA", H, C, {"cantidad": delta})
                if h["idx"] < len(camino) - 1:
                    h["estado"] = "COSECHANDO"
                else:
                    h["estado"] = "REGRESANDO_A_BASE"
                    h["destino"] = base[H]
                    h["ruta"] = bfs(h["pos"], base[H], ancho, alto, {bodega, c["pos"]})
        elif h["estado"] == "REGRESANDO_A_BASE":
            if avanzar(H, C, {bodega}) and h["pos"] == base[H]:
                h["estado"] = "FIN"

        # 3) carro
        if c["estado"] == "EN_BASE":
            if c["inbox"]:
                msg = c["inbox"].pop(0)
                objetivo = (msg["payload"]["x"], msg["payload"]["y"])
                siguiente = camino[h["idx"] + 1] if h["idx"] + 1 < len(camino) else None
                evitar = {siguiente} if siguiente else set()
                cand = [n for n in vecinos(objetivo, ancho, alto) if n != bodega and n != h["pos"]]
                if forzar_bloqueo and S["viajes"] == 0 and siguiente in cand:
                    evitar = set()  # caso construido: se estaciona en la siguiente celda de la cosechadora
                    cand = [siguiente]
                cand = [n for n in cand if n not in evitar] or cand
                rutas = {n: bfs(c["pos"], n, ancho, alto, {h["pos"]}) for n in cand}
                elegido = min((n for n in cand if rutas[n] is not None), key=lambda n: len(rutas[n]))
                S["viajes"] += 1
                c["estado"] = "YENDO_A_COSECHADORA"
                c["destino"], c["ruta"] = elegido, rutas[elegido]
        elif c["estado"] == "YENDO_A_COSECHADORA":
            if c["pos"] == c["destino"] or (avanzar(C, H, set()) and c["pos"] == c["destino"]):
                c["estado"] = "ESPERANDO_TRANSFERENCIA"
        elif c["estado"] == "ESPERANDO_TRANSFERENCIA":
            if c["inbox"] and c["inbox"][0]["tipo_mensaje"] == "TRANSFERENCIA_TERMINADA":
                c["inbox"].pop(0)
                c["estado"], c["destino"] = "YENDO_A_BODEGA", bodega
                c["ruta"] = bfs(c["pos"], bodega, ancho, alto, {h["pos"]})
        elif c["estado"] == "YENDO_A_BODEGA":
            if avanzar(C, H, set()) and c["pos"] == bodega:
                c["estado"] = "DESCARGANDO"
                c["inicio"], c["dur"] = t, math.ceil(c["carga"] / cfg["tasa_descarga"])
        elif c["estado"] == "DESCARGANDO":
            if t - c["inicio"] == c["dur"]:
                S["entregado"] += c["carga"]
                eventos.append({"tipo": "DEPOSITO", "agente": C, "cantidad": c["carga"], "entregado_total": S["entregado"]})
                c["carga"] = 0
                c["estado"], c["destino"] = "REGRESANDO_A_BASE", base[C]
                c["ruta"] = bfs(c["pos"], base[C], ancho, alto, {h["pos"]})
        elif c["estado"] == "REGRESANDO_A_BASE":
            if avanzar(C, H, set()) and c["pos"] == base[C]:
                c["estado"] = "EN_BASE"

        salida.append((t, registros(t), eventos))
        contabilidad.append((t, S["cosechado"], S["entregado"]))
        if (h["estado"] == "FIN" and c["estado"] == "EN_BASE" and not c["inbox"] and c["carga"] == 0
                and S["entregado"] == total_campo):
            break
    return salida, contabilidad, total_campo


def validar(salida, contabilidad, total_campo, cfg):
    """Reglas físicas sobre el guion: R2 (un paso), R3 (nunca la misma celda), R7 (conservación)."""
    previo = None
    for (t, regs, _), (_, cosechado, entregado) in zip(salida, contabilidad):
        poses = {r["agent_id"]: (r["pose"]["x"], r["pose"]["y"]) for r in regs}
        assert len(set(poses.values())) == len(poses), f"R3 en el tick {t}"
        if previo:
            for a, p in poses.items():
                assert abs(p[0] - previo[a][0]) + abs(p[1] - previo[a][1]) <= 1, f"R2 en el tick {t}"
        en_agentes = sum(r["carga"]["actual"] for r in regs)
        assert cosechado == en_agentes + entregado, f"R7 en el tick {t}"
        previo = poses
    assert contabilidad[-1][2] == total_campo


def generar(cfg=None):
    """Devuelve el trace de ejemplo (dict) para el config dado."""
    cfg = CONFIG if cfg is None else cfg
    obs = cfg.get("obstaculos") or {}
    if obs.get("celdas") or obs.get("regiones"):
        raise ValueError("el generador de ejemplo no soporta obstáculos")
    salida, contabilidad, total_campo = simular(cfg)
    validar(salida, contabilidad, total_campo, cfg)
    mundo = {
        "ancho": cfg["ancho"], "alto": cfg["alto"], "bodega": [0, 0],
        "bases": {C: [1, 0], H: [2, 0]}, "grano_por_celda": cfg["grano_por_celda"], "obstaculos": [],
    }
    agentes = [
        {"id": H, "tipo": "cosechadora", "capacidad": cfg["capacidad_cosechadora"], "base": [2, 0]},
        {"id": C, "tipo": "carro", "capacidad": cfg["capacidad_carro"], "base": [1, 0]},
    ]
    b = TraceBuilder(cfg, mundo, agentes)
    for t, regs, eventos in salida:
        b.agregar_tick(t, regs, eventos)
    return b.construir()


def escenarios_de_ejemplo():
    """Tres configuraciones de ejemplo (datos inventados, NO los escenarios reales de config/).

    ejemplo_a: la del fixture (campo de 4 x 2, cosechadora de 3 y carro de 6, transferencia y descarga lentas).
    ejemplo_b: campo más ancho (5 x 2), más capacidad (4 y 8) y transferencia más rápida.
    ejemplo_c: el campo de A con transferencia y descarga más rápidas.
    """
    return {
        "ejemplo_a": dict(CONFIG, nombre="ejemplo_a"),
        "ejemplo_b": dict(CONFIG, nombre="ejemplo_b", ancho=5, capacidad_cosechadora=4, capacidad_carro=8,
                          tasa_transferencia=2),
        "ejemplo_c": dict(CONFIG, nombre="ejemplo_c", tasa_transferencia=2, tasa_descarga=3),
    }


def generar_escenarios(salida=SALIDA_ESCENARIOS):
    """Escribe <salida>/<nombre>/trace.json para cada escenario de ejemplo y devuelve las rutas.
    Cada trace se valida antes de escribirse."""
    rutas = []
    for nombre, cfg in escenarios_de_ejemplo().items():
        trace = generar(cfg)
        errores = validar_trace(trace)
        if errores:
            raise ValueError(f"el escenario {nombre} no es válido: {errores[:3]}")
        ruta = Path(salida) / nombre / "trace.json"
        escribir_trace(trace, ruta)
        rutas.append(ruta)
    return rutas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera datos de ejemplo del trace 2.2 (no es la simulación real).")
    parser.add_argument("--escenarios", action="store_true",
                        help="genera los tres escenarios de ejemplo en lugar del fixture de las pruebas")
    parser.add_argument("--salida", default=str(SALIDA_ESCENARIOS),
                        help="carpeta para --escenarios (default: runs/ejemplo)")
    args = parser.parse_args(argv)

    if args.escenarios:
        for ruta in generar_escenarios(args.salida):
            m = calcular_metricas(cargar_trace(ruta))
            print(f"escrito: {ruta}  (ocioso {m['tiempo_ocioso_cosechadora']} ticks, "
                  f"completación {m['tiempo_completacion']} ticks)")
        return 0

    trace = generar()
    assert verificar_checksums(trace) and not validar_trace(trace)
    escribir_trace(trace, DESTINO)
    eventos = [e["tipo"] for t in trace["ticks"] for e in t["cambios"]]
    print(f"escrito: {DESTINO}")
    print(f"ticks totales: {trace['meta']['total_ticks']} | ticks con cambios: {len(trace['ticks'])}")
    print({tipo: eventos.count(tipo) for tipo in sorted(set(eventos))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
