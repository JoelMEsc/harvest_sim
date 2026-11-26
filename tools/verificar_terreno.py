#!/usr/bin/env python3
"""Verifica las reglas del terreno real en corridas de un escenario con mapa (por defecto G).  [Joel / Ilan]

    python tools/verificar_terreno.py                       # G, 4 estrategias × 20 seeds, en paralelo
    python tools/verificar_terreno.py --seeds 3 --estrategias base subasta

Para cada corrida revisa, desde el trace (docs/especificacion_terreno.md §7): que termine y valide; colisiones y
BLOQUEO; R10 y R12 (nadie en obstáculo ni fuera de campo); R13 (ningún carro sobre cultivo en pie) y los ticks en
que una cosechadora pisa cultivo sin cosecharlo. Imprime un resumen por estrategia y sale con 1 si algo falla.
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from harvest_sim.datos import validar_trace  # noqa: E402
from harvest_sim.datos.campo import celdas_de_campo  # noqa: E402
from harvest_sim.datos.experimentos import ESTRATEGIAS, aplicar_estrategia, simulador_real  # noqa: E402


def revisar_trace(trace: dict) -> dict:
    """Conteos de reglas desde el trace (no usa el estado interno de la simulación)."""
    mundo = trace["mundo"]
    campo = celdas_de_campo(mundo)
    prohibidas = {tuple(c) for c in mundo.get("obstaculos", [])} | {tuple(c) for c in mundo.get("fuera_de_campo", [])}
    pos, cosechadas = {}, set()
    r12 = r13 = pisa_cosechadora = 0
    for tick in trace["ticks"]:
        cosechadas_ahora = set()
        for e in tick["cambios"]:
            if e["tipo"] == "AGENTE" and "pose" in e["set"]:
                pos[e["id"]] = (e["set"]["pose"]["x"], e["set"]["pose"]["y"])
            elif e["tipo"] == "CELDA_COSECHADA":
                cosechadas_ahora.add(tuple(e["celda"]))
        cosechadas |= cosechadas_ahora
        if tick["tick"] == 0:
            continue
        for agente, p in pos.items():
            if p in prohibidas:
                r12 += 1
            if p in campo and p not in cosechadas:
                if agente.startswith("carro_"):
                    r13 += 1
                else:
                    pisa_cosechadora += 1
    eventos = collections.Counter(e["tipo"] for t in trace["ticks"] for e in t["cambios"])
    reglas = collections.Counter(e["regla"] for t in trace["ticks"] for e in t["cambios"] if e["tipo"] == "RESTRICCION")
    m = trace["metricas"]
    return {"ticks": m["tiempo_completacion"], "ocio": m.get("tiempo_ocioso_total"), "colisiones": m["colisiones"],
            "bloqueos": eventos["BLOQUEO"], "r12": r12, "r13_carros": r13, "cosechadora_pisa": pisa_cosechadora,
            "restr_r13": reglas["R13_cultivo_en_pie"], "entregado": m["porcentaje_entregado"]}


def una(args):
    escenario, estrategia, seed = args
    logging.disable(logging.WARNING)
    base = json.loads((RAIZ / "config" / f"{escenario}.json").read_text(encoding="utf-8"))
    config = aplicar_estrategia(base, estrategia)
    config["seed"] = seed
    inicio = time.time()
    try:
        trace = simulador_real(config)
    except Exception as error:  # noqa: BLE001 - se reporta
        return estrategia, seed, f"ERROR {str(error)[:160]}", None, time.time() - inicio
    errores = validar_trace(trace)
    return estrategia, seed, ("ok" if not errores else f"INVALIDO {errores[:2]}"), revisar_trace(trace), time.time() - inicio


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--escenario", default="escenario_g")
    parser.add_argument("--estrategias", nargs="+", default=list(ESTRATEGIAS))
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--procesos", type=int, default=8)
    args = parser.parse_args(argv)
    trabajos = [(args.escenario, e, s) for e in args.estrategias for s in range(args.seeds)]
    with ProcessPoolExecutor(args.procesos) as ex:
        resultados = list(ex.map(una, trabajos))
    falla = False
    for estrategia, seed, estado, _, _ in resultados:
        if estado != "ok":
            print(f"{estrategia} seed {seed}: {estado}")
            falla = True
    por = collections.defaultdict(list)
    for estrategia, _, estado, r, dur in resultados:
        if r:
            por[estrategia].append((r, dur))
    for estrategia, lista in por.items():
        n = len(lista)
        suma = {k: sum(r[k] for r, _ in lista) for k in lista[0][0]}
        print(f"{estrategia:16s} n={n} ticks={suma['ticks'] / n:.0f} ocio={suma['ocio'] / n:.0f} col={suma['colisiones']} "
              f"bloq={suma['bloqueos']} R12={suma['r12']} R13_carros={suma['r13_carros']} "
              f"cosechadora_pisa={suma['cosechadora_pisa'] / n:.1f}/corrida restr_R13={suma['restr_r13'] / n:.1f} "
              f"entregado_min={min(r['entregado'] for r, _ in lista)} t={sum(d for _, d in lista) / n:.1f}s")
        falla |= suma["colisiones"] > 0 or suma["r12"] > 0 or suma["r13_carros"] > 0
    print("fallas:", sum(1 for r in resultados if r[2] != "ok"), "de", len(resultados))
    return 1 if falla else 0


if __name__ == "__main__":
    raise SystemExit(main())
