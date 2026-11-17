#!/usr/bin/env python3
"""Valida uno o más trace.json contra el formato 2.1 (tarea 6 de Datos).

Imprime OK o la lista de errores de cada archivo (con el tick, el evento y el campo) y sale con código 1
si alguno tiene errores, para que sirva en la terminal y en CI.

Uso:
    python tools/validar_trace.py tests/fixtures/trace_ejemplo.json
    python tools/validar_trace.py runs/escenario_*/trace.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import cargar_trace, validar_trace  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Valida trace.json contra el formato 2.1.")
    parser.add_argument("trace", nargs="+", help="uno o más trace.json")
    parser.add_argument("--max", type=int, default=50, help="máximo de errores a mostrar por archivo (default: 50)")
    parser.add_argument("--retraso-maximo", type=int, default=1,
                        help="ticks máximos entre el envío y la entrega de un mensaje (default: 1)")
    args = parser.parse_args(argv)

    hubo_errores = False
    for ruta in args.trace:
        try:
            trace = cargar_trace(ruta)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{ruta}: no se pudo leer: {exc}")
            hubo_errores = True
            continue
        avisos: list[str] = []
        errores = validar_trace(trace, retraso_maximo=args.retraso_maximo, avisos=avisos)
        for a in avisos[:args.max]:
            print(f"{ruta}: aviso: {a}")
        if not errores:
            print(f"{ruta}: OK")
            continue
        hubo_errores = True
        print(f"{ruta}: {len(errores)} error(es)")
        for e in errores[:args.max]:
            print(f"  - {e}")
        if len(errores) > args.max:
            print(f"  ... y {len(errores) - args.max} más")
    return 1 if hubo_errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
