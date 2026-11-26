#!/usr/bin/env python3
"""Exporta traces validados al proyecto de Unity (harvest-simu-visualization).  [Joel]

Corre cada escenario con cada estrategia y seed, **valida** el trace y lo copia a la carpeta destino
(normalmente `Assets/Data/Traces/` del repositorio de Unity). Nunca copia un trace inválido.

Uso:
    python tools/exportar_traces_unity.py ../harvest-simu-visualization/Assets/Data/Traces
    python tools/exportar_traces_unity.py DESTINO --escenarios escenario_d escenario_e --estrategias base anticipada --seed 3
    python tools/exportar_traces_unity.py DESTINO --ejemplo     # traces de ejemplo (guion 2.2), sin simulación

Nombres: `<escenario>__<estrategia>__seed<n>.json` (y `ejemplo_22.json` con --ejemplo).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos import escribir_trace, validar_trace  # noqa: E402
from harvest_sim.datos.experimentos import TODAS_LAS_ESTRATEGIAS, aplicar_estrategia, simulador_real  # noqa: E402


def _cargar_script(ruta: Path):
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def exportar(destino: str | Path, escenarios: list[str] | None = None, estrategias: list[str] | None = None,
             seed: int | None = None, simulador=None, carpeta_config: str | Path | None = None) -> list[Path]:
    """Corre, valida y escribe los traces; devuelve las rutas escritas. Error si alguno no es válido."""
    carpeta = Path(carpeta_config) if carpeta_config else RAIZ / "config"
    disponibles = {r.stem: r for r in sorted(carpeta.glob("escenario_*.json"))}
    escenarios = escenarios or list(disponibles)
    faltan = [e for e in escenarios if e not in disponibles]
    if faltan:
        raise ValueError(f"escenarios inexistentes {faltan}; hay: {list(disponibles)}")
    simulador = simulador or simulador_real
    rutas = []
    for nombre in escenarios:
        base = json.loads(disponibles[nombre].read_text(encoding="utf-8"))
        for estrategia in (estrategias or ["base"]):
            config = aplicar_estrategia(base, estrategia)
            if seed is not None:
                config["seed"] = seed
            trace = simulador(config)
            errores = validar_trace(trace)
            if errores:
                raise ValueError(f"{nombre} con {estrategia}: el trace no es válido: {errores[:3]}")
            ruta = Path(destino) / f"{nombre}__{estrategia}__seed{config.get('seed', 0)}.json"
            escribir_trace(trace, ruta)
            rutas.append(ruta)
    return rutas


def exportar_ejemplos(destino: str | Path) -> list[Path]:
    """Los traces de ejemplo: el guion 2.2 (2 + 2 agentes) y los tres escenarios del generador (1 + 1)."""
    rutas = []
    guion = _cargar_script(RAIZ / "tools" / "traces_ejemplo_22.py").generar()
    escribir_trace(guion, Path(destino) / "ejemplo_22.json")
    rutas.append(Path(destino) / "ejemplo_22.json")
    generador = _cargar_script(RAIZ / "tools" / "generar_trace_ejemplo.py")
    rutas += generador.generar_escenarios(Path(destino) / "ejemplos_1x1")
    return rutas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Exporta traces validados al proyecto de Unity.")
    parser.add_argument("destino", help="carpeta destino (por ejemplo Assets/Data/Traces del repo de Unity)")
    parser.add_argument("--escenarios", nargs="+", help="nombres de config/escenario_*.json (default: todos)")
    parser.add_argument("--estrategias", nargs="+", choices=list(TODAS_LAS_ESTRATEGIAS),
                        help="default: base; qlearning y sarsa necesitan la tabla del escenario (config/aprendizaje/)")
    parser.add_argument("--seed", type=int, help="sobrescribe la seed de cada escenario")
    parser.add_argument("--ejemplo", action="store_true", help="exporta los traces de ejemplo (sin simulación)")
    args = parser.parse_args(argv)
    try:
        rutas = exportar_ejemplos(args.destino) if args.ejemplo else \
            exportar(args.destino, args.escenarios, args.estrategias, args.seed)
    except NotImplementedError as exc:
        print(f"error: la simulación aún no está disponible ({exc}); usa --ejemplo", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for r in rutas:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
