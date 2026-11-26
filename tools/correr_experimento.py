#!/usr/bin/env python3
"""Corre un experimento: escenarios x barrido de parámetros x repeticiones.  [Joel]

Lee un JSON de experimento (ver config/experimentos/), corre cada combinación, y escribe en
<salida>/<nombre>/:
    resultados.csv            una fila por corrida (escenario, parámetros, repetición, seed, métricas)
    resumen.csv               media, desviación estándar e IC 95 % por escenario y combinación
    sensibilidad_<param>.png  la métrica elegida contra el parámetro (si el barrido tiene un solo parámetro)

Formato del JSON (además: `"estrategias": ["base", "anticipada", …]` y `"seeds": {"desde": 0,
"cantidad": 20}` o una lista; con estrategias se escriben también comparacion.csv, pareada contra
"base" (o contra `"referencia": "<estrategia>"`), y ablacion.csv, del costo J; las claves del barrido con punto entran a una sección):
    {"nombre": "tasa_transferencia",
     "escenarios": ["config/escenario_a.json", ...],     # rutas relativas a la raíz del repositorio
     "barrido": {"tasa_transferencia": [1, 2, 3, 5]},    # parámetro -> valores (producto cartesiano)
     "repeticiones": 1,                                  # seeds seed, seed+1, ...
     "metrica": "tiempo_ocioso_cosechadora"}             # la de la gráfica de sensibilidad

Uso:
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json --simulador ejemplo

`--simulador real` (por defecto) usa la simulación del equipo (config.cargar_config + simulacion.ejecutar).
`--simulador ejemplo` usa el generador de datos de ejemplo (1 cosechadora, 1 carro, sin obstáculos):
sirve para probar la herramienta mientras la simulación no existe; sus números NO son resultados.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.datos.experimentos import (  # noqa: E402
    ESTRATEGIAS,
    TODAS_LAS_ESTRATEGIAS,
    ablacion_costo,
    comparar_contra_base,
    correr_experimento,
    escribir_csv,
    resumen_por_grupo,
    simulador_real,
)


def _cargar_script(ruta: Path):
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def simulador_ejemplo(config: dict) -> dict:
    return _cargar_script(RAIZ / "tools" / "generar_trace_ejemplo.py").generar(config)


def cargar_experimento(ruta: str | Path) -> dict:
    experimento = json.loads(Path(ruta).read_text(encoding="utf-8"))
    faltan = [c for c in ("nombre", "escenarios") if c not in experimento]
    if faltan:
        raise ValueError(f"al experimento le faltan {faltan}")
    if not isinstance(experimento.get("barrido", {}), dict):
        raise ValueError("barrido debe ser un objeto {parámetro: [valores]}")
    desconocidas = [e for e in experimento.get("estrategias", []) if e not in TODAS_LAS_ESTRATEGIAS]
    if desconocidas:
        raise ValueError(f"estrategias desconocidas {desconocidas}; hay: {list(TODAS_LAS_ESTRATEGIAS)}")
    return experimento


def seeds_de(experimento: dict) -> list[int] | None:
    """`"seeds": [0, 1, …]` o `{"desde": 0, "cantidad": 20}`; None si el experimento usa `repeticiones`."""
    seeds = experimento.get("seeds")
    if seeds is None:
        return None
    if isinstance(seeds, dict):
        return list(range(seeds.get("desde", 0), seeds.get("desde", 0) + seeds["cantidad"]))
    return list(seeds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Corre un experimento (escenarios x barrido x repeticiones).")
    parser.add_argument("experimento", help="JSON del experimento (ver config/experimentos/)")
    parser.add_argument("--simulador", choices=("real", "ejemplo"), default="real",
                        help="real = simulación del equipo; ejemplo = generador de datos de ejemplo")
    parser.add_argument("--salida", default=str(RAIZ / "runs" / "experimentos"), help="carpeta base de salida")
    parser.add_argument("--procesos", type=int, default=1, help="corridas en paralelo (default: 1)")
    args = parser.parse_args(argv)

    try:
        exp = cargar_experimento(args.experimento)
        escenarios = {}
        for ruta in exp["escenarios"]:
            cfg = json.loads((RAIZ / ruta).read_text(encoding="utf-8"))
            escenarios[cfg.get("nombre") or Path(ruta).stem] = cfg
        simulador = simulador_ejemplo if args.simulador == "ejemplo" else simulador_real
        barrido = exp.get("barrido") or {}
        estrategias = exp.get("estrategias")
        filas = correr_experimento(escenarios, barrido, exp.get("repeticiones", 1), simulador,
                                   estrategias=estrategias, seeds=seeds_de(exp), procesos=args.procesos)
    except NotImplementedError as exc:
        print(f"error: la simulación del equipo aún no está implementada ({exc}); "
              "para probar la herramienta usa --simulador ejemplo", file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    carpeta = Path(args.salida) / exp["nombre"]
    parametros = list(barrido)
    resumen = resumen_por_grupo(filas, parametros)
    generados = [escribir_csv(filas, carpeta / "resultados.csv"), escribir_csv(resumen, carpeta / "resumen.csv")]
    referencia = exp.get("referencia", "base")
    if estrategias and referencia in estrategias and len(estrategias) > 1:
        generados.append(escribir_csv(comparar_contra_base(filas, base=referencia, parametros=parametros),
                                      carpeta / "comparacion.csv"))
    if estrategias and any(f.get("costo_total") is not None for f in filas):
        generados.append(escribir_csv(ablacion_costo(filas, parametros), carpeta / "ablacion.csv"))
    if estrategias:
        plots = _cargar_script(RAIZ / "viz" / "plots.py")
        generados.append(plots.grafica_estrategias(resumen, carpeta / "estrategias.png"))
        if any(f.get("costo_total") is not None for f in filas):
            generados.append(plots.grafica_costo_j(filas, carpeta / "costo_j.png"))
        if referencia in estrategias and len(estrategias) > 1 and not parametros:
            generados.append(plots.grafica_diferencias(comparar_contra_base(filas, base=referencia),
                                                       carpeta / "diferencias.png",
                                                       exp.get("metrica", "tiempo_ocioso_total"), referencia))
    if len(parametros) == 1:
        plots = _cargar_script(RAIZ / "viz" / "plots.py")
        metrica = exp.get("metrica", "tiempo_ocioso_cosechadora")
        generados.append(plots.grafica_sensibilidad(resumen, parametros[0], metrica,
                                                    carpeta / f"sensibilidad_{parametros[0]}.png"))
    if args.simulador == "ejemplo":
        print("aviso: se usó el generador de ejemplo; los números no son resultados de la simulación")
    con_variacion = sum(1 for g in resumen if g["variacion"] == "con variación")
    print(f"{len(filas)} corridas; {con_variacion} de {len(resumen)} grupos con variación entre seeds"
          if resumen else f"{len(filas)} corridas (sin filas)")
    for g in generados:
        print(g)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
