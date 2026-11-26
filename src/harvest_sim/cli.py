"""Punto de entrada: python -m harvest_sim.cli config/escenario_a.json  [Bloque D]

Flujo esperado: cargar config -> ejecutar simulación -> escribir
runs/<escenario>/trace.json (con métricas) -> generar gráficas.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import logging
from pathlib import Path
import subprocess
import sys

from .config import cargar_config
from .datos import escribir_trace
from .simulacion import ejecutar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulación de cosecha multiagente (escenarios A–G; G es el campo real de El Pueblito).")
    parser.add_argument("config", help="ruta al JSON del escenario, p. ej. config/escenario_a.json")
    parser.add_argument("--salida", default="runs", help="carpeta base de salidas (default: runs)")
    parser.add_argument("--sin-plots", action="store_true", help="no generar gráficas")
    parser.add_argument("--seed", type=int, help="sobrescribe la semilla del escenario")
    parser.add_argument("--estrategia", choices=("base", "subasta", "anticipada", "anticipada_plus", "qlearning", "sarsa"),
                        help="sobrescribe la política con una estrategia del experimento")
    nivel = parser.add_mutually_exclusive_group()
    nivel.add_argument("--silencioso", action="store_true", help="log de consola: solo advertencias y errores")
    nivel.add_argument("--detallado", action="store_true", help="log de consola: nivel DEBUG")
    args = parser.parse_args(argv)
    nivel_log = logging.WARNING if args.silencioso else logging.DEBUG if args.detallado else logging.INFO
    logging.basicConfig(level=nivel_log, format="%(message)s")
    try:
        config = cargar_config(args.config)
        if args.seed is not None:
            if args.seed < 0:
                raise ValueError("--seed debe ser un entero no negativo")
            config = replace(config, seed=args.seed)
        if args.estrategia:
            from .datos import experimentos
            estrategias = getattr(experimentos, "ESTRATEGIAS", None)
            if estrategias is None:
                raise ValueError("--estrategia requiere ESTRATEGIAS de Datos")
            estrategias = {**estrategias, **getattr(experimentos, "ESTRATEGIAS_APRENDIDAS", {})}
            politica = getattr(config, "politica", None)
            if politica is None:
                raise ValueError("--estrategia requiere una configuración con politica")
            cambios = estrategias[args.estrategia]
            cambios = cambios.get("politica", cambios)
            politica = replace(politica, **cambios) if hasattr(politica, "__dataclass_fields__") else {**politica, **cambios}
            config = replace(config, politica=politica)
        if not config.nombre or config.nombre in (".", "..") or any(c in config.nombre for c in "/\\"):
            raise ValueError("el nombre del escenario debe ser un nombre de carpeta, sin rutas")
        trace = ejecutar(config)
        ruta_trace = Path(args.salida).resolve() / config.nombre / "trace.json"
        escribir_trace(trace, ruta_trace)
        logging.info("Trace guardado: %s", ruta_trace)
        if not args.sin_plots:
            plots = Path(__file__).resolve().parents[2] / "viz" / "plots.py"
            subprocess.run([sys.executable, str(plots), str(ruta_trace)], check=True,
                           stdout=subprocess.DEVNULL if args.silencioso else None)
        return 0
    except Exception as exc:
        # Frontera del ejecutable: cualquier fallo debe producir código no cero.
        print(f"error: {exc}", file=sys.stderr)
        if args.detallado:
            logging.debug("Detalle del fallo", exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
